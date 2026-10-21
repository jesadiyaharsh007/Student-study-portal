/* Dashboard: reading history from this device (book progress is saved by the reader in localStorage). */
(() => {
  'use strict';
  const esc = s => String(s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

  const ago = ts => {
    const s = Math.max(1, Math.round((Date.now() - ts) / 1000));
    if (s < 60) return 'just now';
    const m = Math.round(s / 60); if (m < 60) return m + ' min ago';
    const h = Math.round(m / 60); if (h < 24) return h + (h === 1 ? ' hour ago' : ' hours ago');
    const d = Math.round(h / 24); if (d < 7) return d + (d === 1 ? ' day ago' : ' days ago');
    return new Date(ts).toLocaleDateString(undefined, { day: 'numeric', month: 'short' });
  };

  const load = () => {
    const items = [];
    try {
      for (let i = 0; i < localStorage.length; i++) {
        const k = localStorage.key(i);
        if (!/^rd:\d+$/.test(k)) continue;
        const v = JSON.parse(localStorage.getItem(k) || 'null');
        if (v && v.title && v.ts) items.push({ key: k, id: k.slice(3), ...v });
      }
    } catch (e) { /* storage blocked */ }
    return items.sort((a, b) => b.ts - a.ts);
  };

  function render(box) {
    const all = load();
    if (!all.length) return;                      // keep the server-rendered empty state
    const shown = all.slice(0, 6);
    box.innerHTML = shown.map((b, i) => {
      const done = b.pct >= 100;
      return `<div class="hr${done ? ' done' : ''}" style="--k:${i}">
        <a href="/books/read/${esc(b.id)}/?t=${encodeURIComponent(b.title)}&a=${encodeURIComponent(b.author || '')}" style="display:contents">
          <span class="lib-cover" aria-hidden="true"><span class="lib-cover-title">${esc(b.title.slice(0, 40))}</span><img src="${esc(b.cover || '')}" alt="" loading="lazy" data-cover></span>
          <span class="hr-t"><b>${esc(b.title)}</b><small>${done ? 'Finished' : b.pct + '% read'} &middot; ${ago(b.ts)}</small><span class="hr-bar"><i style="--p:${Math.min(100, b.pct || 0)}"></i></span></span>
        </a>
        <button class="hr-x" type="button" data-forget="${esc(b.key)}" aria-label="Remove ${esc(b.title)} from history">&times;</button>
      </div>`;
    }).join('') + `<a class="hist-cta" href="/books/"><b>${all.length > shown.length ? '+ ' + (all.length - shown.length) + ' more, and thousands to discover' : 'Find your next read'}</b><small>Browse the free library</small></a>`;
  }

  const setup = box => {
    if (box.dataset.ready) return;
    box.dataset.ready = '1';
    render(box);
    box.addEventListener('click', e => {
      const x = e.target.closest('[data-forget]');
      if (!x) return;
      e.preventDefault();
      try { localStorage.removeItem(x.dataset.forget); } catch (err) { /* ignore */ }
      const row = x.closest('.hr');
      row.style.transition = 'opacity .2s, transform .25s cubic-bezier(.23,1,.32,1)';
      row.style.opacity = '0'; row.style.transform = 'scale(.96)';
      setTimeout(() => { row.remove(); if (!box.querySelector('.hr')) location.reload(); }, 220);
    });
  };

  // the dashboard data is fetched after the page shell loads, so wait for it
  const find = () => document.querySelectorAll('[data-hist]').forEach(setup);
  find();
  new MutationObserver(find).observe(document.body, { childList: true, subtree: true });
})();
