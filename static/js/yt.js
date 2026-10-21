/* Videos page: watch view over the shared player (player.js), in-page search, up next, history, Lexi about the video. */
(() => {
  'use strict';
  const root = document.getElementById('yt');
  const SP = window.StudyPlayer;
  if (!root || !SP) return;
  const $ = id => document.getElementById(id);
  const esc = s => String(s == null ? '' : s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const reduce = matchMedia('(prefers-reduced-motion: reduce)').matches;
  const PLAY = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M9.2 7v10l8.4-5z" fill="currentColor" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/></svg>';

  const el = {
    watch: $('ytWatch'), stage: $('ytStage'), results: $('ytResults'), form: $('ytForm'), input: $('ytSearch'), clear: $('ytClear'), chips: $('ytChips'),
    title: $('ytTitle'), channel: $('ytChannel'), subs: $('ytSubs'), avatar: $('ytAvatar'), meta: $('ytMeta'),
    desc: $('ytDescText'), more: $('ytMore'), descBox: $('ytDesc'), next: $('ytNext'), histList: $('ytHistList'), auto: $('ytAuto'),
    share: $('ytShare'), open: $('ytOpen'), tabNext: $('ytTabNext'), tabHist: $('ytTabHist'), autoWrap: $('ytAutoWrap'),
    lexi: $('ytLexi'), lexiBtn: $('ytLexiBtn'), lexiLog: $('ytLexiLog'), lexiForm: $('ytLexiForm'), lexiInput: $('ytLexiInput'), lexiNote: $('ytLexiNote'),
  };
  const S = SP.state;
  const undo = [];                                           // everything this page attached outside its own markup
  const listen = (t, ev, fn, o) => { t.addEventListener(ev, fn, o); undo.push(() => t.removeEventListener(ev, fn, o)); };
  window.PageCleanup = window.PageCleanup || [];
  window.PageCleanup.push(() => { undo.splice(0).forEach(f => f()); });
  const spOn = (name, fn) => { undo.push(SP.on(name, fn)); };
  const myPath = location.pathname;
  const baseTitle = document.title;
  let reqId = 0, lexiTurns = [], lexiBusy = false;

  const watchUrl = id => root.dataset.watchUrl.replace('XXXXXXXXXXX', encodeURIComponent(id));
  const withV = id => { const u = new URL(location.href); u.searchParams.set('v', id); u.searchParams.delete('t'); return u.pathname + u.search; };
  const listUrl = () => { const u = new URL(location.href); u.searchParams.delete('v'); u.searchParams.delete('t'); u.searchParams.delete('_part'); return u.pathname + u.search; };
  const inWatch = () => !el.watch.hidden && S.mode === 'watch';

  /* ------------------------------------------------------------------ watch view */
  let listScroll = 0;
  const jump = y => { const h = document.documentElement; const b = h.style.scrollBehavior; h.style.scrollBehavior = 'auto'; scrollTo(0, y); h.style.scrollBehavior = b; };
  function showWatch() {
    if (!root.classList.contains('watching')) { listScroll = scrollY; root.classList.add('watching'); jump(0); }
    el.watch.hidden = false;
    el.watch.classList.remove('out');
    void el.watch.offsetWidth;
    el.watch.classList.add('in');
  }
  function hideWatch() {
    if (el.watch.hidden) return;
    el.watch.classList.remove('in'); el.watch.classList.add('out');
    setTimeout(() => {
      if (S.mode === 'watch') return;
      el.watch.hidden = true; el.watch.classList.remove('out');
      if (root.classList.contains('watching')) { root.classList.remove('watching'); jump(listScroll); }   // back to where the list was
    }, reduce ? 0 : 200);
  }

  const trail = { back: [], fwd: [] };        // videos watched this session, for Previous / Next
  const snapshot = () => (S.id ? { id: S.id, meta: Object.assign({}, S.meta) } : null);
  function openVideo(id, meta, opts = {}) {
    const switching = inWatch();
    const prev = snapshot();
    if (!switching) { trail.back = []; trail.fwd = []; }
    else if (prev && prev.id !== id) {
      if (opts.nav === 'prev') trail.fwd.push(prev);
      else { trail.back.push(prev); if (opts.nav !== 'next') trail.fwd = []; }
    }
    showWatch();
    const same = SP.open(id, meta || {}, { stage: el.stage, start: opts.start || 0 });
    document.title = (S.meta.title ? S.meta.title + ' · ' : '') + baseTitle;
    if (!same || opts.refresh) { resetLexi(); fillHeader(S.meta); fetchDetails(id); }
    if (opts.push !== false) {
      // Back should leave the watch page, not walk through every video played: switching videos rewrites the entry.
      if (switching && history.state && history.state.kind === 'watch') history.replaceState({ kind: 'watch', v: id, pushed: !!history.state.pushed }, '', withV(id));
      else history.pushState({ kind: 'watch', v: id, pushed: true }, '', withV(id));
    }
    saveHistory(S.meta, id);
  }
  function minimize(fromHistory) {
    if (!inWatch()) return;
    SP.minimize();
    hideWatch();
    document.title = baseTitle;
    if (!fromHistory && history.state && history.state.kind === 'watch') history.replaceState({ kind: 'list' }, '', listUrl());
  }
  function expand() {
    if (!S.id) return;
    showWatch();
    SP.attach(el.stage);
    history.pushState({ kind: 'watch', v: S.id, pushed: true }, '', withV(S.id));
    document.title = (S.meta.title ? S.meta.title + ' · ' : '') + baseTitle;
  }
  const back = () => { if (history.state && history.state.pushed) history.back(); else minimize(); };

  /* ------------------------------------------------------------------ header + details */
  const initial = n => (n || '?').trim().charAt(0).toUpperCase() || '?';
  function fillHeader(m) {
    el.title.textContent = m.title || 'Loading';
    el.channel.textContent = m.channel || ''; el.subs.textContent = m.subscribers || '';
    el.avatar.textContent = initial(m.channel);
    el.meta.textContent = [m.views, m.published].filter(Boolean).join('  ·  ');
    el.desc.textContent = m.description || '';
    el.open.href = `https://www.youtube.com/watch?v=${encodeURIComponent(S.id)}`;
    el.descBox.classList.remove('open'); el.desc.style.maxHeight = ''; el.more.hidden = true; el.more.textContent = 'Show more';
    el.next.innerHTML = '<div class="yt-sk"></div><div class="yt-sk"></div><div class="yt-sk"></div><div class="yt-sk"></div>';
    $('ytMoreGrid').innerHTML = ''; $('ytMoreVideos').hidden = true;
  }
  const linkify = t => esc(t).replace(/(https?:\/\/[^\s<]+)/g, u => `<a href="${u}" target="_blank" rel="noopener noreferrer nofollow">${u.length > 48 ? u.slice(0, 46) + '…' : u}</a>`);

  async function fetchDetails(id) {
    const mine = ++reqId;
    try {
      const r = await fetch(watchUrl(id), { credentials: 'same-origin', headers: { 'X-Requested-With': 'XMLHttpRequest' } });
      if (!r.ok) throw new Error(r.status);
      const d = await r.json();
      if (mine !== reqId || S.id !== id) return;
      SP.update({ title: d.title, channel: d.channel, subscribers: d.subscribers, views: d.views, published: d.published });
      el.title.textContent = d.title; el.channel.textContent = d.channel; el.subs.textContent = d.subscribers || '';
      el.avatar.textContent = initial(d.channel);
      el.meta.textContent = [d.views, d.published].filter(Boolean).join('  ·  ');
      el.desc.innerHTML = linkify(d.description || '');
      document.title = `${d.title} · ${baseTitle}`;
      setTimeout(() => { el.more.hidden = el.desc.scrollHeight <= el.desc.clientHeight + 4; }, 60);
      renderNext(d.related || []);
      saveHistory(S.meta, id);
    } catch (e) {
      if (mine === reqId) el.next.innerHTML = '<p class="yt-next-empty">Could not load suggestions.</p>';
    }
  }
  function relHtml(v, i) {
    const th = v.thumbnail || v.thumb;
    return `<a class="yt-rel" href="${withV(v.id)}" style="--i:${i}" data-id="${esc(v.id)}" data-title="${esc(v.title)}" data-channel="${esc(v.channel)}" data-views="${esc(v.views)}" data-published="${esc(v.published)}" data-duration="${esc(v.duration)}" data-thumb="${esc(th)}">
      <span class="yt-thumb"><img src="${esc(th)}" alt="" loading="lazy" decoding="async"><span class="yt-play" aria-hidden="true">${PLAY}</span>${v.duration ? `<span class="yt-dur">${esc(v.duration)}</span>` : ''}</span>
      <span class="yt-text"><b class="clamp-2">${esc(v.title)}</b><small class="clamp-1">${esc(v.channel)}</small><small class="clamp-1">${esc([v.views, v.published].filter(Boolean).join(' · '))}</small></span>
    </a>`;
  }
  const SIDE = 14;                      // the sidebar shows the first suggestions; the rest fill the grid under the video
  function cardHtml(v, i) {
    const th = v.thumbnail || v.thumb;
    return `<a class="yt-card" href="${withV(v.id)}" style="--i:${i % 12}" data-id="${esc(v.id)}" data-title="${esc(v.title)}" data-channel="${esc(v.channel)}" data-views="${esc(v.views)}" data-published="${esc(v.published)}" data-duration="${esc(v.duration)}" data-thumb="${esc(th)}">
      <span class="yt-thumb"><img src="${esc(th)}" alt="" loading="lazy" decoding="async"><span class="yt-play" aria-hidden="true">${PLAY}</span>${v.duration ? `<span class="yt-dur">${esc(v.duration)}</span>` : ''}</span>
      <span class="yt-meta"><span class="yt-avatar" aria-hidden="true">${esc(initial(v.channel))}</span><span class="yt-text"><b class="clamp-2">${esc(v.title)}</b><small class="clamp-1">${esc(v.channel)}</small><small class="clamp-1">${esc([v.views, v.published].filter(Boolean).join(' · '))}</small></span></span>
    </a>`;
  }
  function renderNext(list) {
    el.next.innerHTML = list.length ? list.slice(0, SIDE).map(relHtml).join('') : '<p class="yt-next-empty">No suggestions for this video.</p>';
    const more = list.slice(SIDE);
    $('ytMoreGrid').innerHTML = more.map(cardHtml).join('');
    $('ytMoreVideos').hidden = !more.length;
  }
  const playNext = () => {
    const f = trail.fwd.pop();
    if (f) { openVideo(f.id, f.meta, { nav: 'next' }); return; }
    const a = el.next.querySelector('.yt-rel');
    if (a) openVideo(a.dataset.id, metaOf(a), { nav: 'next' });
  };
  const playPrev = () => {
    if (S.time > 3 || !trail.back.length) { SP.seek(0); if (!S.playing) SP.toggle(); return; }   // like YouTube: restart first
    const b = trail.back.pop();
    openVideo(b.id, b.meta, { nav: 'prev' });
  };

  /* ------------------------------------------------------------------ opening videos */
  const metaOf = a => { const d = a.dataset; return { title: d.title, channel: d.channel, views: d.views, published: d.published, duration: d.duration, thumb: d.thumb }; };
  const openFrom = a => openVideo(a.dataset.id, metaOf(a));
  root.addEventListener('click', e => {
    if (e.ctrlKey || e.metaKey || e.shiftKey || e.button === 1) return;
    const a = e.target.closest('.yt-card, .yt-rel, .yt-h');
    if (a) { e.preventDefault(); openFrom(a); }
  });

  /* ------------------------------------------------------------------ player events */
  spOn('expand', expand);
  spOn('closed', () => { el.watch.hidden = true; if (root.classList.contains('watching')) { root.classList.remove('watching'); jump(listScroll); } document.title = baseTitle; if (history.state && history.state.kind === 'watch') history.replaceState({ kind: 'list' }, '', listUrl()); });
  spOn('ended', () => { if (el.auto.checked) playNext(); });
  let skipTimer = 0;
  spOn('error', () => {
    const has = !!el.next.querySelector('.yt-rel');
    $('ytErrNext').hidden = !has;
    clearTimeout(skipTimer);
    if (has && el.auto.checked) skipTimer = setTimeout(() => { if (!$('ytErr').hidden) playNext(); }, 3500);
  });
  spOn('skip', playNext);
  spOn('next', playNext);
  spOn('prev', playPrev);

  /* ------------------------------------------------------------------ controls */
  $('ytBack').addEventListener('click', back);
  $('ytPrevB').addEventListener('click', () => playPrev());
  $('ytNextB').addEventListener('click', () => playNext());
  $('ytMiniBtn').addEventListener('click', back);
  const collapsed = () => parseFloat(getComputedStyle(el.desc).lineHeight) * 3 + 'px';
  el.more.addEventListener('click', () => {
    const on = el.descBox.classList.toggle('open');
    el.desc.style.maxHeight = on ? el.desc.scrollHeight + 'px' : collapsed();
    el.more.textContent = on ? 'Show less' : 'Show more';
    if (on) setTimeout(() => { if (el.descBox.classList.contains('open')) el.desc.style.maxHeight = 'none'; }, 450);
    else { el.desc.style.maxHeight = el.desc.scrollHeight + 'px'; void el.desc.offsetHeight; el.desc.style.maxHeight = collapsed(); }
  });
  el.share.addEventListener('click', async () => {
    const url = `${location.origin}${withV(S.id)}`;
    const label = el.share.lastElementChild;
    try { await navigator.clipboard.writeText(url); label.textContent = 'Link copied'; } catch (err) { label.textContent = 'Copy failed'; }
    setTimeout(() => { label.textContent = 'Share'; }, 1600);
  });
  try { const a = localStorage.getItem('yt:auto'); if (a !== null) el.auto.checked = a === '1'; } catch (e) { /* storage blocked */ }
  el.auto.addEventListener('change', () => { try { localStorage.setItem('yt:auto', el.auto.checked ? '1' : '0'); } catch (e) { /* ignore */ } });

  const tab = which => {
    const hist = which === 'hist';
    el.tabNext.setAttribute('aria-selected', String(!hist)); el.tabHist.setAttribute('aria-selected', String(hist));
    el.next.hidden = hist; el.histList.hidden = !hist; el.autoWrap.hidden = hist;
    if (hist) renderHistory();
  };
  el.tabNext.addEventListener('click', () => tab('next'));
  el.tabHist.addEventListener('click', () => tab('hist'));

  listen(window, 'keydown', e => {
    const t = e.target;
    if ((t && /^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName)) || e.ctrlKey || e.metaKey || e.altKey) return;
    if (e.key === 'Escape' && !el.lexi.hidden) openLexi(false);
    else if ((e.key === 'Escape' || e.key === 'i' || e.key === 'I') && inWatch()) back();
    else if ((e.key === 'i' || e.key === 'I') && S.mode === 'mini' && S.id) expand();
  });

  /* ------------------------------------------------------------------ search and topics without leaving the page */
  let loaded = listUrl();
  async function loadList(url, push) {
    minimize(false);                                         // like YouTube: the video drops into the mini player
    el.results.classList.add('loading'); el.results.setAttribute('aria-busy', 'true');
    const part = url + (url.includes('?') ? '&' : '?') + '_part=1';
    try {
      const r = await fetch(part, { credentials: 'same-origin', headers: { 'X-Requested-With': 'XMLHttpRequest' } });
      if (r.redirected) { location.href = url; return; }
      if (!r.ok) throw new Error(r.status);
      el.results.innerHTML = await r.text();
      if (push) history.pushState({ kind: 'list' }, '', url);
      syncChrome(url);
      prepGrid();
      scrollTo({ top: 0, behavior: reduce ? 'auto' : 'smooth' });
    } catch (e) { location.href = url; return; }
    el.results.classList.remove('loading'); el.results.removeAttribute('aria-busy');
  }
  function syncChrome(url) {
    const u = new URL(url, location.origin);
    const q = u.searchParams.get('q') || '', topic = u.searchParams.get('topic') || '';
    el.input.value = q; el.clear.hidden = !q;
    [...el.chips.children].forEach(a => {
      const t = new URL(a.href, location.origin).searchParams.get('topic') || '';
      if (!q && t === topic) a.setAttribute('aria-current', 'true'); else a.removeAttribute('aria-current');
    });
  }
  el.form.addEventListener('submit', e => {
    e.preventDefault();
    const q = el.input.value.trim();
    loadList(q ? `${el.form.getAttribute('action')}?q=${encodeURIComponent(q)}` : el.form.getAttribute('action'), true);
  });
  el.clear.addEventListener('click', e => { e.preventDefault(); loadList(el.form.getAttribute('action'), true); });
  el.input.addEventListener('input', () => { el.clear.hidden = !el.input.value; });
  el.chips.addEventListener('click', e => {
    const a = e.target.closest('a');
    if (!a || e.ctrlKey || e.metaKey || e.shiftKey) return;
    e.preventDefault();
    loadList(a.getAttribute('href'), true);
  });

  listen(window, 'popstate', e => {
    if (location.pathname !== myPath) return;                 // another page: the soft navigation handles it
    const st = e.state || {};
    if (st.kind === 'watch' && st.v) {
      if (S.id) {                                   // something is playing: show it, never switch to another video
        if (!inWatch()) { showWatch(); SP.attach(el.stage); }
        if (st.v !== S.id) history.replaceState({ kind: 'watch', v: S.id, pushed: true }, '', withV(S.id));
      } else openVideo(st.v, null, { push: false });
    } else {
      if (inWatch()) minimize(true);
      if (listUrl() !== loaded) loadList(listUrl(), false);
    }
  });

  /* ------------------------------------------------------------------ results grid: length filter, broken thumbnails */
  const seconds = s => { const p = (s || '').split(':').map(Number); return !p.length || p.some(Number.isNaN) ? 0 : p.reduce((a, n) => a * 60 + n, 0); };
  function prepGrid() {
    loaded = listUrl();
    const grid = $('ytGrid');
    if (grid) [...grid.children].forEach(c => { c.dataset.sec = seconds(c.dataset.duration); });
  }
  root.addEventListener('click', e => {
    const b = e.target.closest('[data-len]');
    const grid = $('ytGrid');
    if (!b || !grid) return;
    [...$('ytLen').children].forEach(x => x.setAttribute('aria-pressed', String(x === b)));
    const mode = b.dataset.len; let shown = 0, k = 0;
    [...grid.children].forEach(c => {
      const s = +c.dataset.sec;
      const ok = mode === 'all' || (mode === 'short' && s < 300) || (mode === 'mid' && s >= 300 && s <= 1200) || (mode === 'long' && s > 1200);
      const was = c.hidden; c.hidden = !ok;
      if (ok) { shown++; if (was && !reduce) { c.style.setProperty('--i', Math.min(k++, 10)); c.classList.remove('enter'); void c.offsetWidth; c.classList.add('enter'); } }
    });
    const none = $('ytNone'); if (none) none.hidden = shown > 0;
  });
  const deadCard = img => { const c = img.closest('.yt-card, .yt-rel, .yt-h'); if (c) c.remove(); };
  listen(document, 'error', e => {
    const img = e.target;
    if (!(img instanceof HTMLImageElement) || !img.closest('.yt-thumb')) return;
    const m = /\/vi\/([^/]+)\//.exec(img.src);
    if (m && !img.dataset.retry) { img.dataset.retry = '1'; img.src = `https://i.ytimg.com/vi/${m[1]}/hqdefault.jpg`; } else deadCard(img);
  }, true);
  listen(document, 'load', e => {
    const img = e.target;
    if (img instanceof HTMLImageElement && img.closest('.yt-card') && img.naturalWidth > 0 && img.naturalWidth <= 120) deadCard(img);   // YouTube's placeholder for removed videos
  }, true);
  prepGrid();

  /* ------------------------------------------------------------------ history (this device), shown in the sidebar */
  const HKEY = 'yt:hist';
  const readHist = () => { try { return JSON.parse(localStorage.getItem(HKEY) || '[]'); } catch (e) { return []; } };
  function saveHistory(m, id) {
    if (!m || !m.title) return;
    const list = readHist().filter(x => x.id !== id);
    list.unshift({ id, title: m.title, channel: m.channel || '', duration: m.duration || '', thumbnail: m.thumb || `https://i.ytimg.com/vi/${id}/mqdefault.jpg`, ts: Date.now() });
    try { localStorage.setItem(HKEY, JSON.stringify(list.slice(0, 30))); } catch (e) { /* ignore */ }
    if (!el.histList.hidden) renderHistory();
  }
  function renderHistory() {
    const list = readHist();
    el.histList.innerHTML = list.length
      ? list.map(relHtml).join('') + '<button type="button" class="yt-link yt-hist-clear" id="ytHistClear">Clear history</button>'
      : '<p class="yt-next-empty">Videos you watch will appear here.</p>';
    const c = $('ytHistClear');
    if (c) c.addEventListener('click', () => { try { localStorage.removeItem(HKEY); } catch (e) { /* ignore */ } renderHistory(); });
  }

  /* ------------------------------------------------------------------ Lexi about this video */
  function md(src) {
    const blocks = [];
    const t = esc(src).replace(/```(\w*)\n?([\s\S]*?)```/g, (m, l, code) => { blocks.push(`<pre><code>${code.replace(/\n$/, '')}</code></pre>`); return `\u0000${blocks.length - 1}\u0000`; });
    const inline = s => s.replace(/`([^`]+)`/g, '<code>$1</code>').replace(/\*\*([^*]+)\*\*/g, '<b>$1</b>').replace(/(^|[^*])\*([^*\s][^*]*)\*/g, '$1<i>$2</i>');
    const out = []; let list = null;
    const flush = () => { if (list) { out.push(`<${list.t}>${list.items.join('')}</${list.t}>`); list = null; } };
    t.split('\n').forEach(line => {
      let m;
      if ((m = /^\s*[-*•]\s+(.*)$/.exec(line))) { if (!list || list.t !== 'ul') { flush(); list = { t: 'ul', items: [] }; } list.items.push(`<li>${inline(m[1])}</li>`); }
      else if ((m = /^\s*\d+[.)]\s+(.*)$/.exec(line))) { if (!list || list.t !== 'ol') { flush(); list = { t: 'ol', items: [] }; } list.items.push(`<li>${inline(m[1])}</li>`); }
      else { flush(); if ((m = /^#{1,4}\s+(.*)$/.exec(line))) out.push(`<h4>${inline(m[1])}</h4>`); else if (line.trim()) out.push(`<p>${inline(line)}</p>`); }
    });
    flush();
    return out.join('').replace(/\u0000(\d+)\u0000/g, (m, i) => blocks[+i]);
  }
  function lexiAdd(role, html, cls) {
    const d = document.createElement('div');
    d.className = `yt-msg ${role}${cls ? ' ' + cls : ''}`;
    d.innerHTML = html;
    el.lexiLog.appendChild(d);
    el.lexiLog.scrollTop = el.lexiLog.scrollHeight;
    return d;
  }
  function resetLexi() {
    lexiTurns = []; lexiBusy = false;
    el.lexiLog.innerHTML = '';
    el.lexiNote.textContent = 'Ask anything about this video';
    $('ytLexiChips').hidden = false;
  }
  function openLexi(open) {
    const on = open === undefined ? el.lexi.hidden : open;
    el.lexi.hidden = !on;
    el.lexiBtn.setAttribute('aria-expanded', String(on));
    if (on) {
      el.lexi.classList.remove('in'); void el.lexi.offsetWidth; el.lexi.classList.add('in');
      setTimeout(() => el.lexiInput.focus({ preventScroll: true }), 50);
    }
  }
  async function ask(question) {
    if (!question || lexiBusy || !S.id) return;
    lexiBusy = true;
    $('ytLexiChips').hidden = true;
    lexiAdd('me', `<p>${esc(question)}</p>`);
    const wait = lexiAdd('ai', '<span class="yt-dots"><i></i><i></i><i></i></span>', 'wait');
    const fd = new FormData();
    fd.append('video', S.id); fd.append('question', question); fd.append('history', JSON.stringify(lexiTurns.slice(-6)));
    try {
      const r = await fetch(root.dataset.lexiUrl, { method: 'POST', body: fd, credentials: 'same-origin', headers: { 'X-CSRFToken': root.dataset.csrf, 'X-Requested-With': 'XMLHttpRequest' } });
      const d = await r.json();
      if (!d.ok) throw new Error(d.error || 'Lexi could not answer.');
      wait.classList.remove('wait'); wait.innerHTML = md(d.reply);
      lexiTurns.push({ role: 'user', text: question }, { role: 'model', text: d.reply.slice(0, 1200) });
      el.lexiNote.textContent = d.captions ? 'Answering from the video captions' : 'No captions found, so answers use the title and description';
    } catch (err) {
      wait.classList.remove('wait'); wait.classList.add('err'); wait.innerHTML = `<p>${esc(err.message || 'Lexi could not answer right now.')}</p>`;
    }
    lexiBusy = false;
    el.lexiLog.scrollTop = el.lexiLog.scrollHeight;
  }
  el.lexiBtn.addEventListener('click', () => openLexi());
  $('ytLexiClose').addEventListener('click', () => openLexi(false));
  el.lexiInput.addEventListener('keydown', e => { if (e.key === 'Escape') { e.stopPropagation(); openLexi(false); el.lexiBtn.focus(); } });
  listen(document, 'pointerdown', e => { if (!el.lexi.hidden && !el.lexi.contains(e.target) && !el.lexiBtn.contains(e.target)) openLexi(false); });
  el.lexiForm.addEventListener('submit', e => { e.preventDefault(); const q = el.lexiInput.value.trim(); el.lexiInput.value = ''; ask(q); });
  $('ytLexiChips').addEventListener('click', e => { const b = e.target.closest('[data-q]'); if (b) ask(b.dataset.q); });

  /* ------------------------------------------------------------------ start: deep link, or a player that came with us from another page */
  history.replaceState({ kind: root.dataset.start ? 'watch' : 'list', v: root.dataset.start || undefined }, '', location.href);
  if (root.dataset.start) {
    const id = root.dataset.start;
    const card = $('ytGrid') && $('ytGrid').querySelector(`[data-id="${CSS.escape(id)}"]`);
    const t = +new URL(location.href).searchParams.get('t') || 0;
    openVideo(id, card ? metaOf(card) : (S.id === id ? S.meta : {}), { push: false, start: t, refresh: true });
  }
  renderHistory();
})();
