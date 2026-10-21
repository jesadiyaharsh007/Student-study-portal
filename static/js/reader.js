/* Book reader: fetches one book as chapters, shows one chapter at a time, remembers where you stopped. */
(() => {
  'use strict';
  const $ = s => document.querySelector(s);
  const body = document.body;
  const id = body.dataset.id;
  const KEY = 'rd:' + id;
  const PREFS = 'rd:prefs';
  const reduce = matchMedia('(prefers-reduced-motion: reduce)').matches;
  const WPM = 230;

  const read = k => { try { return JSON.parse(localStorage.getItem(k) || 'null'); } catch (e) { return null; } };
  const write = (k, v) => { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) { /* storage full or blocked */ } };
  const esc = s => String(s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

  /* ---------- preferences ---------- */
  const root = document.documentElement;
  const prefs = Object.assign({ size: 20, font: 'serif', lh: 1.75, width: 680, theme: root.dataset.rd || 'paper' }, read(PREFS) || {});
  function applyPrefs() {
    root.dataset.rd = prefs.theme;
    root.style.setProperty('--rd-size', prefs.size + 'px');
    root.style.setProperty('--rd-lh', prefs.lh);
    root.style.setProperty('--rd-w', prefs.width + 'px');
    root.dataset.font = prefs.font;
    $('#size').value = prefs.size;
    document.querySelectorAll('[data-pref]').forEach(group => {
      const cur = String(prefs[group.dataset.pref]);
      group.querySelectorAll('button').forEach(b => { const on = b.dataset.v === cur; b.classList.toggle('on', on); b.setAttribute('aria-pressed', String(on)); if (b.hasAttribute('role')) b.setAttribute('aria-checked', String(on)); });
    });
    write(PREFS, prefs);
  }

  /* ---------- state ---------- */
  let book = null, ch = 0, cum = [], total = 1, saveT = 0;
  const saved = read(KEY) || {};
  const page = $('#page'), stage = $('#stage');

  /* ---------- load ---------- */
  async function load() {
    $('#loading').hidden = false; $('#error').hidden = true; page.hidden = true; $('#pager').hidden = true;
    try {
      const r = await fetch(body.dataset.src, { credentials: 'same-origin' });
      if (r.redirected || r.status === 401) { location.reload(); return; }
      const d = await r.json().catch(() => ({}));
      if (!r.ok || !d.ok) throw new Error(d.error || 'This book could not be opened right now.');
      open(d.book);
    } catch (e) {
      $('#loading').hidden = true;
      $('#error-text').textContent = e.message || 'Something went wrong while getting the text.';
      $('#error').hidden = false;
    }
  }

  function open(b) {
    book = b;
    total = Math.max(1, b.words);
    let run = 0;
    cum = b.chapters.map(c => { const start = run; run += c.words; return start; });
    document.title = b.title + ' | Reader | Student Study Portal';
    $('#rd-title').textContent = b.title;
    $('#rd-sub').textContent = b.author || '';
    $('#btn-toc').disabled = false;
    buildToc();
    $('#loading').hidden = true;
    page.hidden = false;
    const resumed = typeof saved.ch === 'number';
    const start = resumed ? Math.min(Math.max(0, saved.ch), b.chapters.length - 1) : firstReal(b);
    show(start, resumed ? saved.f || 0 : 0, true);
  }

  // new readers skip publisher front matter and land on the first real chapter (it is still in the contents)
  function firstReal(b) {
    const cs = b.chapters;
    if (cs.length < 4 || cs[0].t !== 'Beginning' || cs[0].words > 1500) return 0;
    const i = cs.findIndex(c => /^(chapter|book|part|volume|stave|act|canto|letter|scene|section)\b|^([ivxlcdm]{1,6}|\d{1,3})\b[ \t.:)\]]*$/i.test(c.t) && c.words > 120);
    return i > 0 && i < 6 ? i : 0;
  }

  /* ---------- show a chapter ---------- */
  function show(i, frac = 0, instant = false) {
    ch = Math.min(Math.max(0, i), book.chapters.length - 1);
    const c = book.chapters[ch];
    const heading = c.t === 'Beginning' ? book.title : c.t;
    page.innerHTML = `<header class="rd-chhead"><small>${book.chapters.length > 1 ? 'Section ' + (ch + 1) + ' of ' + book.chapters.length : ''}</small><h1 class="rd-ch">${esc(heading)}</h1></header>${c.html}<p class="rd-end" aria-hidden="true">&#10086;</p>`;
    const lead = page.querySelector('p:not(.fig):not(.verse)');
    if (lead && /^[A-Za-z“"‘']/.test(lead.textContent.trim())) lead.classList.add('lead');
    page.classList.remove('turn'); void page.offsetWidth; if (!reduce && !instant) page.classList.add('turn');
    pager();
    markToc();
    requestAnimationFrame(() => {
      const max = document.documentElement.scrollHeight - innerHeight;
      scrollTo({ top: frac > 0 ? Math.max(0, max * frac) : 0, behavior: 'instant' });
      update();
    });
  }

  function pager() {
    const prev = book.chapters[ch - 1], next = book.chapters[ch + 1];
    $('#prev').disabled = !prev; $('#next').disabled = !next;
    $('#prev-t').textContent = prev ? prev.t : '';
    $('#next-t').textContent = next ? next.t : 'You reached the end';
    $('#pager').hidden = false;
  }

  /* ---------- progress ---------- */
  function fraction() {
    const max = document.documentElement.scrollHeight - innerHeight;
    return max > 0 ? Math.min(1, Math.max(0, scrollY / max)) : 1;
  }
  function update() {
    if (!book) return;
    const f = fraction();
    const c = book.chapters[ch];
    const done = (cum[ch] + c.words * f) / total;
    $('#bar').style.transform = `scaleX(${done.toFixed(4)})`;
    const left = Math.max(0, Math.round((total - cum[ch] - c.words * f) / WPM));
    $('#foot-ch').textContent = `${Math.round(done * 100)}% read`;
    $('#foot-left').textContent = left > 1 ? `${left >= 60 ? Math.floor(left / 60) + ' h ' + (left % 60) + ' min' : left + ' min'} left` : 'Almost done';
    clearTimeout(saveT);
    saveT = setTimeout(() => write(KEY, { ch, f: +f.toFixed(4), pct: Math.round(done * 100), ts: Date.now(), title: book.title, author: book.author, cover: book.cover }), 350);
  }
  addEventListener('scroll', () => requestAnimationFrame(update), { passive: true });
  addEventListener('beforeunload', () => { if (book) { clearTimeout(saveT); write(KEY, { ch, f: +fraction().toFixed(4), pct: Math.round(((cum[ch] + book.chapters[ch].words * fraction()) / total) * 100), ts: Date.now(), title: book.title, author: book.author, cover: book.cover }); } });

  /* ---------- contents drawer ---------- */
  function buildToc() {
    $('#toc-list').innerHTML = book.chapters.map((c, i) => `<li><button type="button" data-i="${i}"><span class="n">${i + 1}</span><span class="t">${esc(c.t)}</span></button></li>`).join('');
  }
  function markToc() {
    document.querySelectorAll('#toc-list button').forEach(b => { const i = +b.dataset.i; b.classList.toggle('cur', i === ch); b.classList.toggle('past', i < ch); if (i === ch) b.setAttribute('aria-current', 'true'); else b.removeAttribute('aria-current'); });
  }
  $('#toc-list').addEventListener('click', e => { const b = e.target.closest('button[data-i]'); if (b) { show(+b.dataset.i); closePanels(); } });
  $('#toc-q').addEventListener('input', e => {
    const q = e.target.value.trim().toLowerCase();
    document.querySelectorAll('#toc-list li').forEach(li => { li.hidden = q && !li.textContent.toLowerCase().includes(q); });
  });

  /* ---------- panels ---------- */
  const toc = $('#toc'), aa = $('#aa'), scrim = $('#scrim');
  function closePanels() {
    toc.hidden = true; aa.hidden = true; scrim.hidden = true;
    $('#btn-toc').setAttribute('aria-expanded', 'false'); $('#btn-aa').setAttribute('aria-expanded', 'false');
  }
  function openToc() {
    closePanels(); toc.hidden = false; scrim.hidden = false; $('#btn-toc').setAttribute('aria-expanded', 'true');
    const cur = toc.querySelector('.cur'); cur && cur.scrollIntoView({ block: 'center' });
  }
  function openAa() { closePanels(); aa.hidden = false; scrim.hidden = false; $('#btn-aa').setAttribute('aria-expanded', 'true'); }
  $('#btn-toc').addEventListener('click', () => (toc.hidden ? openToc() : closePanels()));
  $('#btn-aa').addEventListener('click', () => (aa.hidden ? openAa() : closePanels()));
  scrim.addEventListener('click', closePanels);
  document.querySelectorAll('[data-close]').forEach(b => b.addEventListener('click', closePanels));

  /* ---------- settings ---------- */
  document.querySelectorAll('[data-pref]').forEach(group => group.addEventListener('click', e => {
    const b = e.target.closest('button[data-v]'); if (!b) return;
    const key = group.dataset.pref; const raw = b.dataset.v;
    prefs[key] = key === 'lh' || key === 'width' ? Number(raw) : raw;
    keepPlace(applyPrefs);
  }));
  document.querySelectorAll('[data-size]').forEach(b => b.addEventListener('click', () => { prefs.size = Math.min(30, Math.max(15, prefs.size + Number(b.dataset.size))); keepPlace(applyPrefs); }));
  $('#size').addEventListener('input', e => { prefs.size = Number(e.target.value); keepPlace(applyPrefs); });
  // changing text size reflows the page: keep the same spot
  function keepPlace(fn) { const f = book ? fraction() : 0; fn(); if (book) requestAnimationFrame(() => { const max = document.documentElement.scrollHeight - innerHeight; scrollTo({ top: max * f, behavior: 'instant' }); update(); }); }

  /* ---------- navigation ---------- */
  $('#prev').addEventListener('click', () => show(ch - 1));
  $('#next').addEventListener('click', () => show(ch + 1));
  $('#retry').addEventListener('click', load);
  addEventListener('keydown', e => {
    if (e.target.closest('input, textarea, select') || e.metaKey || e.ctrlKey || e.altKey) return;
    if (e.key === 'Escape') closePanels();
    else if (!book) return;
    else if (e.key === 'ArrowRight' || e.key === 'n') show(ch + 1);
    else if (e.key === 'ArrowLeft' || e.key === 'p') show(ch - 1);
    else if (e.key === 't') (toc.hidden ? openToc() : closePanels());
    else if (e.key === '+' || e.key === '=') { prefs.size = Math.min(30, prefs.size + 1); keepPlace(applyPrefs); }
    else if (e.key === '-') { prefs.size = Math.max(15, prefs.size - 1); keepPlace(applyPrefs); }
  });

  // hide the top bar while reading down, bring it back on the way up
  let lastY = 0;
  addEventListener('scroll', () => {
    const y = scrollY, top = $('#top');
    top.classList.toggle('away', y > lastY && y > 160 && toc.hidden && aa.hidden);
    lastY = y;
  }, { passive: true });

  applyPrefs();
  load();
})();
