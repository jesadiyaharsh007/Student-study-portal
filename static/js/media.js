/* Books page: cover fallbacks, retry buttons, "continue reading" shelf. */
(() => {
  'use strict';
  const $ = (s, r = document) => r.querySelector(s);

  // a cover or thumbnail that fails to load just disappears, leaving the title card behind it
  document.addEventListener('error', e => {
    const img = e.target;
    if (img instanceof HTMLImageElement && img.hasAttribute('data-cover')) img.hidden = true;
  }, true);

  document.addEventListener('click', e => {
    if (e.target.closest('[data-retry]')) location.reload();
  });

  // ---- continue reading (books page) ----
  const shelf = $('[data-shelf]');
  if (shelf) {
    const items = [];
    try {
      for (let i = 0; i < localStorage.length; i++) {
        const k = localStorage.key(i);
        if (!/^rd:\d+$/.test(k)) continue;
        const v = JSON.parse(localStorage.getItem(k) || 'null');
        if (v && v.title && v.ts && v.pct < 100) items.push({ id: k.slice(3), ...v });
      }
    } catch (err) { /* storage blocked */ }
    items.sort((a, b) => b.ts - a.ts);
    if (items.length) {
      shelf.innerHTML = items.slice(0, 4).map(b => `
        <a class="lib-resume" href="/books/read/${b.id}/?t=${encodeURIComponent(b.title)}&a=${encodeURIComponent(b.author || '')}">
          <span class="lib-cover" aria-hidden="true"><span class="lib-cover-title">${esc(b.title.slice(0, 40))}</span><img src="${esc(b.cover || '')}" alt="" loading="lazy" data-cover></span>
          <div><b>${esc(b.title)}</b><small>${esc(b.author || '')}${b.author ? ' &middot; ' : ''}${b.pct}% read</small><span class="lib-bar"><i style="--p:${b.pct}%"></i></span></div>
        </a>`).join('');
      $('[data-continue]').hidden = false;
    }
  }

  // ---- books search clear handler ----
  const booksInput = $('#booksSearchInput');
  const booksClear = $('#booksSearchClear');
  if (booksInput && booksClear) {
    booksInput.addEventListener('input', () => {
      if (booksInput.value.trim().length > 0) {
        booksClear.removeAttribute('hidden');
      } else {
        booksClear.setAttribute('hidden', '');
      }
    });
    booksClear.addEventListener('click', (e) => {
      if (!location.search) {
        e.preventDefault();
        booksInput.value = '';
        booksClear.setAttribute('hidden', '');
        booksInput.focus();
      }
    });
  }
})();
