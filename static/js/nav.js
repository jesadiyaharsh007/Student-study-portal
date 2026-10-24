/* Soft navigation: moving between pages swaps only the page content, so the navigation bar
   stays in place instead of reloading. Anything unusual (forms, login, other layouts, errors)
   falls back to a normal page load. */
(() => {
  'use strict';
  const body = document.body;
  const mainEl = () => document.getElementById('main');
  if (window.PJAX || !body.dataset.shell || !mainEl() || !history.pushState || !window.fetch || !window.DOMParser) return;

  const SKIP = /^\/(login|register|logout|admin|static|media)(\/|$)|^\/books\/read\//;
  const prog = () => document.getElementById('nprog');
  let current = location.pathname + location.search;
  let seq = 0;
  const ran = new Set([...document.querySelectorAll('script[data-once][src]')].map(s => s.getAttribute('src').split('?')[0]));
  window.PageCleanup = window.PageCleanup || [];

  const css = () => new Set([...document.querySelectorAll('link[rel=stylesheet]')].map(l => (l.getAttribute('href') || '').split('?')[0]));
  // The page's Content-Security-Policy only trusts inline scripts carrying the nonce of the first load.
  const NONCE = (document.querySelector('script[nonce]') || {}).nonce || '';

  // Prefetch: a page starts loading when the pointer rests on its link (or a finger touches it),
  // so by the time the click lands the HTML is usually here. Kept for 10 seconds, used once.
  const pre = new Map();
  const keyOf = u => { const x = new URL(u, location.href); return x.origin + x.pathname + x.search; };
  const fetchPage = href => fetch(href, { credentials: 'same-origin', headers: { 'X-Requested-With': 'pjax' } })
    .then(async r => ({ ok: r.ok, redirected: r.redirected, type: r.headers.get('content-type') || '', text: r.ok && !r.redirected ? await r.text() : '' }));
  function prefetch(href) {
    const k = keyOf(href), hit = pre.get(k);
    if (hit && Date.now() - hit.t < 10000) return;
    if (pre.size > 8) pre.delete(pre.keys().next().value);
    pre.set(k, { t: Date.now(), p: fetchPage(href).catch(() => null) });
  }
  function load(href) {
    const k = keyOf(href), hit = pre.get(k);
    pre.delete(k);
    return hit && Date.now() - hit.t < 10000 ? hit.p : fetchPage(href).catch(() => null);
  }

  function syncNav(doc) {
    const nav = 'header.nav-pill a, #overlay a, #palette a';
    document.querySelectorAll(nav).forEach(a => a.removeAttribute('aria-current'));
    doc.querySelectorAll('header.nav-pill [aria-current], #overlay [aria-current]').forEach(n => {
      const href = n.getAttribute('href');
      if (href) document.querySelectorAll(nav).forEach(a => { if (a.getAttribute('href') === href && !a.closest('#palette')) a.setAttribute('aria-current', 'page'); });
    });
    body.classList.remove('menu-open');
    document.querySelectorAll('header.nav-pill [data-menu][aria-expanded="true"]').forEach(b => b.setAttribute('aria-expanded', 'false'));
  }

  function runScripts(doc) {
    const list = [...doc.body.querySelectorAll('script')];
    for (const old of list) {
      const src = old.getAttribute('src');
      const key = src && src.split('?')[0];
      if (old.hasAttribute('data-once') && key && ran.has(key)) continue;
      const s = document.createElement('script');
      [...old.attributes].forEach(a => { if (a.name !== 'defer' && a.name !== 'async' && a.name !== 'nonce') s.setAttribute(a.name, a.value); });
      if (NONCE) s.nonce = NONCE;
      if (src) { s.async = false; if (key) ran.add(key); } else s.textContent = old.textContent;
      document.body.appendChild(s);
      if (!src) s.remove();                                     // inline code has already run
    }
  }

  async function go(url, opts = {}) {
    const u = new URL(url, location.href);
    if (u.origin !== location.origin || SKIP.test(u.pathname)) { location.href = u.href; return; }
    const mine = ++seq;
    const p = prog(); if (p) { p.className = ''; void p.offsetWidth; p.className = 'run'; }
    const res = await load(u.href);
    if (mine !== seq) return;
    if (!res || res.redirected || !res.ok || !res.type.includes('text/html')) { location.href = u.href; return; }
    const html = res.text;
    const doc = new DOMParser().parseFromString(html, 'text/html');
    if (!doc.getElementById('main') || doc.body.dataset.shell !== body.dataset.shell) { location.href = u.href; return; }

    // leaving the old page: its scripts clean up after themselves
    window.PageCleanup.splice(0).forEach(fn => { try { fn(); } catch (e) { /* ignore */ } });
    try { history.replaceState(Object.assign({}, history.state, { sy: scrollY }), ''); } catch (e) { /* ignore */ }

    // stylesheets this page needs that we do not have yet
    const have = css(), waits = [];
    doc.querySelectorAll('link[rel=stylesheet]').forEach(l => {
      const href = l.getAttribute('href') || '';
      if (href && !have.has(href.split('?')[0])) {
        const n = document.createElement('link');
        n.rel = 'stylesheet'; n.href = href;
        waits.push(new Promise(res => { n.onload = n.onerror = res; }));
        document.head.appendChild(n);
      }
    });
    if (waits.length) await Promise.race([Promise.all(waits), new Promise(r => setTimeout(r, 1800))]);
    if (mine !== seq) return;

    document.title = doc.title;
    const robots = doc.querySelector('meta[name=robots]'), mine_r = document.querySelector('meta[name=robots]');
    if (robots && mine_r) mine_r.setAttribute('content', robots.getAttribute('content'));
    const main = mainEl();
    main.innerHTML = doc.getElementById('main').innerHTML;
    document.documentElement.style.overflow = '';
    syncNav(doc);

    if (opts.push !== false) history.pushState({ pjax: true, from: current }, '', u.pathname + u.search + u.hash);
    current = u.pathname + u.search;
    scrollTo({ top: opts.scroll || 0, behavior: 'auto' });
    runScripts(doc);

    const q = prog(); if (q) { q.className = 'done'; setTimeout(() => { q.className = ''; }, 700); }
    main.focus({ preventScroll: true });
    document.dispatchEvent(new CustomEvent('pjax:load', { detail: { url: u.href } }));
  }

  // A link this script may handle: same site, not a download/new tab/log out, not a page that needs a full load.
  const softLink = target => {
    const a = target && target.closest && target.closest('a[href]');
    if (!a || a.target || a.hasAttribute('download') || a.hasAttribute('data-noprefetch') || a.getAttribute('rel') === 'external') return null;
    const u = new URL(a.href, location.href);
    return u.origin === location.origin && !SKIP.test(u.pathname) && u.protocol.startsWith('http') ? a : null;
  };
  const saveData = navigator.connection && navigator.connection.saveData;
  let hoverT = 0;
  document.addEventListener('pointerover', e => {
    const a = !saveData && e.pointerType !== 'touch' && softLink(e.target);
    clearTimeout(hoverT);
    if (a && keyOf(a.href) !== keyOf(location.href)) hoverT = setTimeout(() => prefetch(a.href), 65);
  });
  document.addEventListener('pointerout', () => clearTimeout(hoverT));
  document.addEventListener('touchstart', e => {
    const a = !saveData && softLink(e.target);
    if (a && keyOf(a.href) !== keyOf(location.href)) prefetch(a.href);
  }, { passive: true });

  document.addEventListener('click', e => {
    if (e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
    const a = softLink(e.target);
    if (!a) return;
    const u = new URL(a.href, location.href);
    if (u.pathname === location.pathname && u.search === location.search) { if (!u.hash) e.preventDefault(); return; }
    e.preventDefault();
    go(u.href);
  });

  addEventListener('popstate', e => {
    if (location.pathname + location.search === current) return;   // only the #hash changed
    go(location.href, { push: false, scroll: e.state && e.state.sy });
  });

  mainEl().setAttribute('tabindex', '-1');
  window.PJAX = { go: url => go(url) };
})();
