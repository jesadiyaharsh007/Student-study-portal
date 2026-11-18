/* YTEngine: plays separate H.264 video and AAC audio streams through Media Source Extensions, so quality can change
   mid-play and picture and sound stay on one clock. Bytes come from our own server (see youtube_media).
   Every SourceBuffer operation goes through one queue per track, so appends, removals and quality switches never overlap. */
(() => {
  'use strict';
  const AHEAD = 40;          // seconds to keep buffered ahead of the playhead
  const BEHIND = 30;         // seconds to keep behind it
  const INDEX_BYTES = 262144;
  const START_BUFFER = 4;    // seconds to have ready before playback starts

  const u8 = (dv, o) => dv.getUint8(o);
  const u32 = (dv, o) => dv.getUint32(o);
  const u64 = (dv, o) => dv.getUint32(o) * 4294967296 + dv.getUint32(o + 4);
  const fourcc = (dv, o) => String.fromCharCode(u8(dv, o), u8(dv, o + 1), u8(dv, o + 2), u8(dv, o + 3));
  const wait = ms => new Promise(r => setTimeout(r, ms));

  /** Reads ftyp/moov/sidx from the start of a fragmented MP4 and returns where the init segment ends and where each media segment lives. */
  function parseIndex(buf) {
    const dv = new DataView(buf);
    let o = 0, moovEnd = 0, sidx = null;
    while (o + 8 <= buf.byteLength) {
      let size = u32(dv, o); const type = fourcc(dv, o + 4); let head = 8;
      if (size === 1) { size = u64(dv, o + 8); head = 16; }
      if (size < 8) break;
      if (type === 'moof' || type === 'mdat') break;
      if (type === 'moov') moovEnd = o + size;
      if (type === 'sidx') {
        if (o + size > buf.byteLength) return { need: o + size };
        const version = u8(dv, o + head);
        let p = o + head + 4;
        p += 4;                                                   // reference_ID
        const timescale = u32(dv, p); p += 4;
        let earliest, firstOffset;
        if (version === 0) { earliest = u32(dv, p); firstOffset = u32(dv, p + 4); p += 8; }
        else { earliest = u64(dv, p); firstOffset = u64(dv, p + 8); p += 16; }
        const count = dv.getUint16(p + 2); p += 4;
        const segs = [];
        let byte = o + size + firstOffset, t = earliest;
        for (let i = 0; i < count; i++) {
          const ref = u32(dv, p), dur = u32(dv, p + 4); p += 12;
          const len = ref & 0x7fffffff;
          segs.push({ start: byte, end: byte + len - 1, time: t / timescale, dur: dur / timescale });
          byte += len; t += dur;
        }
        sidx = segs;
        break;
      }
      o += size;
    }
    if (!sidx || !moovEnd) return { need: buf.byteLength + INDEX_BYTES };
    return { initEnd: moovEnd, segs: sidx };
  }

  const bufferedEnd = (sb, t) => {
    const r = sb.buffered;
    for (let i = 0; i < r.length; i++) if (r.start(i) <= t + 0.3 && r.end(i) >= t) return r.end(i);
    return t;
  };
  const isBuffered = (sb, t) => {
    const r = sb.buffered;
    for (let i = 0; i < r.length; i++) if (r.start(i) <= t + 0.05 && r.end(i) > t + 0.5) return true;
    return false;
  };
  const segAt = (segs, t) => {
    let lo = 0, hi = segs.length - 1, ans = 0;
    while (lo <= hi) { const m = (lo + hi) >> 1; if (segs[m].time <= t) { ans = m; lo = m + 1; } else hi = m - 1; }
    return ans;
  };

  class Engine {
    /** hooks: mediaUrl(itag) -> url, onQuality({height, auto}), onError(message), onWaiting(bool), maxHeight() */
    constructor(video, hooks) {
      this.video = video; this.hooks = hooks; this.gen = 0; this.dead = false;
      this.auto = true; this.thr = 0; this.tracks = {}; this.ended = false; this.lastSwitch = 0;
    }

    static supported(manifest) {
      if (!('MediaSource' in window)) return false;
      const a = manifest.audio;
      return MediaSource.isTypeSupported(`audio/mp4; codecs="${a.codec}"`) &&
        manifest.video.some(v => MediaSource.isTypeSupported(`video/mp4; codecs="${v.codec}"`));
    }

    get formats() { return this.manifest.video.filter(v => MediaSource.isTypeSupported(`video/mp4; codecs="${v.codec}"`)); }

    async fetchRange(itag, start, end) {
      let lastErr;
      for (let attempt = 0; attempt < 4; attempt++) {
        if (this.dead) throw new Error('closed');
        try {
          const t0 = performance.now();
          const r = await fetch(this.hooks.mediaUrl(itag), { headers: { Range: `bytes=${start}-${end}` }, credentials: 'same-origin' });
          if (!(r.status === 206 || r.status === 200)) throw new Error('http ' + r.status);
          const buf = await r.arrayBuffer();
          const ms = Math.max(1, performance.now() - t0);
          const bps = buf.byteLength * 8 / (ms / 1000);
          this.thr = this.thr ? this.thr * 0.6 + bps * 0.4 : bps;
          return buf;
        } catch (e) { lastErr = e; await wait(250 * (attempt + 1) ** 2); }
      }
      throw lastErr;
    }

    async loadIndex(fmt) {
      let size = INDEX_BYTES, buf, info;
      for (let i = 0; i < 3; i++) {
        buf = await this.fetchRange(fmt.itag, 0, size - 1);
        info = parseIndex(buf);
        if (info.initEnd) break;
        size = Math.max(size * 2, info.need || size * 2);
      }
      if (!info.initEnd) throw new Error('index');
      return { fmt, init: buf.slice(0, info.initEnd), segs: info.segs };
    }

    mime(fmt, audio) { return `${audio ? 'audio' : 'video'}/mp4; codecs="${fmt.codec}"`; }

    pickStart(targetHeight) {
      const list = this.formats;
      const ok = list.filter(v => v.height <= targetHeight);
      return ok.length ? ok[ok.length - 1] : list[0];
    }

    /** Runs one SourceBuffer operation at a time, in order. */
    op(tr, fn) {
      const run = tr.q.then(async () => {
        while (tr.sb.updating) await wait(10);
        if (this.dead || this.ms.readyState === 'closed') return;
        return fn();
      });
      tr.q = run.catch(() => {});
      return run;
    }

    sbDo(tr, start) {                                           // start(): triggers appendBuffer/remove; resolves on updateend
      return new Promise((resolve, reject) => {
        const sb = tr.sb;
        const done = () => { sb.removeEventListener('updateend', ok); sb.removeEventListener('error', bad); };
        const ok = () => { done(); resolve(); };
        const bad = () => { done(); reject(new Error('sourcebuffer')); };
        sb.addEventListener('updateend', ok); sb.addEventListener('error', bad);
        try { start(); } catch (e) { done(); reject(e); }
      });
    }

    appendTo(tr, buf) {
      return this.op(tr, async () => {
        try { await this.sbDo(tr, () => tr.sb.appendBuffer(buf)); }
        catch (e) {
          if (e && e.name === 'QuotaExceededError') {
            const cut = this.video.currentTime - 6;
            if (cut > 1 && tr.sb.buffered.length) await this.sbDo(tr, () => tr.sb.remove(0, cut));
            await this.sbDo(tr, () => tr.sb.appendBuffer(buf));
          } else throw e;
        }
      });
    }

    removeFrom(tr, a, b) {
      return this.op(tr, () => this.sbDo(tr, () => tr.sb.remove(a, b)));
    }

    async load(manifest, opts = {}) {
      this.manifest = manifest;
      const v = this.video;
      this.ms = new MediaSource();
      this.url = URL.createObjectURL(this.ms);
      v.src = this.url;
      await new Promise(res => this.ms.addEventListener('sourceopen', res, { once: true }));
      this.auto = opts.quality === 'auto' || !opts.quality;
      // start modestly and climb while the connection proves itself: a stall at the start is worse than a few soft seconds
      const start = this.auto ? this.pickStart(Math.min(opts.targetHeight || 480, 480)) : (this.formats.find(f => f.height === +opts.quality) || this.pickStart(480));
      const [vi, ai] = await Promise.all([this.loadIndex(start), this.loadIndex(manifest.audio)]);
      if (this.dead) return;
      this.ms.duration = manifest.duration || vi.segs[vi.segs.length - 1].time + vi.segs[vi.segs.length - 1].dur;
      const mk = (name, fmt, idx, audio) => {
        const sb = this.ms.addSourceBuffer(this.mime(fmt, audio));
        return { name, sb, fmt, segs: idx.segs, next: segAt(idx.segs, opts.start || 0), busy: false, q: Promise.resolve(), init: idx.init };
      };
      this.tracks.video = mk('video', start, vi, false);
      this.tracks.audio = mk('audio', manifest.audio, ai, true);
      await Promise.all([this.appendTo(this.tracks.video, vi.init), this.appendTo(this.tracks.audio, ai.init)]);
      if (opts.start > 0) v.currentTime = opts.start;
      this.bind();
      this.hooks.onQuality && this.hooks.onQuality({ height: start.height, auto: this.auto });
      this.pump();
      await this.prebuffer(opts.start || 0);
    }

    /** Waits until a few seconds are ready on both tracks so playback does not start into a stall. */
    async prebuffer(t0) {
      const until = performance.now() + 8000;
      while (!this.dead && performance.now() < until) {
        const ok = Object.values(this.tracks).every(tr => tr.next >= tr.segs.length || bufferedEnd(tr.sb, t0) - t0 >= START_BUFFER);
        if (ok) return;
        await wait(80);
      }
    }

    bind() {
      const v = this.video;
      this.on = {
        seeking: () => this.onSeek(),
        timeupdate: () => this.pump(),
        waiting: () => this.hooks.onWaiting && this.hooks.onWaiting(true),
        playing: () => this.hooks.onWaiting && this.hooks.onWaiting(false),
        canplay: () => this.hooks.onWaiting && this.hooks.onWaiting(false),
      };
      Object.entries(this.on).forEach(([k, fn]) => v.addEventListener(k, fn));
      this.timer = setInterval(() => this.pump(), 700);
    }

    onSeek() {
      const t = this.video.currentTime;
      Object.values(this.tracks).forEach(tr => {
        if (!isBuffered(tr.sb, t)) { this.gen++; tr.next = segAt(tr.segs, t); }
      });
      this.ended = false;
      this.pump();
    }

    pump() { Object.values(this.tracks).forEach(tr => this.fill(tr)); }

    async fill(tr) {
      if (this.dead || tr.busy || !this.ms || this.ms.readyState === 'closed') return;
      if (tr.name === 'video' && tr.switchTo) return this.switchVideo(tr);
      const t = this.video.currentTime;
      if (tr.next >= tr.segs.length) { this.checkEnd(); return; }
      const seg = tr.segs[tr.next];
      if (seg.time > t + AHEAD) return;
      tr.busy = true;
      const gen = this.gen, idx = tr.next;
      try {
        const t0 = performance.now();
        const buf = await this.fetchRange(tr.fmt.itag, seg.start, seg.end);
        if (this.dead) return;
        if (gen === this.gen && tr.next === idx) {
          await this.appendTo(tr, buf);
          if (gen === this.gen && tr.next === idx) tr.next = idx + 1;
          if (tr.name === 'video') this.abr();
        }
        const cut = this.video.currentTime - BEHIND;
        if (cut > 2 && tr.sb.buffered.length && tr.sb.buffered.start(0) < cut - 2) this.removeFrom(tr, 0, cut).catch(() => {});
      } catch (e) {
        if (!this.dead) { this.dead = true; this.hooks.onError && this.hooks.onError('Playback was interrupted. Check your connection and try again.'); }
      } finally { tr.busy = false; }
      if (!this.dead) this.pump();
    }

    checkEnd() {
      const done = Object.values(this.tracks).every(tr => tr.next >= tr.segs.length && !tr.busy && !tr.sb.updating);
      if (done && this.ms.readyState === 'open' && !this.ended) { try { this.ms.endOfStream(); this.ended = true; } catch (e) { /* already ended */ } }
    }

    /** Gentle adaptive choice: drop one step quickly when the buffer is thin, climb one step only after a long calm stretch. */
    abr() {
      if (!this.auto) return;
      const tr = this.tracks.video, list = this.formats, cur = list.findIndex(f => f.itag === tr.fmt.itag);
      const ahead = bufferedEnd(tr.sb, this.video.currentTime) - this.video.currentTime;
      const maxH = this.hooks.maxHeight ? this.hooks.maxHeight() : 1080;
      const now = performance.now();
      let want = cur;
      if (ahead < 7 && this.thr && this.thr < tr.fmt.bitrate * 1.6 && cur > 0) want = cur - 1;
      else if (ahead > 24 && now - this.lastSwitch > 15000 && cur < list.length - 1 && list[cur + 1].height <= maxH && this.thr > list[cur + 1].bitrate * 3) want = cur + 1;
      if (want !== cur) { tr.switchTo = list[want]; tr.soft = true; }
    }

    setQuality(q) {
      const tr = this.tracks.video;
      if (!tr) return;
      if (q === 'auto') { this.auto = true; this.hooks.onQuality && this.hooks.onQuality({ height: tr.fmt.height, auto: true }); return; }
      this.auto = false;
      const f = this.formats.find(x => x.height === +q);
      if (f && f.itag !== tr.fmt.itag) { tr.switchTo = f; tr.soft = false; this.pump(); }
      else this.hooks.onQuality && this.hooks.onQuality({ height: tr.fmt.height, auto: false });
    }

    /** Changes the picture quality without emptying the buffer: what is already loaded plays out, the new quality follows it.
        A manual choice drops only the seconds beyond a short lead, so the change shows up quickly without a stall. */
    async switchVideo(tr) {
      const f = tr.switchTo, soft = tr.soft; tr.switchTo = null;
      if (!f || f.itag === tr.fmt.itag) return;
      tr.busy = true;
      try {
        const info = await this.loadIndex(f);
        if (this.dead) return;
        const t = this.video.currentTime;
        await this.op(tr, async () => {
          if (info.fmt.codec !== tr.fmt.codec && tr.sb.changeType) tr.sb.changeType(this.mime(f));
        });
        let from;
        if (soft) {
          from = bufferedEnd(tr.sb, t);                       // continue where the buffer ends
        } else {
          from = t + 5;                                       // keep five seconds so playback does not stop
          if (tr.sb.buffered.length && tr.sb.buffered.end(tr.sb.buffered.length - 1) > from + 0.5) await this.removeFrom(tr, from, Infinity);
          from = Math.min(from, bufferedEnd(tr.sb, t));
        }
        await this.appendTo(tr, info.init);
        tr.fmt = f; tr.segs = info.segs; tr.next = segAt(info.segs, from);
        this.gen++; this.ended = false; this.lastSwitch = performance.now();
        this.hooks.onQuality && this.hooks.onQuality({ height: f.height, auto: this.auto });
      } catch (e) { /* keep the current quality */ } finally { tr.busy = false; }
      if (!this.dead) this.pump();
    }

    destroy() {
      this.dead = true;
      clearInterval(this.timer);
      const v = this.video;
      if (this.on) Object.entries(this.on).forEach(([k, fn]) => v.removeEventListener(k, fn));
      try { v.pause(); v.removeAttribute('src'); v.load(); } catch (e) { /* ignore */ }
      if (this.url) URL.revokeObjectURL(this.url);
    }
  }

  window.YTEngine = Engine;
})();
