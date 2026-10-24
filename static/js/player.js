/* StudyPlayer: the one video player for the whole site, with its own controls (quality, speed, captions, fullscreen).
   On the Videos page it sits over the watch stage; everywhere else it docks bottom-right as a mini player and keeps going.
   State is saved per tab, so moving to another section resumes where it was. */
(() => {
  'use strict';
  const host = document.getElementById('ytPlayer');
  if (!host) return;
  const $ = id => document.getElementById(id);
  const reduce = matchMedia('(prefers-reduced-motion: reduce)').matches;
  const KEY = 'sp:player', PREFS = 'sp:prefs';
  const esc = s => String(s == null ? '' : s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

  const fill = d => `<svg viewBox="0 0 24 24" aria-hidden="true"><path d="${d}" fill="currentColor"/></svg>`;
  const ICON = {
    play: fill('M8 5.14v13.72a1 1 0 0 0 1.52.85l11.1-6.86a1 1 0 0 0 0-1.7L9.52 4.29A1 1 0 0 0 8 5.14z'),
    pause: fill('M7 4.5h3.2a1 1 0 0 1 1 1v13a1 1 0 0 1-1 1H7a1 1 0 0 1-1-1v-13a1 1 0 0 1 1-1zm6.8 0H17a1 1 0 0 1 1 1v13a1 1 0 0 1-1 1h-3.2a1 1 0 0 1-1-1v-13a1 1 0 0 1 1-1z'),
    vol: fill('M3 9v6h4l5 5V4L7 9H3zm13.5 3c0-1.77-1.02-3.29-2.5-4.03v8.05c1.48-.73 2.5-2.25 2.5-4.02zM14 3.23v2.06c2.89.86 5 3.54 5 6.71s-2.11 5.85-5 6.71v2.06c4.01-.91 7-4.49 7-8.77s-2.99-7.86-7-8.77z'),
    low: fill('M18.5 12c0-1.77-1.02-3.29-2.5-4.03v8.05c1.48-.73 2.5-2.25 2.5-4.02zM5 9v6h4l5 5V4L9 9H5z'),
    mute: fill('M16.5 12c0-1.77-1.02-3.29-2.5-4.03v2.21l2.45 2.45c.03-.2.05-.41.05-.63zm2.5 0c0 .94-.2 1.82-.54 2.64l1.51 1.51C20.63 14.91 21 13.5 21 12c0-4.28-2.99-7.86-7-8.77v2.06c2.89.86 5 3.54 5 6.71zM4.27 3L3 4.27 7.73 9H3v6h4l5 5v-6.73l4.25 4.25c-.67.52-1.42.93-2.25 1.18v2.06c1.38-.31 2.63-.95 3.69-1.81L19.73 21 21 19.73l-9-9L4.27 3zM12 4L9.91 6.09 12 8.18V4z'),
    cc: fill('M19 4H5a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V6a2 2 0 0 0-2-2zm-8 7H9.5v-.5h-2v3h2V13H11v1a1 1 0 0 1-1 1H7a1 1 0 0 1-1-1v-4a1 1 0 0 1 1-1h3a1 1 0 0 1 1 1v1zm7 0h-1.5v-.5h-2v3h2V13H18v1a1 1 0 0 1-1 1h-3a1 1 0 0 1-1-1v-4a1 1 0 0 1 1-1h3a1 1 0 0 1 1 1v1z'),
    gear: fill('M19.14 12.94c.04-.3.06-.61.06-.94 0-.32-.02-.64-.07-.94l2.03-1.58c.18-.14.23-.41.12-.61l-1.92-3.32c-.12-.22-.37-.29-.59-.22l-2.39.96c-.5-.38-1.03-.7-1.62-.94l-.36-2.54c-.04-.24-.24-.41-.48-.41h-3.84c-.24 0-.43.17-.47.41l-.36 2.54c-.59.24-1.13.57-1.62.94l-2.39-.96c-.22-.08-.47 0-.59.22L2.74 8.87c-.12.21-.08.47.12.61l2.03 1.58c-.05.3-.09.63-.09.94s.02.64.07.94l-2.03 1.58c-.18.14-.23.41-.12.61l1.92 3.32c.12.22.37.29.59.22l2.39-.96c.5.38 1.03.7 1.62.94l.36 2.54c.05.24.24.41.48.41h3.84c.24 0 .44-.17.47-.41l.36-2.54c.59-.24 1.13-.56 1.62-.94l2.39.96c.22.08.47 0 .59-.22l1.92-3.32c.12-.22.07-.47-.12-.61l-2.01-1.58zM12 15.6c-1.98 0-3.6-1.62-3.6-3.6s1.62-3.6 3.6-3.6 3.6 1.62 3.6 3.6-1.62 3.6-3.6 3.6z'),
    pip: fill('M19 11h-8v6h8v-6zm4 8V4.98C23 3.88 22.1 3 21 3H3c-1.1 0-2 .88-2 1.98V19c0 1.1.9 2 2 2h18c1.1 0 2-.9 2-2zm-2 .02H3V4.97h18v14.05z'),
    fs: fill('M7 14H5v5h5v-2H7v-3zm-2-4h2V7h3V5H5v5zm12 7h-3v2h5v-5h-2v3zM14 5v2h3v3h2V5h-5z'),
    fsx: fill('M5 16h3v3h2v-5H5v2zm3-8H5v2h5V5H8v3zm6 11h2v-3h3v-2h-5v5zm2-11V5h-2v5h5V8h-3z'),
    back: fill('M11.99 5V1l-5 5 5 5V7c3.31 0 6 2.69 6 6s-2.69 6-6 6-6-2.69-6-6h-2c0 4.42 3.58 8 8 8s8-3.58 8-8-3.58-8-8-8zm-1.1 11H10v-3.3L9 13v-.7l1.8-.6h.1V16zm4.3-1.8c0 .3 0 .6-.1.8l-.3.6s-.3.3-.5.3-.4.1-.6.1-.4 0-.6-.1-.3-.2-.5-.3-.2-.3-.3-.6-.1-.5-.1-.8v-.7c0-.3 0-.6.1-.8l.3-.6s.3-.3.5-.3.4-.1.6-.1.4 0 .6.1.3.2.5.3.2.3.3.6.1.5.1.8v.7zm-.9-.8v-.5s-.1-.2-.1-.3-.1-.1-.2-.2-.2-.1-.3-.1-.2 0-.3.1l-.2.2s-.1.2-.1.3v2s.1.2.1.3.1.1.2.2.2.1.3.1.2 0 .3-.1l.2-.2s.1-.2.1-.3v-1.5z'),
    fwd: fill('M4 13c0 4.4 3.6 8 8 8s8-3.6 8-8h-2c0 3.3-2.7 6-6 6s-6-2.7-6-6 2.7-6 6-6v4l5-5-5-5v4c-4.4 0-8 3.6-8 8zm6.8 3H10v-3.3L9 13v-.7l1.8-.6h.1V16zm4.3-1.8c0 .3 0 .6-.1.8l-.3.6s-.3.3-.5.3-.4.1-.6.1-.4 0-.6-.1-.3-.2-.5-.3-.2-.3-.3-.6-.1-.5-.1-.8v-.7c0-.3 0-.6.1-.8l.3-.6s.3-.3.5-.3.4-.1.6-.1.4 0 .6.1.3.2.5.3.2.3.3.6.1.5.1.8v.7zm-.8-.8v-.5c0-.1-.1-.2-.1-.3s-.1-.1-.2-.2-.2-.1-.3-.1-.2 0-.3.1l-.2.2s-.1.2-.1.3v2s.1.2.1.3.1.1.2.2.2.1.3.1.2 0 .3-.1l.2-.2s.1-.2.1-.3v-1.5z'),
    prev: fill('M6 6h2v12H6zm3.5 6l8.5 6V6z'),
    next: fill('M6 18l8.5-6L6 6v12zM16 6v12h2V6h-2z'),
    check: fill('M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z'),
    chev: fill('M10 6L8.59 7.41 13.17 12l-4.58 4.59L10 18l6-6z'),
    chevl: fill('M15.41 7.41L14 6l-6 6 6 6 1.41-1.41L10.83 12z'),
    sun: fill('M12 7c-2.76 0-5 2.24-5 5s2.24 5 5 5 5-2.24 5-5-2.24-5-5-5zM2 13h2c.55 0 1-.45 1-1s-.45-1-1-1H2c-.55 0-1 .45-1 1s.45 1 1 1zm18 0h2c.55 0 1-.45 1-1s-.45-1-1-1h-2c-.55 0-1 .45-1 1s.45 1 1 1zM11 2v2c0 .55.45 1 1 1s1-.45 1-1V2c0-.55-.45-1-1-1s-1 .45-1 1zm0 18v2c0 .55.45 1 1 1s1-.45 1-1v-2c0-.55-.45-1-1-1s-1 .45-1 1zM5.99 4.58c-.39-.39-1.03-.39-1.41 0s-.39 1.03 0 1.41l1.06 1.06c.39.39 1.03.39 1.41 0s.39-1.03 0-1.41L5.99 4.58zm12.37 12.37c-.39-.39-1.03-.39-1.41 0s-.39 1.03 0 1.41l1.06 1.06c.39.39 1.03.39 1.41 0s.39-1.03 0-1.41l-1.06-1.06zm1.06-10.96c.39-.39.39-1.03 0-1.41s-1.03-.39-1.41 0l-1.06 1.06c-.39.39-.39 1.03 0 1.41s1.03.39 1.41 0l1.06-1.06zM7.05 18.36c.39-.39.39-1.03 0-1.41s-1.03-.39-1.41 0l-1.06 1.06c-.39.39-.39 1.03 0 1.41s1.03.39 1.41 0l1.06-1.06z'),
  };

  const read = (store, k, d) => { try { return JSON.parse(store.getItem(k) || 'null') || d; } catch (e) { return d; } };
  const prefs = Object.assign({ vol: 1, muted: false, rate: 1, quality: 'auto', cc: '', autoplay: true }, read(localStorage, PREFS, {}));
  if (prefs.quality === '144' || !prefs.quality) { prefs.quality = 'auto'; savePrefs(); }
  const savePrefs = () => { try { localStorage.setItem(PREFS, JSON.stringify(prefs)); } catch (e) { /* storage blocked */ } };

  /* ------------------------------------------------------------------ markup */
  const frame = $('ytFrame');
  frame.innerHTML = `
    <video class="yt-video" playsinline preload="auto"></video>
    <div class="yt-embed" id="ytEmbed" hidden></div>
    <div class="yt-ui" data-state="idle">
      <div class="yt-hud" hidden><span class="yt-hud-icon"></span><span class="yt-hud-text"></span><div class="yt-hud-bar" hidden><i class="yt-hud-fill"></i></div></div>
      <div class="yt-cc" hidden><span></span></div>
      <div class="yt-spin" hidden><i></i></div>
      <button type="button" class="yt-bigplay" aria-label="Play">${ICON.play}</button>
      <div class="yt-top"><b class="yt-vtitle"></b></div>
      <div class="yt-ctrl">
        <div class="yt-seek" role="slider" aria-label="Seek" tabindex="0" aria-valuemin="0" aria-valuemax="100" aria-valuenow="0">
          <div class="yt-rail"><i class="yt-buf"></i><i class="yt-played"></i></div><i class="yt-knob"></i><span class="yt-tip">0:00</span>
        </div>
        <div class="yt-row">
          <div class="yt-grp">
            <button type="button" class="yt-cb yt-nav" data-a="prev" aria-label="Previous video" title="Previous (Shift+P)">${ICON.prev}</button>
            <button type="button" class="yt-cb yt-primary" data-a="play" aria-label="Play">${ICON.play}</button>
            <button type="button" class="yt-cb yt-nav" data-a="next" aria-label="Next video" title="Next (Shift+N)">${ICON.next}</button>
            <div class="yt-vol"><button type="button" class="yt-cb" data-a="mute" aria-label="Mute" title="Mute (M)">${ICON.vol}</button><input class="yt-volr" type="range" min="0" max="1" step="0.02" value="1" aria-label="Volume"></div>
            <span class="yt-time">0:00 / 0:00</span>
          </div>
          <span class="yt-gap"></span>
          <div class="yt-grp">
            <button type="button" class="yt-cb" data-a="cc" aria-label="Captions" title="Captions (C)">${ICON.cc}</button>
            <button type="button" class="yt-cb yt-gearb" data-a="settings" aria-label="Settings" title="Quality and speed">${ICON.gear}</button>
            <button type="button" class="yt-cb yt-pipb" data-a="pip" aria-label="Picture in picture" title="Picture in picture">${ICON.pip}</button>
            <button type="button" class="yt-cb" data-a="fs" aria-label="Full screen" title="Full screen (F)">${ICON.fs}</button>
          </div>
        </div>
      </div>
      <div class="yt-menu" hidden></div>
    </div>`;
  const video = frame.querySelector('.yt-video');
  const ui = frame.querySelector('.yt-ui');
  const q = sel => frame.querySelector(sel);
  const el = {
    toggle: $('ytToggle'), title: $('ytMiniTitle'), prog: $('ytProg'), err: $('ytErr'), errOpen: $('ytErrOpen'), errNext: $('ytErrNext'),
    errTitle: $('ytErrTitle'), errText: $('ytErrText'), embed: q('#ytEmbed'),
    cc: q('.yt-cc'), ccText: q('.yt-cc span'), spin: q('.yt-spin'), vtitle: q('.yt-vtitle'),
    seek: q('.yt-seek'), buf: q('.yt-buf'), played: q('.yt-played'), knob: q('.yt-knob'), tip: q('.yt-tip'),
    time: q('.yt-time'), volr: q('.yt-volr'), menu: q('.yt-menu'),
    bPlay: q('[data-a=play]'), bMute: q('[data-a=mute]'), bFs: q('[data-a=fs]'), bCc: q('[data-a=cc]'),
    hud: q('.yt-hud'), hudIcon: q('.yt-hud-icon'), hudText: q('.yt-hud-text'), hudBar: q('.yt-hud-bar'), hudFill: q('.yt-hud-fill'),
  };
  if (!document.pictureInPictureEnabled && !window.documentPictureInPicture) q('.yt-pipb').hidden = true;

  let hudTimer = 0;
  function showHud(iconHtml, text, percent) {
    if (!el.hud) return;
    el.hudIcon.innerHTML = iconHtml;
    el.hudText.textContent = text;
    if (typeof percent === 'number' && !isNaN(percent)) {
      if (el.hudBar) el.hudBar.hidden = false;
      el.hudFill.style.transform = `scaleX(${Math.max(0, Math.min(1, percent))})`;
    } else {
      if (el.hudBar) el.hudBar.hidden = true;
    }
    el.hud.hidden = false;
    el.hud.classList.add('show');
    clearTimeout(hudTimer);
    hudTimer = setTimeout(() => {
      el.hud.classList.remove('show');
      setTimeout(() => { if (!el.hud.classList.contains('show')) el.hud.hidden = true; }, 200);
    }, 1100);
  }

  const state = { id: null, meta: {}, mode: 'none', playing: false, time: 0, duration: 0, stage: null, tok: 0, manifest: null, cues: [], tracks: [], ccLang: '', quality: 'auto', height: 0, engineType: 'mse' };
  const listeners = {};
  const emit = (name, arg) => {
    (listeners[name] || []).forEach(fn => fn(arg));
    if (name === 'ended' && state.mode === 'mini' && prefs.autoplay) autoNext();   // a docked player goes on to the next video by itself
  };
  let engine = null, embedPlayer = null, embedTimer = 0;

  let currentBrightness = 1.0;
  function setBrightness(val) {
    currentBrightness = Math.max(0.15, Math.min(1.8, val));
    frame.style.setProperty('--yt-bright', currentBrightness);
    const percent = (currentBrightness - 0.15) / (1.8 - 0.15);
    showHud(ICON.sun, `Brightness: ${Math.round(currentBrightness * 100)}%`, percent);
  }

  function paintVolume() {
    const isMuted = !!(prefs.muted || prefs.vol === 0);
    const v = isMuted ? 0 : prefs.vol;
    el.volr.value = v;
    el.volr.style.setProperty('--v', `${v * 100}%`);
    const icon = isMuted ? ICON.mute : (v < .5 ? ICON.low : ICON.vol);
    el.bMute.innerHTML = icon;
    el.bMute.setAttribute('aria-label', isMuted ? 'Unmute' : 'Mute');
    if (state.engineType === 'embed' && embedPlayer) {
      if (isMuted) {
        if (typeof embedPlayer.mute === 'function') embedPlayer.mute();
        if (typeof embedPlayer.setVolume === 'function') embedPlayer.setVolume(0);
      } else {
        if (typeof embedPlayer.unMute === 'function') embedPlayer.unMute();
        const targetVol = Math.round(v * 100);
        if (typeof embedPlayer.setVolume === 'function') embedPlayer.setVolume(targetVol);
      }
      const iframe = document.getElementById('ytIframeHost');
      if (iframe && iframe.contentWindow) {
        try {
          if (isMuted) {
            iframe.contentWindow.postMessage(JSON.stringify({ event: 'command', func: 'mute', args: [] }), '*');
            iframe.contentWindow.postMessage(JSON.stringify({ event: 'command', func: 'setVolume', args: [0] }), '*');
          } else {
            const targetVol = Math.round(v * 100);
            iframe.contentWindow.postMessage(JSON.stringify({ event: 'command', func: 'unMute', args: [] }), '*');
            iframe.contentWindow.postMessage(JSON.stringify({ event: 'command', func: 'setVolume', args: [targetVol] }), '*');
          }
        } catch (e) {}
      }
    }
  }

  function applyVolume(v, muted, showFeedback = false) {
    v = Math.max(0, Math.min(1, v));
    const isMuted = !!(muted || v === 0);
    prefs.vol = v;
    prefs.muted = isMuted;
    savePrefs();
    video.volume = isMuted ? 0 : v;
    video.muted = isMuted;
    if (state.engineType === 'embed') {
      try { video.pause(); } catch (e) {}
    }
    paintVolume();
    if (showFeedback) {
      const icon = isMuted ? ICON.mute : (v < 0.5 ? ICON.low : ICON.vol);
      showHud(icon, isMuted ? 'Muted' : `${Math.round(v * 100)}%`, isMuted ? 0 : v);
    }
  }

  function setGestureVolume(val) {
    const v = Math.max(0, Math.min(1, val));
    applyVolume(v, v === 0, true);
  }

  // The next video comes from the list the Videos page saved with this video (see renderNext in yt.js), so it works on every page.
  function autoNext() {
    const q = state.meta.related || [];                       // the queue the Videos page made
    const i = q.findIndex(v => v && v.id === state.id);
    let list = q, n = i >= 0 ? q[i + 1] : null;
    if (!n) { list = (state.meta.fresh || []).filter(v => v && v.id && v.id !== state.id); n = list[0]; }   // queue done: last video's suggestions
    if (!n) return;
    const pl = state.meta.playlist, plList = state.meta.list;
    api.open(n.id, {
      title: n.title, channel: n.channel, channel_id: n.channel_id,
      avatar: n.avatar, views: n.views, published: n.published,
      duration: n.duration, thumb: n.thumbnail || n.thumb,
      list: plList, playlist: pl
    }, { autoplay: true });
    state.meta.related = list;
    if (pl) state.meta.playlist = pl;
    if (plList) state.meta.list = plList;
    save();
  }

  let ytApiReady = false, ytApiQueue = [];
  const prevYtReady = window.onYouTubeIframeAPIReady;
  window.onYouTubeIframeAPIReady = () => {
    if (typeof prevYtReady === 'function') {
      try { prevYtReady(); } catch (e) {}
    }
    ytApiReady = true;
    while (ytApiQueue.length) {
      const fn = ytApiQueue.shift();
      try { fn(); } catch (e) {}
    }
  };
  function ensureYTApi(cb, onFail) {
    if (window.YT && window.YT.Player) {
      cb();
      return;
    }
    ytApiQueue.push(cb);
    if (!document.getElementById('ytApiScript')) {
      const s = document.createElement('script');
      s.id = 'ytApiScript';
      s.src = 'https://www.youtube.com/iframe_api';
      s.onerror = () => {
        if (typeof onFail === 'function') onFail();
      };
      document.head.appendChild(s);
    }
    setTimeout(() => {
      if (!window.YT || !window.YT.Player) {
        if (typeof onFail === 'function') onFail();
      }
    }, 4500);
  }

  const fmt = t => {
    t = Math.max(0, Math.floor(t || 0));
    const h = Math.floor(t / 3600), m = Math.floor(t / 60) % 60, s = t % 60;
    return (h ? h + ':' + String(m).padStart(2, '0') : m) + ':' + String(s).padStart(2, '0');
  };
  let svc = null;
  async function ensureService() { return false; }
  const urlFor = (attr, id, extra) => {
    let u = (host.dataset[attr] || '').replace('XXXXXXXXXXX', encodeURIComponent(id));
    Object.entries(extra || {}).forEach(([k, v]) => { u = u.replace(k, v); });
    return u;
  };

  /* ------------------------------------------------------------------ persistence */
  let lastSave = 0;
  const save = () => {
    try {
      if (!state.id) { sessionStorage.removeItem(KEY); return; }
      sessionStorage.setItem(KEY, JSON.stringify({ id: state.id, meta: state.meta, time: state.time, playing: state.playing, ts: Date.now() }));
    } catch (e) { /* storage blocked */ }
  };
  addEventListener('pagehide', save);

  /* ------------------------------------------------------------------ placement */
  let tracking = 0;
  function place(animate) {
    if (state.mode === 'none') return;
    const watching = state.mode === 'watch' && state.stage && document.contains(state.stage);
    let x, y, w, h;
    if (watching) {
      const r = state.stage.getBoundingClientRect();
      x = r.left; y = r.top; w = r.width; h = r.height;
      host.style.setProperty('--bar', '0px');
    } else {
      w = Math.min(360, innerWidth - 24);
      h = Math.round(w * 9 / 16) + 52;
      x = innerWidth - w - 12; y = innerHeight - h - 12;
      host.style.setProperty('--bar', '52px');
    }
    host.classList.toggle('sync', !animate);
    host.classList.toggle('mini', !watching);
    host.style.width = w + 'px'; host.style.height = h + 'px';
    host.style.transform = `translate(${Math.round(x)}px, ${Math.round(y)}px)`;
  }
  function track(ms) {
    const end = performance.now() + ms;
    cancelAnimationFrame(tracking);
    const step = () => { place(false); if (performance.now() < end) tracking = requestAnimationFrame(step); };
    tracking = requestAnimationFrame(step);
  }
  addEventListener('scroll', () => { if (state.mode === 'watch') place(false); }, { passive: true });
  addEventListener('resize', () => place(false));

  /* ------------------------------------------------------------------ UI state */
  const setPlaying = on => {
    if (state.playing === on && el.toggle.innerHTML) return;
    state.playing = on;
    el.toggle.innerHTML = on ? ICON.pause : ICON.play;
    el.toggle.setAttribute('aria-label', on ? 'Pause' : 'Play');
    el.bPlay.innerHTML = on ? ICON.pause : ICON.play;
    el.bPlay.setAttribute('aria-label', on ? 'Pause' : 'Play');
    ui.dataset.state = on ? 'playing' : (state.ready ? 'paused' : ui.dataset.state);
    emit('playing', on);
  };
  const setWaiting = on => { el.spin.hidden = !on; };
  function showError(title, text) {
    el.errOpen.href = `https://www.youtube.com/watch?v=${encodeURIComponent(state.id || '')}`;
    el.errTitle.textContent = title || "This video can't be played here";
    el.errText.textContent = text || 'YouTube would not give us this video right now.';
    el.err.hidden = false;
    ui.dataset.state = 'error';
    setWaiting(false); setPlaying(false);
    emit('error');
  }
  const hideError = () => { el.err.hidden = true; };

  /* ------------------------------------------------------------------ controls: seek bar, volume, time */
  function paint() {
    const isEmbed = state.engineType === 'embed' && embedPlayer;
    const d = (isEmbed && embedPlayer.getDuration) ? (embedPlayer.getDuration() || state.duration || 0) : (video.duration || state.duration || 0);
    const t = (isEmbed && embedPlayer.getCurrentTime) ? (embedPlayer.getCurrentTime() || state.time || 0) : (video.currentTime || state.time || 0);
    state.time = t;
    if (d > 0) state.duration = d;
    const p = d ? Math.min(1, t / d) : 0;
    el.played.style.transform = `scaleX(${p})`;
    el.knob.style.transform = `translateX(${p * el.seek.clientWidth}px)`;
    el.seek.setAttribute('aria-valuenow', String(Math.round(p * 100)));
    el.time.textContent = `${fmt(t)} / ${fmt(d)}`;
    el.prog.style.transform = `scaleX(${p})`;
    let end = 0;
    if (isEmbed && embedPlayer.getVideoLoadedFraction) {
      end = (embedPlayer.getVideoLoadedFraction() || 0) * d;
    } else {
      for (let i = 0; i < video.buffered.length; i++) if (video.buffered.start(i) <= t + 0.5 && video.buffered.end(i) >= t) end = video.buffered.end(i);
    }
    el.buf.style.transform = `scaleX(${d ? Math.min(1, end / d) : 0})`;
    paintCaption(t);
  }
  const seekTo = t => {
    const isEmbed = state.engineType === 'embed' && embedPlayer;
    const d = (isEmbed && embedPlayer.getDuration) ? (embedPlayer.getDuration() || state.duration || 0) : (video.duration || state.duration || 0);
    const target = Math.max(0, Math.min(d || t, t));
    state.time = target;
    if (isEmbed && embedPlayer.seekTo) {
      embedPlayer.seekTo(target, true);
    } else {
      video.currentTime = target;
    }
    paint();
  };
  let scrubbing = false;
  const fracAt = e => { const r = el.seek.getBoundingClientRect(); return Math.max(0, Math.min(1, (e.clientX - r.left) / r.width)); };
  el.seek.addEventListener('pointerdown', e => { scrubbing = true; el.seek.setPointerCapture(e.pointerId); ui.classList.add('scrub'); seekTo(fracAt(e) * (video.duration || state.duration || 0)); });
  el.seek.addEventListener('pointermove', e => {
    const f = fracAt(e), d = video.duration || state.duration || 0;
    el.tip.textContent = fmt(f * d); el.tip.style.transform = `translateX(${f * el.seek.clientWidth}px) translateX(-50%)`;
    if (scrubbing) seekTo(f * d);
  });
  const endScrub = () => { scrubbing = false; ui.classList.remove('scrub'); };
  el.seek.addEventListener('pointerup', endScrub); el.seek.addEventListener('pointercancel', endScrub);
  el.seek.addEventListener('keydown', e => {
    if (e.key === 'ArrowLeft') { seekTo(video.currentTime - 5); e.preventDefault(); e.stopPropagation(); }
    else if (e.key === 'ArrowRight') { seekTo(video.currentTime + 5); e.preventDefault(); e.stopPropagation(); }
  });

  const iconVol = () => (prefs.muted || prefs.vol === 0) ? ICON.mute : (prefs.vol < .5 ? ICON.low : ICON.vol);
  el.volr.addEventListener('input', () => {
    applyVolume(+el.volr.value, +el.volr.value === 0, false);
  });
  video.addEventListener('volumechange', () => {
    if (state.engineType !== 'embed') paintVolume();
  });
  video.volume = prefs.vol; video.muted = prefs.muted; paintVolume();

  /* ------------------------------------------------------------------ video events */
  let endingTriggered = false;
  video.addEventListener('play', () => { hideError(); setPlaying(true); endingTriggered = false; });
  video.addEventListener('pause', () => { if (!video.ended && !endingTriggered) setPlaying(false); });
  video.addEventListener('ended', () => {
    if (!endingTriggered) {
      endingTriggered = true;
      setPlaying(false);
      ui.dataset.state = 'ended';
      emit('ended');
    }
  });
  video.addEventListener('playing', () => { state.ready = true; setWaiting(false); });
  video.addEventListener('durationchange', () => { state.duration = video.duration || state.duration; paint(); });
  video.addEventListener('progress', paint);
  video.addEventListener('timeupdate', () => {
    state.time = video.currentTime;
    paint();
    if (Date.now() - lastSave > 2000) { lastSave = Date.now(); save(); }
    if (prefs.autoplay && state.duration > 2 && state.time >= state.duration - 0.35 && !endingTriggered) {
      endingTriggered = true;
      setPlaying(false);
      ui.dataset.state = 'ended';
      emit('ended');
    }
  });
  video.addEventListener('seeking', () => { if (state.ready) setWaiting(true); });
  video.addEventListener('seeked', () => setWaiting(false));
  video.addEventListener('error', () => {
    if ((state.engineType === 'native' || state.engineType === 'mse') && state.id) {
      startEmbedEngine(state.id, video.currentTime || state.time || 0, true);
    }
  });

  const toggle = () => {
    if (state.mode === 'none') return;
    if (state.engineType === 'embed' && embedPlayer) {
      if (typeof embedPlayer.getPlayerState === 'function') {
        const s = embedPlayer.getPlayerState();
        if (s === 1) embedPlayer.pauseVideo();
        else embedPlayer.playVideo();
      } else if (state.playing) {
        if (embedPlayer.pauseVideo) embedPlayer.pauseVideo();
      } else {
        if (embedPlayer.playVideo) embedPlayer.playVideo();
      }
      return;
    }
    if (video.ended) { seekTo(0); }
    if (video.paused) video.play().catch(() => {}); else video.pause();
  };

  /* ------------------------------------------------------------------ captions */
  function paintCaption(t) {
    const cues = state.cues;
    if (!state.ccLang || !cues.length) { el.cc.hidden = true; return; }
    let lo = 0, hi = cues.length - 1, hit = null;
    while (lo <= hi) { const m = (lo + hi) >> 1; if (cues[m][0] <= t) { hit = m; lo = m + 1; } else hi = m - 1; }
    const c = hit !== null && cues[hit][1] >= t ? cues[hit] : null;
    if (c) { if (el.ccText.textContent !== c[2]) el.ccText.textContent = c[2]; el.cc.hidden = false; } else el.cc.hidden = true;
  }
  async function setCaptions(lang) {
    state.ccLang = lang; state.cues = [];
    el.bCc.classList.toggle('on', !!lang);
    prefs.cc = lang; savePrefs();
    if (state.engineType === 'embed' && embedPlayer) {
      try {
        if (typeof embedPlayer.loadModule === 'function') embedPlayer.loadModule('captions');
        if (typeof embedPlayer.setOption === 'function') {
          embedPlayer.setOption('captions', 'track', lang ? { languageCode: lang } : {});
          embedPlayer.setOption('captions', 'reload', true);
        }
      } catch (e) {}
      const iframe = document.getElementById('ytIframeHost');
      if (iframe && iframe.contentWindow) {
        try {
          iframe.contentWindow.postMessage(JSON.stringify({ event: 'command', func: 'loadModule', args: ['captions'] }), '*');
          iframe.contentWindow.postMessage(JSON.stringify({ event: 'command', func: 'setOption', args: ['captions', 'track', lang ? { languageCode: lang } : {}] }), '*');
          iframe.contentWindow.postMessage(JSON.stringify({ event: 'command', func: 'setOption', args: ['captions', 'reload', true] }), '*');
        } catch (e) {}
      }
    }
    if (!lang) {
      el.cc.hidden = true;
      if (el.ccText) el.ccText.textContent = '';
      showHud(ICON.cc, 'Captions: Off');
      return;
    }
    const track = state.tracks.find(t => t.lang === lang);
    showHud(ICON.cc, `Captions: ${(track && track.name) || lang.toUpperCase()}`);
    const id = state.id;
    try {
      const r = await fetch(urlFor('cuesUrl', id, { LANG: encodeURIComponent(lang) }), { credentials: 'same-origin' });
      const d = await r.json();
      if (state.id === id && state.ccLang === lang) {
        state.cues = d.cues || [];
        paintCaption(state.time || video.currentTime || 0);
      }
    } catch (e) { /* captions from embedPlayer will render if server cues are unavailable */ }
  }
  function syncEmbedCaptions() {
    if (!embedPlayer || typeof embedPlayer.getOption !== 'function') return;
    try {
      const list = embedPlayer.getOption('captions', 'tracklist') || [];
      if (Array.isArray(list) && list.length) {
        list.forEach(t => {
          const lang = t.languageCode || t.vssId;
          if (lang && !state.tracks.some(x => x.lang === lang)) {
            state.tracks.push({
              lang: lang,
              name: t.displayName || t.languageName || lang,
              auto: t.kind === 'asr' || !!t.is_default
            });
          }
        });
        el.bCc.hidden = !state.tracks.length;
        if (state.ccLang) {
          embedPlayer.setOption('captions', 'track', { languageCode: state.ccLang });
        } else if (prefs.cc && state.tracks.some(t => t.lang === prefs.cc)) {
          setCaptions(prefs.cc);
        }
      }
    } catch (e) {}
  }
  async function loadCaptionTracks(id) {
    state.tracks = []; state.ccLang = ''; state.cues = [];
    el.bCc.classList.remove('on');
    try {
      const r = await fetch(urlFor('captionsUrl', id), { credentials: 'same-origin' });
      const d = await r.json();
      if (state.id === id && Array.isArray(d.tracks)) {
        d.tracks.forEach(t => {
          if (!state.tracks.some(x => x.lang === t.lang)) state.tracks.push(t);
        });
      }
    } catch (e) { /* ignore */ }
    syncEmbedCaptions();
    el.bCc.hidden = !state.tracks.length;
    if (prefs.cc && state.tracks.some(t => t.lang === prefs.cc)) setCaptions(prefs.cc);
  }

  const YT_QUALITY_MAP = {
    'highres': 2160,
    'hd2160': 2160,
    'hd1440': 1440,
    'hd1080': 1080,
    'hd720': 720,
    'large': 480,
    'medium': 360,
    'small': 240,
    'tiny': 144,
  };
  const HEIGHT_TO_YT_QUALITY = {
    2160: 'hd2160',
    1440: 'hd1440',
    1080: 'hd1080',
    720: 'hd720',
    480: 'large',
    360: 'medium',
    240: 'small',
    144: 'tiny',
  };
  function setEmbedQuality(q, silent = false) {
    state.quality = q;
    prefs.quality = q;
    savePrefs();
    const cur = (embedPlayer && embedPlayer.getCurrentTime && embedPlayer.getCurrentTime()) || state.time || 0;
    const ytQ = q === 'auto' ? 'default' : (HEIGHT_TO_YT_QUALITY[+q] || 'default');
    if (q === 'auto') {
      state.height = 0;
      if (embedPlayer && typeof embedPlayer.setPlaybackQuality === 'function') embedPlayer.setPlaybackQuality('default');
    } else {
      state.height = +q;
      if (embedPlayer && typeof embedPlayer.setPlaybackQuality === 'function') embedPlayer.setPlaybackQuality(ytQ);
      if (embedPlayer && typeof embedPlayer.setPlaybackQualityRange === 'function') embedPlayer.setPlaybackQualityRange(ytQ, ytQ);
    }

    const iframe = document.getElementById('ytIframeHost');
    if (iframe && iframe.contentWindow) {
      try {
        iframe.contentWindow.postMessage(JSON.stringify({ event: 'command', func: 'setPlaybackQuality', args: [ytQ] }), '*');
        iframe.contentWindow.postMessage(JSON.stringify({ event: 'command', func: 'setPlaybackQualityRange', args: [ytQ, ytQ] }), '*');
      } catch (e) {}
    }

    if (!silent && q !== 'auto' && state.id && embedPlayer && typeof embedPlayer.loadVideoById === 'function') {
      try {
        embedPlayer.loadVideoById({ videoId: state.id, startSeconds: Math.floor(cur), suggestedQuality: ytQ });
      } catch (e) {}
    }

    if (!el.menu.hidden) renderMenu();

    if (!silent) {
      const label = q === 'auto' ? 'Quality: Auto' : (q >= 720 ? `Quality: ${q}p HD` : `Quality: ${q}p`);
      showHud(ICON.gear, label);
    }
  }

  /* ------------------------------------------------------------------ menus */
  let menuStack = [];
  const closeMenu = () => { el.menu.hidden = true; menuStack = []; ui.classList.remove('menu-open'); };
  function renderMenu() {
    const view = menuStack[menuStack.length - 1];
    if (!view) { closeMenu(); return; }
    const item = (label, value, attrs, on, arrow, slot) => `<button type="button" class="yt-mi${on ? ' on' : ''}" ${attrs}><span class="yt-mi-l">${on ? ICON.check : (slot ? '<i class="yt-ck"></i>' : '')}${label}</span>${value ? `<span class="yt-mi-v">${value}</span>` : ''}${arrow ? ICON.chev : ''}</button>`;
    let html = '';
    const head = t => `<button type="button" class="yt-mh" data-m="back">${ICON.chevl}<span>${t}</span></button>`;
    if (view === 'settings') {
      const qlabel = state.quality === 'auto' ? `Auto${state.height ? ` (${state.height}p)` : ''}` : `${state.quality}p`;
      html = item('Quality', qlabel, 'data-m="quality"', false, true) + item('Speed', prefs.rate === 1 ? 'Normal' : prefs.rate + '×', 'data-m="speed"', false, true) +
        item('Captions', state.ccLang ? (state.tracks.find(t => t.lang === state.ccLang) || {}).name || state.ccLang : 'Off', 'data-m="cc"', false, true);
    } else if (view === 'quality') {
      let hs = [];
      if (engine && engine.formats && engine.formats.length) {
        hs = engine.formats.map(f => f.height).filter((h, i, a) => a.indexOf(h) === i).sort((a, b) => b - a);
      } else if (state.manifest && state.manifest.video && state.manifest.video.length) {
        hs = state.manifest.video.map(v => v.height).filter((h, i, a) => a.indexOf(h) === i).sort((a, b) => b - a);
      } else if (state.engineType === 'embed') {
        const levels = (embedPlayer && embedPlayer.getAvailableQualityLevels && embedPlayer.getAvailableQualityLevels()) || [];
        const parsed = levels.map(l => YT_QUALITY_MAP[l]).filter(Boolean);
        hs = parsed.length ? parsed.filter((h, i, a) => a.indexOf(h) === i).sort((a, b) => b - a) : [1080, 720, 480, 360, 240, 144];
      }
      if (!hs.length) hs = [1080, 720, 480, 360, 240, 144];
      html = head('Quality') + item('Auto', state.quality === 'auto' && state.height ? `${state.height}p` : '', 'data-q="auto"', state.quality === 'auto', false, true) +
        hs.map(h => item(`${h}p${h >= 720 ? ' <b class="yt-hd">HD</b>' : ''}`, '', `data-q="${h}"`, String(state.quality) === String(h), false, true)).join('');
    } else if (view === 'speed') {
      html = head('Speed') + [0.5, 0.75, 1, 1.25, 1.5, 1.75, 2].map(r => item(r === 1 ? 'Normal' : r + '×', '', `data-r="${r}"`, prefs.rate === r, false, true)).join('');
    } else if (view === 'cc') {
      html = head('Captions') + item('Off', '', 'data-c=""', !state.ccLang, false, true) +
        (state.tracks.map(t => item(esc(t.name) + (t.auto ? ' <small>auto</small>' : ''), '', `data-c="${esc(t.lang)}"`, state.ccLang === t.lang, false, true)).join('') || '<p class="yt-mnone">No captions for this video.</p>');
    }
    el.menu.innerHTML = html;
    el.menu.hidden = false; ui.classList.add('menu-open');
  }
  function openMenu(name) { menuStack = [name]; renderMenu(); }
  el.menu.addEventListener('click', e => {
    e.stopPropagation();
    const b = e.target.closest('button');
    if (!b) return;
    const d = b.dataset;
    if (d.m === 'back') { menuStack.pop(); renderMenu(); }
    else if (d.m) { menuStack.push(d.m); renderMenu(); }
    else if (d.q !== undefined) {
      if (engine) {
        state.quality = d.q; prefs.quality = d.q; savePrefs(); engine.setQuality(d.q);
        const label = d.q === 'auto' ? 'Quality: Auto' : (d.q >= 720 ? `Quality: ${d.q}p HD` : `Quality: ${d.q}p`);
        showHud(ICON.gear, label);
      } else if (state.engineType === 'native' && state.manifest && state.manifest.video) {
        state.quality = d.q; prefs.quality = d.q; savePrefs();
        const v = (d.q === 'auto')
          ? state.manifest.video[state.manifest.video.length - 1]
          : (state.manifest.video.find(x => String(x.height) === String(d.q)) || state.manifest.video[0]);
        if (v) {
          const t = video.currentTime;
          const wasPlaying = !video.paused;
          video.src = urlFor('mediaUrl', state.id).replace('/0/', `/${v.itag}/`);
          video.currentTime = t;
          state.height = v.height;
          if (wasPlaying) video.play().catch(() => {});
        }
        const label = d.q === 'auto' ? 'Quality: Auto' : (d.q >= 720 ? `Quality: ${d.q}p HD` : `Quality: ${d.q}p`);
        showHud(ICON.gear, label);
      } else if (state.engineType === 'embed' && embedPlayer) {
        setEmbedQuality(d.q, false);
      }
      closeMenu();
    }
    else if (d.r !== undefined) {
      prefs.rate = +d.r;
      video.playbackRate = prefs.rate;
      if (state.engineType === 'embed' && embedPlayer && embedPlayer.setPlaybackRate) embedPlayer.setPlaybackRate(prefs.rate);
      savePrefs();
      showHud(ICON.gear, `Speed: ${prefs.rate === 1 ? 'Normal' : prefs.rate + '×'}`);
      closeMenu();
    }
    else if (d.c !== undefined) { setCaptions(d.c); closeMenu(); }
  });
  el.menu.addEventListener('pointerdown', e => e.stopPropagation());
  document.addEventListener('pointerdown', e => { if (!el.menu.hidden && !el.menu.contains(e.target) && !e.target.closest('[data-a=settings],[data-a=cc]')) closeMenu(); });

  const fsActive = () => document.fullscreenElement === host;
  async function fullscreen() {
    try {
      if (fsActive()) {
        await document.exitFullscreen();
      } else {
        if (host.requestFullscreen) await host.requestFullscreen();
        else if (host.webkitRequestFullscreen) await host.webkitRequestFullscreen();
        else if (video.webkitEnterFullscreen) video.webkitEnterFullscreen();
      }
    } catch (e) { /* not allowed */ }
  }
  document.addEventListener('fullscreenchange', () => { el.bFs.innerHTML = fsActive() ? ICON.fsx : ICON.fs; host.classList.toggle('fs', fsActive()); place(false); });
  document.addEventListener('webkitfullscreenchange', () => { el.bFs.innerHTML = fsActive() ? ICON.fsx : ICON.fs; host.classList.toggle('fs', fsActive()); place(false); });

  async function openDocumentPiP() {
    try {
      if (window.documentPictureInPicture && typeof window.documentPictureInPicture.requestWindow === 'function') {
        const pipWin = await window.documentPictureInPicture.requestWindow({ width: 480, height: 270 });
        [...document.styleSheets].forEach(s => {
          try {
            const rules = [...s.cssRules].map(r => r.cssText).join('');
            const st = document.createElement('style');
            st.textContent = rules;
            pipWin.document.head.appendChild(st);
          } catch (e) {
            const link = document.createElement('link');
            link.rel = 'stylesheet';
            link.href = s.href;
            pipWin.document.head.appendChild(link);
          }
        });
        pipWin.document.body.appendChild(host);
        pipWin.addEventListener('pagehide', () => {
          document.body.appendChild(host);
          place(false);
        });
        return;
      }
    } catch (e) {}
    showHud(ICON.pip, 'Docked mini player');
    api.minimize();
  }

  const ctrlBar = frame.querySelector('.yt-ctrl');
  if (ctrlBar) {
    ctrlBar.addEventListener('click', e => e.stopPropagation());
    ctrlBar.addEventListener('dblclick', e => e.stopPropagation());
    ctrlBar.addEventListener('pointerdown', e => e.stopPropagation());
    ctrlBar.addEventListener('pointerup', e => e.stopPropagation());
  }

  frame.querySelector('.yt-row').addEventListener('click', e => {
    e.stopPropagation();
    const b = e.target.closest('[data-a]');
    if (!b) return;
    const a = b.dataset.a;
    if (a === 'play') toggle();
    else if (a === 'prev') emit('prev');
    else if (a === 'next') emit('next');
    else if (a === 'mute') {
      applyVolume(prefs.vol || 1, !prefs.muted, true);
    }
    else if (a === 'cc') {
      if (state.ccLang) {
        setCaptions('');
      } else if (state.tracks.length) {
        const preferred = (prefs.cc && state.tracks.find(t => t.lang === prefs.cc)) || state.tracks[0];
        setCaptions(preferred ? preferred.lang : 'en');
      }
    }
    else if (a === 'settings') { if (el.menu.hidden || menuStack[0] !== 'settings') openMenu('settings'); else closeMenu(); }
    else if (a === 'pip') {
      if (document.pictureInPictureElement) {
        document.exitPictureInPicture().catch(() => {});
      } else if (window.documentPictureInPicture && typeof window.documentPictureInPicture.requestWindow === 'function') {
        openDocumentPiP();
      } else if (video && video.requestPictureInPicture && state.engineType !== 'embed') {
        video.requestPictureInPicture().catch(() => {});
      } else {
        showHud(ICON.pip, 'Docked mini player');
        api.minimize();
      }
    }
    else if (a === 'fs') fullscreen();
  });
  q('.yt-bigplay').addEventListener('click', e => { e.stopPropagation(); toggle(); });

  /* Touch & drag gestures: left side = brightness, right side = volume */
  let clickTimer = 0;
  let clickCount = 0;
  let gestureActive = false;
  let gestureType = null;
  let gestureStartX = 0;
  let gestureStartY = 0;
  let gestureStartVal = 0;
  let gestureMoved = false;
  let gestureJustEnded = false;

  ui.addEventListener('pointerdown', e => {
    if (state.mode === 'mini') return;
    if (e.target.closest('.yt-ctrl, .yt-menu, .yt-mini-ui, .yt-bigplay, .yt-err, .yt-seek, .yt-hud')) return;
    const rect = ui.getBoundingClientRect();
    if (!rect.width || !rect.height) return;
    gestureStartX = e.clientX;
    gestureStartY = e.clientY;
    gestureMoved = false;
    gestureActive = true;
    const x = e.clientX - rect.left;
    if (x < rect.width / 2) {
      gestureType = 'brightness';
      gestureStartVal = currentBrightness;
    } else {
      gestureType = 'volume';
      gestureStartVal = prefs.muted ? 0 : prefs.vol;
    }
  });

  ui.addEventListener('pointermove', e => {
    if (!gestureActive) return;
    const dx = e.clientX - gestureStartX;
    const dy = gestureStartY - e.clientY; // upward drag is positive
    if (!gestureMoved) {
      if (Math.abs(dy) > 16 && Math.abs(dy) > Math.abs(dx)) {
        gestureMoved = true;
        try { ui.setPointerCapture(e.pointerId); } catch (_) {}
      }
    }
    if (gestureMoved) {
      try { e.preventDefault(); } catch (_) {}
      const delta = dy / 220; // 220px drag = full 100% swing
      if (gestureType === 'brightness') {
        setBrightness(gestureStartVal + delta * 1.0);
      } else if (gestureType === 'volume') {
        setGestureVolume(gestureStartVal + delta);
      }
    }
  });

  const endGesture = e => {
    if (gestureMoved) {
      gestureJustEnded = true;
      setTimeout(() => { gestureJustEnded = false; }, 220);
    }
    try { if (e && e.pointerId) ui.releasePointerCapture(e.pointerId); } catch (_) {}
    gestureActive = false;
    gestureType = null;
    gestureMoved = false;
  };
  ui.addEventListener('pointerup', endGesture);
  ui.addEventListener('pointercancel', endGesture);

  /* Single tap to toggle controls or play/pause; double tap left/right to seek -10s/+10s; double tap center for fullscreen */
  ui.addEventListener('click', e => {
    if (gestureJustEnded || gestureMoved) return;
    if (state.mode === 'mini') {
      if (!e.target.closest('#ytToggle, #ytClose, .yt-cb, .yt-vol, .yt-ib')) expand();
      return;
    }
    if (e.target.closest('.yt-ctrl, .yt-menu, .yt-mini-ui, .yt-bigplay, .yt-err, .yt-seek, .yt-hud')) return;
    if (!el.menu.hidden) { closeMenu(); return; }

    const rect = ui.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const width = rect.width || 1;
    const relX = x / width;

    clickCount++;
    if (clickCount === 1) {
      clearTimeout(clickTimer);
      clickTimer = setTimeout(() => {
        clickCount = 0;
        if (!ui.classList.contains('show') && state.playing) {
          poke();
        } else {
          toggle();
          poke();
        }
      }, 250);
    } else if (clickCount >= 2) {
      clearTimeout(clickTimer);
      clickCount = 0;
      const cur = (state.engineType === 'embed' && embedPlayer && embedPlayer.getCurrentTime ? embedPlayer.getCurrentTime() : video.currentTime) || state.time || 0;
      if (relX < 0.35) {
        seekTo(cur - 10);
        showHud(ICON.back, '-10s');
        poke();
      } else if (relX > 0.65) {
        seekTo(cur + 10);
        showHud(ICON.fwd, '+10s');
        poke();
      } else {
        fullscreen();
      }
    }
  });

  ui.addEventListener('dblclick', e => {
    if (e.target.closest('.yt-ctrl, .yt-menu, .yt-mini-ui, .yt-bigplay, .yt-err, .yt-seek, .yt-hud')) return;
    clearTimeout(clickTimer);
    clickCount = 0;
    fullscreen();
  });

  /* controls fade out while playing and the pointer is still */
  let hideT = 0;
  const poke = () => { ui.classList.add('show'); clearTimeout(hideT); hideT = setTimeout(() => { if (state.playing && el.menu.hidden && !scrubbing) ui.classList.remove('show'); }, 2600); };
  ui.addEventListener('pointermove', poke); ui.addEventListener('pointerdown', poke);
  ui.addEventListener('pointerleave', () => { if (state.playing && el.menu.hidden) ui.classList.remove('show'); });
  video.addEventListener('pause', () => { ui.classList.add('show'); clearTimeout(hideT); });

  /* ------------------------------------------------------------------ engine */
  function teardown() {
    state.tok++;
    endingTriggered = false;
    stopEmbedTimer();
    if (embedPlayer) {
      try { embedPlayer.destroy(); } catch (e) {}
      embedPlayer = null;
    }
    if (engine) {
      engine.destroy();
      engine = null;
    }
    if (el.embed) {
      el.embed.innerHTML = '';
      el.embed.classList.remove('ready');
      el.embed.hidden = true;
    }
    host.classList.remove('embed');
    ui.hidden = false;
    ui.style.display = '';
    video.hidden = false;
    video.muted = true;
    video.pause();
    video.removeAttribute('src');
    try { video.load(); } catch (e) {}
    state.engineType = 'mse';
    state.manifest = null; state.ready = false; state.height = 0; state.cues = []; state.tracks = [];
    closeMenu(); hideError(); el.cc.hidden = true; setWaiting(false);
  }

  function fallbackIframe(id, start, autoplay) {
    if (!el.embed) return;
    if (engine) {
      try { engine.destroy(); } catch (e) {}
      engine = null;
    }
    el.embed.innerHTML = '';
    el.embed.classList.remove('ready');
    el.embed.hidden = false;
    video.pause();
    video.muted = true;
    video.removeAttribute('src');
    try { video.load(); } catch (e) {}
    video.hidden = true;
    const iframe = document.createElement('iframe');
    const origin = encodeURIComponent(window.location.origin || '');
    host.classList.add('embed');
    const startSec = Math.floor(start || 0);
    const vqParam = (prefs.quality && prefs.quality !== 'auto' && prefs.quality !== '144') ? (HEIGHT_TO_YT_QUALITY[+prefs.quality] || 'hd1080') : 'hd1080';
    const ccParam = prefs.cc ? `&cc_load_policy=1&hl=${encodeURIComponent(prefs.cc)}` : '';
    iframe.src = `https://www.youtube.com/embed/${encodeURIComponent(id)}?enablejsapi=1&origin=${origin}&controls=0&modestbranding=1&rel=0&iv_load_policy=3&disablekb=1&fs=0&playsinline=1&vq=${vqParam}&widget_referrer=${encodeURIComponent(window.location.href)}${startSec > 0 ? '&start=' + startSec : ''}${ccParam}`;
    iframe.referrerPolicy = 'strict-origin-when-cross-origin';
    iframe.allow = 'accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share';
    iframe.allowFullscreen = true;
    iframe.style.position = 'absolute';
    iframe.style.top = '-50px';
    iframe.style.left = '0';
    iframe.style.width = '100%';
    iframe.style.height = 'calc(100% + 50px)';
    iframe.style.bottom = '0';
    iframe.style.border = '0';
    iframe.style.pointerEvents = 'none';
    el.embed.appendChild(iframe);
    ui.hidden = false;
    ui.style.display = '';
    setWaiting(false);
    hideError();
    state.ready = true;
    setPlaying(!!autoplay);
    setTimeout(() => { if (el.embed) el.embed.classList.add('ready'); }, 500);
  }

  function startEmbedEngine(id, start, autoplay) {
    const tok = state.tok;
    state.engineType = 'embed';
    host.classList.add('embed');
    if (engine) {
      try { engine.destroy(); } catch (e) {}
      engine = null;
    }
    video.pause();
    video.muted = true;
    video.removeAttribute('src');
    try { video.load(); } catch (e) {}
    video.hidden = true;
    if (el.embed) {
      el.embed.hidden = false;
      el.embed.innerHTML = '';
      el.embed.classList.remove('ready');
    }
    ui.hidden = false;
    ui.style.display = '';
    setWaiting(true);
    ui.dataset.state = 'loading';

    ensureYTApi(() => {
      if (tok !== state.tok) return;
      if (el.embed) el.embed.innerHTML = '';
      const iframe = document.createElement('iframe');
      iframe.id = 'ytIframeHost';
      iframe.referrerPolicy = 'strict-origin-when-cross-origin';
      iframe.allow = 'accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share';
      iframe.style.position = 'absolute';
      iframe.style.top = '-50px';
      iframe.style.left = '0';
      iframe.style.width = '100%';
      iframe.style.height = 'calc(100% + 50px)';
      iframe.style.bottom = '0';
      iframe.style.border = '0';
      iframe.style.pointerEvents = 'none';

      const origin = encodeURIComponent(window.location.origin || '');
      const startSec = Math.floor(start || 0);
      const vqParam = (prefs.quality && prefs.quality !== 'auto' && prefs.quality !== '144') ? (HEIGHT_TO_YT_QUALITY[+prefs.quality] || 'hd1080') : 'hd1080';
      const ccParam = prefs.cc ? `&cc_load_policy=1&hl=${encodeURIComponent(prefs.cc)}` : '';
      iframe.src = `https://www.youtube.com/embed/${encodeURIComponent(id)}?enablejsapi=1&origin=${origin}&controls=0&modestbranding=1&rel=0&iv_load_policy=3&disablekb=1&fs=0&playsinline=1&vq=${vqParam}&widget_referrer=${encodeURIComponent(window.location.href)}${startSec > 0 ? '&start=' + startSec : ''}${ccParam}`;

      if (el.embed) el.embed.appendChild(iframe);

      try {
        embedPlayer = new YT.Player(iframe, {
          events: {
            onReady: () => {
              if (tok !== state.tok) return;
              state.ready = true;
              if (el.embed) el.embed.classList.add('ready');
              if (!autoplay) {
                setWaiting(false);
                ui.dataset.state = 'paused';
              }
              state.duration = (embedPlayer.getDuration && embedPlayer.getDuration()) || state.duration || 0;
              if (embedPlayer.setPlaybackRate) embedPlayer.setPlaybackRate(prefs.rate);
              applyVolume(prefs.vol, prefs.muted, false);
              if (start > 0 && embedPlayer.seekTo) embedPlayer.seekTo(start, true);
              if (prefs.quality && prefs.quality !== 'auto' && prefs.quality !== '144') {
                setEmbedQuality(prefs.quality, true);
              } else {
                prefs.quality = 'auto';
                savePrefs();
                const qLevel = (embedPlayer.getPlaybackQuality && embedPlayer.getPlaybackQuality()) || '';
                state.height = YT_QUALITY_MAP[qLevel] || state.height || 1080;
              }
              if (embedPlayer.loadModule) {
                try { embedPlayer.loadModule('captions'); } catch (e) {}
              }
              syncEmbedCaptions();
              if (autoplay && embedPlayer.playVideo) embedPlayer.playVideo();
              paint();
            },
            onPlaybackQualityChange: ev => {
              if (tok !== state.tok) return;
              const h = YT_QUALITY_MAP[ev.data];
              if (h) {
                state.height = h;
                if (!el.menu.hidden) renderMenu();
              }
            },
            onStateChange: ev => {
              if (tok !== state.tok) return;
              if (ev.data === 1) { // playing
                hideError();
                setPlaying(true);
                setWaiting(false);
                state.ready = true;
                if (el.embed) el.embed.classList.add('ready');
                const qLevel = (embedPlayer.getPlaybackQuality && embedPlayer.getPlaybackQuality()) || '';
                if (YT_QUALITY_MAP[qLevel]) state.height = YT_QUALITY_MAP[qLevel];
                syncEmbedCaptions();
                startEmbedTimer();
              } else if (ev.data === 2) { // paused
                setPlaying(false);
                stopEmbedTimer();
              } else if (ev.data === 3) { // buffering
                if (!state.playing) setWaiting(true);
              } else if (ev.data === 0) { // ended
                setPlaying(false);
                stopEmbedTimer();
                ui.dataset.state = 'ended';
                emit('ended');
              } else if (ev.data === 5) { // cued
                if (autoplay && embedPlayer && embedPlayer.playVideo) embedPlayer.playVideo();
              }
            },
            onError: ev => {
              if (tok !== state.tok) return;
              if (ev.data === 101 || ev.data === 150) {
                showError("This video can't be played here", 'Playback is restricted on this video by YouTube.');
              } else if (ev.data === 100 || ev.data === 2) {
                showError('Video not found', 'This video may be private or removed.');
              } else {
                showError("This video can't be played right now", 'Please try another video.');
              }
            }
          }
        });
      } catch (err) {
        if (tok === state.tok) fallbackIframe(id, start, autoplay);
      }
      loadCaptionTracks(id);
    }, () => {
      if (tok === state.tok && !embedPlayer) {
        fallbackIframe(id, start, autoplay);
      }
    });
  }

  function startEmbedTimer() {
    stopEmbedTimer();
    embedTimer = setInterval(() => {
      if (state.engineType !== 'embed' || !embedPlayer || !embedPlayer.getCurrentTime) return;
      paint();
      if (Date.now() - lastSave > 2000) { lastSave = Date.now(); save(); }
    }, 250);
  }
  function stopEmbedTimer() {
    if (embedTimer) { clearInterval(embedTimer); embedTimer = 0; }
  }

  const manifestCache = new Map();
  async function preloadManifest(id) {
    if (!id || manifestCache.has(id)) return;
    try {
      const r = await fetch(urlFor('streamUrl', id), { credentials: 'same-origin' });
      if (r.ok) {
        const d = await r.json();
        if (d && d.ok && d.fallback !== 'embed') {
          if (manifestCache.size > 8) manifestCache.clear();
          manifestCache.set(id, d);
        }
      }
    } catch (e) { /* ignore */ }
  }

  async function startEngine(id, start, autoplay) {
    endingTriggered = false;
    const tok = ++state.tok;
    if (host.dataset.mode === 'embed') {
      startEmbedEngine(id, start, autoplay);
      return;
    }
    hideError(); setWaiting(true); ui.dataset.state = 'loading';
    el.buf.style.transform = el.played.style.transform = 'scaleX(0)';
    let mf = manifestCache.get(id);
    if (mf) {
      manifestCache.delete(id);
    } else {
      try {
        const ctl = new AbortController(), timer = setTimeout(() => ctl.abort(), 8000);
        const r = await fetch(urlFor('streamUrl', id), { credentials: 'same-origin', signal: ctl.signal });
        clearTimeout(timer);
        if (r.ok) mf = await r.json();
      } catch (e) {
        if (tok === state.tok) startEmbedEngine(id, start, autoplay);
        return;
      }
    }
    if (tok !== state.tok) return;

    if (!mf || !mf.ok || mf.fallback === 'embed') {
      startEmbedEngine(id, start, autoplay);
      return;
    }

    state.manifest = mf;
    state.duration = mf.duration || 0;
    video.playbackRate = prefs.rate;

    // Progressive muxed MP4 stream (plays natively in <video>)
    if (mf.is_muxed) {
      state.engineType = 'native';
      const itag = mf.progressive_itag || (mf.video && mf.video[0] && mf.video[0].itag) || '18';
      const mediaSrc = urlFor('mediaUrl', id).replace('/0/', `/${itag}/`);
      video.hidden = false;
      if (el.embed) {
        el.embed.hidden = true;
        el.embed.innerHTML = '';
      }
      host.classList.remove('embed');
      video.src = mediaSrc;
      if (start > 0) video.currentTime = start;
      state.height = (mf.video && mf.video[0] && mf.video[0].height) || 360;
      applyVolume(prefs.vol, prefs.muted, false);
      if (autoplay) {
        video.play().catch(() => { setPlaying(false); ui.dataset.state = 'paused'; state.ready = true; setWaiting(false); });
      } else {
        setPlaying(false); ui.dataset.state = 'paused'; state.ready = true; setWaiting(false);
      }
      loadCaptionTracks(id);
      return;
    }

    // Adaptive DASH MSE stream
    if (!window.YTEngine || !window.YTEngine.supported(mf)) {
      startEmbedEngine(id, start, autoplay);
      return;
    }

    state.engineType = 'mse';
    video.hidden = false;
    if (el.embed) {
      el.embed.hidden = true;
      el.embed.innerHTML = '';
    }
    host.classList.remove('embed');
    ui.hidden = false;
    ui.style.display = '';

    engine = new window.YTEngine(video, {
      mediaUrl: itag => urlFor('mediaUrl', id).replace(/\/0(\?|\/|$)/, `/${itag}$1`),
      onQuality: s => {
        state.height = s.height;
        state.quality = s.auto ? 'auto' : String(s.height);
        if (!el.menu.hidden) renderMenu();
      },
      onError: msg => { if (tok === state.tok) startEmbedEngine(id, video.currentTime || start, true); },
      onWaiting: setWaiting,
      maxHeight: () => Math.max(360, Math.round((host.clientHeight || 360) * (window.devicePixelRatio || 1))),
    });
    try {
      await engine.load(mf, {
        quality: prefs.quality || 'auto',
        start,
        targetHeight: Math.max(480, Math.min(1080, Math.round((host.clientHeight || 360) * (window.devicePixelRatio || 1))))
      });
    } catch (e) {
      if (tok === state.tok) startEmbedEngine(id, video.currentTime || start, true);
      return;
    }
    if (tok !== state.tok) return;

    applyVolume(prefs.vol, prefs.muted, false);
    video.playbackRate = prefs.rate;

    if (autoplay) {
      video.play().catch(() => { setPlaying(false); ui.dataset.state = 'paused'; state.ready = true; setWaiting(false); });
    } else {
      setPlaying(false); ui.dataset.state = 'paused'; state.ready = true; setWaiting(false);
    }
    loadCaptionTracks(id);

    // Auto-preload the next item in the queue
    const q = state.meta.related || [];
    const idx = q.findIndex(v => v && v.id === id);
    if (idx >= 0 && idx + 1 < q.length && q[idx + 1] && q[idx + 1].id) {
      setTimeout(() => preloadManifest(q[idx + 1].id), 800);
    }
  }

  /* ------------------------------------------------------------------ public API */
  const api = {
    state,
    on(name, fn) { (listeners[name] = listeners[name] || []).push(fn); return () => { listeners[name] = (listeners[name] || []).filter(f => f !== fn); }; },
    /** Play a video. With a stage the player sits over it (watch mode); without, it docks as the mini player. */
    open(id, meta = {}, opts = {}) {
      const first = state.mode === 'none';
      const reuse = state.id === id && ui.dataset.state !== 'error' && (engine || (embedPlayer && state.ready));
      const prevPlaylist = state.meta && state.meta.playlist;
      const prevList = state.meta && state.meta.list;
      const prevRelated = state.meta && state.meta.related;
      state.id = id;
      state.meta = Object.assign({}, reuse ? state.meta : {}, meta);
      if (meta && meta.list && prevPlaylist && meta.list === prevPlaylist.id) {
        state.meta.playlist = prevPlaylist;
        state.meta.list = prevPlaylist.id;
        if (prevRelated && (!state.meta.related || !state.meta.related.length)) {
          state.meta.related = prevRelated;
        }
      } else if (!meta || !meta.list) {
        delete state.meta.playlist;
        delete state.meta.list;
        delete state.meta.related;
      }
      state.stage = opts.stage || null;
      state.mode = state.stage ? 'watch' : 'mini';
      host.hidden = false;
      host.classList.toggle('pop', first);
      el.title.textContent = el.vtitle.textContent = state.meta.title || 'Video';
      if (!reuse) { teardown(); state.time = opts.start || 0; startEngine(id, opts.start || 0, opts.autoplay !== false); }
      place(false); track(900); save();
      return !!reuse;
    },
    update(meta) {
      state.meta = Object.assign({}, state.meta, meta);
      if (meta.playlist === null) delete state.meta.playlist;
      if (meta.list === null) delete state.meta.list;
      if (meta.related === null) delete state.meta.related;
      if (meta.title) el.title.textContent = el.vtitle.textContent = meta.title;
      save();
    },
    attach(stage) { if (state.mode === 'none') return; state.stage = stage; state.mode = 'watch'; place(false); track(900); },
    minimize() { if (state.mode === 'none') return; if (fsActive()) document.exitFullscreen(); state.mode = 'mini'; closeMenu(); place(true); save(); },
    close() {
      if (fsActive()) document.exitFullscreen();
      teardown();
      state.mode = 'none'; state.id = null; state.time = 0;
      cancelAnimationFrame(tracking);
      host.classList.add('gone');
      setTimeout(() => { host.hidden = true; host.classList.remove('gone'); }, reduce ? 0 : 200);
      try { sessionStorage.removeItem(KEY); } catch (e) { /* ignore */ }
      emit('closed');
    },
    toggle,
    seek(t) { seekTo(t); },
    get embed() { return state.engineType === 'embed'; },
    refresh() { place(false); },
    track,
    get video() { return video; },
    get active() { return state.mode !== 'none'; },
    get autoplay() { return prefs.autoplay !== false; },
    set autoplay(on) { prefs.autoplay = !!on; savePrefs(); },
    preload(id) { preloadManifest(id); },
  };
  window.StudyPlayer = api;

  /* ------------------------------------------------------------------ keyboard (watch view and full screen only) */
  addEventListener('keydown', e => {
    if (state.mode === 'none' || e.ctrlKey || e.metaKey || e.altKey) return;
    const t = e.target;
    if (t && (/^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName) && t !== el.volr || t.isContentEditable)) return;
    if (!(state.mode === 'watch' || fsActive())) return;
    const k = e.key;
    const vol = d => {
      const cur = prefs.muted ? 0 : prefs.vol;
      applyVolume(cur + d, false, true);
      poke();
    };
    const curTime = () => (state.engineType === 'embed' && embedPlayer && embedPlayer.getCurrentTime ? (embedPlayer.getCurrentTime() || state.time || 0) : (video.currentTime || state.time || 0));
    const totalDur = () => (state.engineType === 'embed' && embedPlayer && embedPlayer.getDuration ? (embedPlayer.getDuration() || state.duration || 0) : (video.duration || state.duration || 0));

    if (k === ' ' || k === 'k' || k === 'K') { if (t && t.closest && t.closest('button, a, [role=slider]') && k === ' ') return; e.preventDefault(); toggle(); poke(); }
    else if (k === 'ArrowLeft') { e.preventDefault(); seekTo(curTime() - 5); poke(); }
    else if (k === 'ArrowRight') { e.preventDefault(); seekTo(curTime() + 5); poke(); }
    else if (k === 'P' && e.shiftKey) { emit('prev'); }
    else if (k === 'N' && e.shiftKey) { emit('next'); }
    else if (k === 'j' || k === 'J') { seekTo(curTime() - 10); poke(); }
    else if (k === 'l' || k === 'L') { seekTo(curTime() + 10); poke(); }
    else if (k === 'ArrowUp') { e.preventDefault(); vol(0.05); }
    else if (k === 'ArrowDown') { e.preventDefault(); vol(-0.05); }
    else if (k === 'm' || k === 'M') {
      applyVolume(prefs.vol || 1, !prefs.muted, true);
      poke();
    }
    else if (k === 'f' || k === 'F') { fullscreen(); }
    else if (k === 'c' || k === 'C') { if (state.tracks.length) setCaptions(state.ccLang ? '' : (prefs.cc && state.tracks.some(x => x.lang === prefs.cc) ? prefs.cc : state.tracks[0].lang)); }
    else if (k === '<' || k === '>') { const rs = [0.5, 0.75, 1, 1.25, 1.5, 1.75, 2]; const i = rs.indexOf(prefs.rate); const n = rs[Math.max(0, Math.min(rs.length - 1, i + (k === '>' ? 1 : -1)))]; prefs.rate = n; video.playbackRate = n; if (state.engineType === 'embed' && embedPlayer && embedPlayer.setPlaybackRate) embedPlayer.setPlaybackRate(n); savePrefs(); poke(); }
    else if (k === 'Home') { seekTo(0); }
    else if (k === 'End') { seekTo(totalDur()); }
    else if (/^[0-9]$/.test(k)) { seekTo(totalDur() * (+k / 10)); poke(); }
  });

  /* ------------------------------------------------------------------ mini player controls */
  el.toggle.addEventListener('click', toggle);
  $('ytClose').addEventListener('click', api.close);
  const expand = () => {
    if (!state.id) return;
    if (document.getElementById('yt')) { emit('expand'); return; }               // on the Videos page: yt.js re-opens the watch view
    save();
    const t = Math.floor(state.time || 0);
    const to = `${host.dataset.videosUrl}?v=${encodeURIComponent(state.id)}${t > 1 ? '&t=' + t : ''}`;
    if (window.PJAX) window.PJAX.go(to); else location.href = to;
  };
  $('ytExpand').addEventListener('click', expand);
  el.title.addEventListener('click', expand);
  $('ytErrNext').addEventListener('click', () => emit('skip'));
  $('ytErrRetry').addEventListener('click', () => { if (state.id) { const id = state.id, t = state.time; teardown(); startEngine(id, t, true); } });
  el.errNext.hidden = true;
  api.showNext = on => { el.errNext.hidden = !on; };

  /* ------------------------------------------------------------------ resume after moving to another page */
  const saved = read(sessionStorage, KEY, null);
  if (saved && saved.id) {
    const elapsed = saved.playing ? Math.max(0, (Date.now() - saved.ts) / 1000) : 0;
    state.id = saved.id; state.meta = saved.meta || {}; state.mode = 'mini'; state.stage = null;
    host.hidden = false; host.classList.add('pop');
    el.title.textContent = el.vtitle.textContent = state.meta.title || 'Video';
    place(false);
    state.time = (saved.time || 0) + Math.min(elapsed, 8);
    startEngine(saved.id, state.time, !!saved.playing);
    requestAnimationFrame(() => emit('restored'));
  }
})();
