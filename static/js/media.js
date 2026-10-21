/* Books + Videos pages: cover fallbacks, retry buttons, video player, "continue reading" shelf. */
(() => {
  'use strict';
  const $ = (s, r = document) => r.querySelector(s);
  const esc = s => String(s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

  // a cover or thumbnail that fails to load just disappears, leaving the title card behind it
  document.addEventListener('error', e => {
    const img = e.target;
    if (img instanceof HTMLImageElement && img.hasAttribute('data-cover')) img.hidden = true;
  }, true);

  document.addEventListener('click', e => {
    if (e.target.closest('[data-retry]')) location.reload();

    // ---- video player ----
    const card = e.target.closest('[data-video]');
    const dlg = $('#player');
    if (card && dlg) {
      const id = card.dataset.video;
      const title = card.dataset.title || 'Video Lesson';
      const channel = card.dataset.channel || 'Educational Channel';
      const stats = [card.dataset.views, card.dataset.published].filter(Boolean).join(' • ');

      const titleEl = $('#player-title');
      if (titleEl) titleEl.textContent = title;

      const channelEl = $('#player-channel');
      if (channelEl) channelEl.textContent = channel;

      const statsEl = $('#player-stats');
      if (statsEl) statsEl.textContent = stats;

      const lexiEl = $('#player-lexi');
      if (lexiEl) lexiEl.href = `/chatbot/?topic=${encodeURIComponent(title)}`;

      const shareEl = $('#player-share');
      if (shareEl) shareEl.dataset.videoId = id;

      $('#player-frame').innerHTML = `<iframe src="https://www.youtube-nocookie.com/embed/${encodeURIComponent(id)}?autoplay=1&rel=0&modestbranding=1&iv_load_policy=3&playsinline=1" title="${esc(title)}" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; fullscreen" allowfullscreen referrerpolicy="strict-origin-when-cross-origin"></iframe>`;
      if (typeof dlg.showModal === 'function') dlg.showModal(); else dlg.setAttribute('open', '');
    }

    // copy study link button in player
    const shareBtn = e.target.closest('#player-share');
    if (shareBtn) {
      const vidId = shareBtn.dataset.videoId;
      if (vidId) {
        const url = `${location.origin}/youtube/?v=${encodeURIComponent(vidId)}`;
        navigator.clipboard?.writeText(url).then(() => {
          const original = shareBtn.innerHTML;
          shareBtn.innerHTML = '<span>Copied study link!</span>';
          setTimeout(() => { shareBtn.innerHTML = original; }, 2000);
        });
      }
    }

    if (e.target.closest('[data-player-close]') && dlg) dlg.close();
    if (dlg && e.target === dlg) dlg.close();                       // click on the dimmed backdrop
  });
  const dlg = $('#player');
  if (dlg) dlg.addEventListener('close', () => { $('#player-frame').innerHTML = ''; });   // stops the video

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

  // ---- videos search clear handler ----
  const videosInput = $('#videosSearchInput');
  const videosClear = $('#videosSearchClear');
  if (videosInput && videosClear) {
    videosInput.addEventListener('input', () => {
      if (videosInput.value.trim().length > 0) {
        videosClear.removeAttribute('hidden');
      } else {
        videosClear.setAttribute('hidden', '');
      }
    });
    videosClear.addEventListener('click', (e) => {
      if (!location.search) {
        e.preventDefault();
        videosInput.value = '';
        videosClear.setAttribute('hidden', '');
        videosInput.focus();
      }
    });
  }

  // ---- autoplay if url has ?v=ID and modal is ready ----
  const params = new URLSearchParams(location.search);
  const autoVid = params.get('v');
  if (autoVid && !$('#videoTheaterSection')) {
    const targetCard = $(`[data-video="${esc(autoVid)}"]`);
    if (targetCard) {
      setTimeout(() => targetCard.click(), 120);
    }
  }
})();
