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
    desc: $('ytDescText'), more: $('ytMore'), descBox: $('ytDesc'), next: $('ytNext'), auto: $('ytAuto'),
    share: $('ytShare'), open: $('ytOpen'), tabNext: $('ytTabNext'), autoWrap: $('ytAutoWrap'),
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

  const getActiveList = () => {
    try {
      const u = new URL(location.href);
      return u.searchParams.get('list') || '';
    } catch (e) {
      return '';
    }
  };
  const watchUrl = id => root.dataset.watchUrl.replace('XXXXXXXXXXX', encodeURIComponent(id));
  const playlistPageUrl = id => root.dataset.playlistUrl
    ? root.dataset.playlistUrl.replace('PL00000000000000000000000000000000', encodeURIComponent(id))
    : `/youtube/playlist/${encodeURIComponent(id)}/`;
  function defaultReturnUrl() {
    const u = new URL(location.href);
    const pl = u.searchParams.get('list') || getActiveList();
    if (pl) return playlistPageUrl(pl);
    const q = u.searchParams.get('q');
    if (q) return `${myPath}?q=${encodeURIComponent(q)}`;
    const topic = u.searchParams.get('topic');
    if (topic) return `${myPath}?topic=${encodeURIComponent(topic)}`;
    return myPath;
  }
  const listUrl = (href = location.href) => {
    try {
      const u = new URL(href, location.origin);
      const pl = u.searchParams.get('list');
      if (pl && !u.searchParams.get('q') && !u.searchParams.get('topic')) {
        return playlistPageUrl(pl);
      }
      u.searchParams.delete('v');
      u.searchParams.delete('t');
      u.searchParams.delete('list');
      u.searchParams.delete('_part');
      return u.pathname + (u.search || '');
    } catch (e) {
      return myPath;
    }
  };
  let lastListUrl = listUrl();
  const withV = (id, listId) => {
    const base = (history.state && history.state.fromUrl) || lastListUrl || listUrl();
    const u = new URL(base, location.origin);
    u.searchParams.set('v', id);
    u.searchParams.delete('t');
    const pl = listId !== undefined ? listId : getActiveList();
    if (pl) u.searchParams.set('list', pl);
    else u.searchParams.delete('list');
    return u.pathname + (u.search || '');
  };
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

  // The Up next list is a queue: while a video from it plays, the list stays the same and plays in its order.
  const toMeta = v => ({ id: v.id, title: v.title, channel: v.channel, channel_id: v.channel_id || '', avatar: v.avatar || '', subscribers: v.subscribers || '', views: v.views || '', published: v.published || '', duration: v.duration || '', thumbnail: v.thumbnail || v.thumb || '' });
  let queue = Array.isArray(S.meta && S.meta.related) ? S.meta.related.slice() : [];
  let pendingKeep = false;                    // the next details load keeps the queue (Previous and Next through history)
  const trail = { back: [], fwd: [] };        // videos watched this session, for Previous / Next
  const snapshot = () => (S.id ? { id: S.id, meta: Object.assign({}, S.meta) } : null);
  function openVideo(id, meta, opts = {}) {
    pendingKeep = !!opts.keepQueue;
    const targetList = opts.list !== undefined ? opts.list : (meta && meta.list ? meta.list : getActiveList());
    if (targetList) {
      meta = Object.assign({}, meta, { list: targetList });
    } else {
      if (meta) { meta.list = ''; meta.playlist = null; }
      if (!opts.keepQueue) queue = [];
      updatePlaylistUi(null);
    }
    if (opts.keepMini && S.mode === 'mini') {         // autoplay while the mini player is showing: switch inside it, do not open the page
      const prev = snapshot();
      if (prev && prev.id !== id) { trail.back.push(prev); trail.fwd = []; }
      SP.open(id, meta || {}, { start: 0 });
      resetLexi(); fillHeader(S.meta); fetchDetails(id, targetList); saveHistory(S.meta, id);
      return;
    }
    const switching = inWatch();
    const prev = snapshot();
    if (!switching) { trail.back = []; trail.fwd = []; }
    else if (prev && prev.id !== id) {
      if (opts.nav === 'prev') trail.fwd.push(prev);
      else { trail.back.push(prev); if (opts.nav !== 'next') trail.fwd = []; }
    }
    showWatch();
    const same = SP.open(id, meta || {}, { stage: el.stage, start: opts.start || 0 });
    markCurrent();
    document.title = (S.meta.title ? S.meta.title + ' · ' : '') + baseTitle;
    // A page opened from the mini player comes back with the video still playing but an empty watch panel: fill it again.
    if (!same || opts.refresh || !el.title.textContent.trim()) { resetLexi(); fillHeader(S.meta); fetchDetails(id, targetList); }
    if (opts.push !== false) {
      const url = withV(id, targetList);
      const stateObj = { kind: 'watch', v: id, list: targetList, fromUrl: lastListUrl || listUrl(), pushed: true };
      history.pushState(stateObj, '', url);
    }
    saveHistory(S.meta, id);
  }
  function minimize(fromHistory) {
    if (!inWatch()) return;
    SP.minimize();
    hideWatch();
    document.title = baseTitle;
    if (!fromHistory && history.state && history.state.kind === 'watch') {
      const target = (history.state && history.state.fromUrl) || lastListUrl || listUrl();
      history.replaceState({ kind: 'list', url: target }, '', target);
    }
  }
  function expand() {
    if (!S.id) return;
    showWatch();
    SP.attach(el.stage);
    ensureDetails();
    const url = withV(S.id);
    history.pushState({ kind: 'watch', v: S.id, list: getActiveList(), fromUrl: lastListUrl || listUrl(), pushed: true }, '', url);
    document.title = (S.meta.title ? S.meta.title + ' · ' : '') + baseTitle;
  }
  function back() {
    if (!inWatch()) return;
    minimize(true);
    const returnUrl = (history.state && (history.state.from || history.state.fromUrl)) || lastListUrl || (getActiveList() ? playlistPageUrl(getActiveList()) : defaultReturnUrl());
    if (returnUrl && (!returnUrl.startsWith(myPath) || returnUrl.includes('/playlist/') || returnUrl.includes('/channel/'))) {
      if (window.PJAX) window.PJAX.go(returnUrl);
      else location.href = returnUrl;
      return;
    }
    if (window.history.length > 1 && (history.state && (history.state.pushed || history.state.pjax || history.state.from || history.state.fromUrl || document.referrer))) {
      history.back();
    } else {
      history.pushState({ kind: 'list', url: returnUrl }, '', returnUrl);
      syncChrome(returnUrl);
      if (returnUrl !== loaded) {
        loadList(returnUrl, false);
      }
    }
  }

  /* ------------------------------------------------------------------ header + details */
  const initial = n => (n || '?').trim().charAt(0).toUpperCase() || '?';
  // Whenever the watch view comes back, make sure its details are there (back navigation can show it with an empty panel).
  function ensureDetails() {
    if (S.id && (!el.title.textContent.trim() || el.title.dataset.id !== S.id)) {
      fillHeader(S.meta);
      fetchDetails(S.id);
    } else {
      markCurrent();
    }
  }
  // The channel line: picture (or initial) and a link to the channel's page once we know its id.
  const chanLink = $('ytChanLink');
  const channelUrl = id => root.dataset.channelUrl.replace('UC0000000000000000000000', encodeURIComponent(id));
  function paintChannel(name, id, avatar) {
    el.avatar.innerHTML = avatar ? `<img src="${esc(avatar)}" alt="" referrerpolicy="no-referrer">` : esc(initial(name));
    if (id) chanLink.href = channelUrl(id);
    else chanLink.removeAttribute('href');
  }
  function fillHeader(m) {
    el.title.dataset.id = S.id || '';
    el.title.textContent = m.title || 'Loading';
    el.channel.textContent = m.channel || ''; el.subs.textContent = m.subscribers || '';
    paintChannel(m.channel, m.channel_id || '', m.avatar || '');       // the link works at once when the card knew the channel
    el.meta.textContent = [m.views, m.published].filter(Boolean).join('  ·  ');
    el.desc.innerHTML = linkify(m.description || '');
    el.open.href = `https://www.youtube.com/watch?v=${encodeURIComponent(S.id)}`;
    el.descBox.classList.remove('open'); el.desc.style.maxHeight = ''; el.more.hidden = true; el.more.textContent = 'Show more';

    const activeList = getActiveList();
    const hasRenderedPlaylist = !!(activeList && queue.length > 0 && el.next.querySelector('.yt-pl-banner'));
    const hasRenderedQueue = queue.length > 0 && !!el.next.querySelector('.yt-rel') && !el.next.querySelector('.yt-pl-banner');
    const shouldKeepNext = hasRenderedPlaylist || (hasRenderedQueue && (pendingKeep || queue.some(v => v.id === S.id)));

    if (!shouldKeepNext) {
      if (plObserver) { plObserver.disconnect(); plObserver = null; }
      el.next.innerHTML = '<div class="yt-sk"></div><div class="yt-sk"></div><div class="yt-sk"></div><div class="yt-sk"></div>';
      updatePlaylistUi(null);
    } else {
      markCurrent();
    }
    if (!$('ytMoreGrid').children.length) {
      $('ytMoreVideos').hidden = false;
      $('ytMoreGrid').innerHTML = '<div class="yt-sk"></div><div class="yt-sk"></div><div class="yt-sk"></div><div class="yt-sk"></div><div class="yt-sk"></div><div class="yt-sk"></div>';
    }
  }
  const linkify = t => esc(t).replace(/(https?:\/\/[^\s<]+)/g, u => `<a href="${u}" target="_blank" rel="noopener noreferrer nofollow">${u.length > 48 ? u.slice(0, 46) + '…' : u}</a>`);

  // Two requests: the header (title, channel, subscribers, picture) comes first and is quick; the up-next list follows.
  async function fetchDetails(id, listId) {
    const mine = ++reqId;
    const currentList = listId !== undefined ? listId : getActiveList();
    const isSamePlaylist = !!(currentList && queue.length > 0 && el.next.querySelector('.yt-pl-banner'));
    const isSameQueue = !currentList && queue.length > 0 && !!el.next.querySelector('.yt-rel') && !el.next.querySelector('.yt-pl-banner') && (queue.some(v => v.id === id) || pendingKeep);
    const get = header => {
      const u = new URL(watchUrl(id), location.origin);
      if (header) u.searchParams.set('part', 'header');
      if (currentList) u.searchParams.set('list', currentList);
      return fetch(u.pathname + u.search, { credentials: 'same-origin', headers: { 'X-Requested-With': 'XMLHttpRequest' } })
        .then(r => { if (!r.ok) throw new Error(r.status); return r.json(); });
    };
    const paintHeader = d => {
      // Keep everything in the page state, so a later refill of the header shows the same details instead of blanks.
      const updateData = {
        title: d.title, channel: d.channel, channel_id: d.channel_id,
        avatar: d.avatar, subscribers: d.subscribers, views: d.views,
        published: d.published, description: d.description
      };
      if (d.playlist && currentList) {
        updateData.playlist = d.playlist;
        updateData.list = d.playlist.id;
      } else if (!currentList) {
        updateData.playlist = null;
        updateData.list = null;
        updateData.related = null;
      }
      SP.update(updateData);
      el.title.textContent = d.title; el.channel.textContent = d.channel; el.subs.textContent = d.subscribers || '';
      paintChannel(d.channel, d.channel_id, d.avatar);
      el.meta.textContent = [d.views, d.published].filter(Boolean).join('  ·  ');
      el.desc.innerHTML = linkify(d.description || '');
      el.open.href = `https://www.youtube.com/watch?v=${encodeURIComponent(S.id)}${currentList ? `&list=${encodeURIComponent(currentList)}` : ''}`;
      document.title = `${d.title} · ${baseTitle}`;
      setTimeout(() => { el.more.hidden = el.desc.scrollHeight <= el.desc.clientHeight + 4; }, 60);
    };
    get(true).then(d => {
      if (mine === reqId && S.id === id) {
        paintHeader(d);
        updatePlaylistUi(currentList ? d.playlist || null : null);
      }
    }).catch(() => {});
    try {
      const d = await get(false);
      if (mine !== reqId || S.id !== id) return;
      paintHeader(d);
      if (isSamePlaylist && currentList) {
        markCurrent();
        if (d.related && d.related.length) {
          $('ytMoreGrid').innerHTML = d.related.map(cardHtml).join('');
          $('ytMoreVideos').hidden = false;
          hydrateRelated();
        }
      } else if (isSameQueue) {
        // Normal video within the current queue: keep Up Next stable!
        markCurrent();
        if (d.related && d.related.length) {
          const existingIds = new Set(queue.map(v => v.id));
          const newItems = d.related.filter(v => v && v.id && v.id !== S.id && !existingIds.has(v.id)).map(toMeta);
          if (newItems.length) {
            queue.push(...newItems);
            const moreGrid = $('ytMoreGrid');
            if (moreGrid) {
              const currentMoreIds = new Set([...moreGrid.querySelectorAll('.yt-card')].map(c => c.dataset.id));
              const toAppend = newItems.filter(v => !currentMoreIds.has(v.id)).slice(0, 12);
              if (toAppend.length) {
                const frag = document.createRange().createContextualFragment(toAppend.map(cardHtml).join(''));
                moreGrid.appendChild(frag);
                $('ytMoreVideos').hidden = false;
                hydrateRelated();
              }
            }
          }
        }
        SP.update({ related: queue.slice(0, 100), fresh: (d.related || []).slice(0, 50), playlist: null, list: null });
      } else {
        renderNext(d.related || [], currentList ? d.playlist : null, d.playlist_videos);
      }
      saveHistory(S.meta, id);
    } catch (e) {
      if (mine === reqId && !isSamePlaylist && !isSameQueue) el.next.innerHTML = '<p class="yt-next-empty">Could not load suggestions.</p>';
    }
  }
  // The channel picture in a card, or the first letter of the channel while there is no picture.
  const avatarHtml = v => (v.avatar ? `<img src="${esc(v.avatar)}" alt="" referrerpolicy="no-referrer">` : esc(initial(v.channel)));
  function relHtml(v, i) {
    const th = v.thumbnail || v.thumb;
    const pl = getActiveList();
    return `<a class="yt-rel" href="${withV(v.id, pl)}" style="--i:${i}" data-id="${esc(v.id)}" data-title="${esc(v.title)}" data-channel="${esc(v.channel)}" data-views="${esc(v.views)}" data-published="${esc(v.published)}" data-duration="${esc(v.duration)}" data-thumb="${esc(th)}"${pl ? ` data-list="${esc(pl)}"` : ''}>
      <span class="yt-thumb"><img src="${esc(th)}" alt="" loading="lazy" decoding="async"><span class="yt-play" aria-hidden="true">${PLAY}</span>${v.duration ? `<span class="yt-dur">${esc(v.duration)}</span>` : ''}</span>
      <span class="yt-text"><b class="clamp-2">${esc(v.title)}</b><span class="yt-chan-line"><span class="yt-avatar yt-chan-tap" aria-hidden="true"${v.channel_id ? ` data-chan="${esc(v.channel_id)}"` : ''}>${avatarHtml(v)}</span><small class="clamp-1 yt-chan-tap"${v.channel_id ? ` data-chan="${esc(v.channel_id)}"` : ''}>${esc(v.channel)}</small></span><small class="clamp-1 yt-chan-subs">${esc(v.subscribers || '')}</small><small class="clamp-1">${esc([v.views, v.published].filter(Boolean).join(' · '))}</small></span>
    </a>`;
  }
  const SIDE = 14;                      // the sidebar shows the first suggestions; the rest fill the grid under the video
  function cardHtml(v, i) {
    const th = v.thumbnail || v.thumb;
    return `<a class="yt-card" href="${withV(v.id, '')}" style="--i:${i % 12}" data-id="${esc(v.id)}" data-title="${esc(v.title)}" data-channel="${esc(v.channel)}" data-views="${esc(v.views)}" data-published="${esc(v.published)}" data-duration="${esc(v.duration)}" data-thumb="${esc(th)}">
      <span class="yt-thumb"><img src="${esc(th)}" alt="" loading="lazy" decoding="async"><span class="yt-play" aria-hidden="true">${PLAY}</span>${v.duration ? `<span class="yt-dur">${esc(v.duration)}</span>` : ''}</span>
      <span class="yt-meta"><span class="yt-avatar yt-chan-tap" aria-hidden="true"${v.channel_id ? ` data-chan="${esc(v.channel_id)}"` : ''}>${avatarHtml(v)}</span><span class="yt-text"><b class="clamp-2">${esc(v.title)}</b><small class="clamp-1 yt-chan-tap"${v.channel_id ? ` data-chan="${esc(v.channel_id)}"` : ''}>${esc(v.channel)}</small><small class="clamp-1 yt-chan-subs">${esc(v.subscribers || '')}</small><small class="clamp-1">${esc([v.views, v.published].filter(Boolean).join(' · '))}</small></span></span>
    </a>`;
  }
  function updatePlaylistUi(pl) {
    if (pl && el.tabNext) {
      el.tabNext.textContent = 'Playlist';
    } else if (el.tabNext) {
      el.tabNext.textContent = 'Up next';
    }
  }
  let renderedCount = 0;
  let plObserver = null;
  const CHUNK_SIZE = 20;

  function appendNextChunk() {
    if (renderedCount >= queue.length) {
      if (plObserver) { plObserver.disconnect(); plObserver = null; }
      const s = $('ytPlSentinel'); if (s) s.remove();
      return;
    }
    const sentinel = $('ytPlSentinel');
    const nextSlice = queue.slice(renderedCount, renderedCount + CHUNK_SIZE);
    const startIdx = renderedCount;
    renderedCount += nextSlice.length;

    const frag = document.createDocumentFragment();
    const temp = document.createElement('div');
    temp.innerHTML = nextSlice.map((v, i) => relHtml(v, (startIdx + i) % 12)).join('');
    while (temp.firstChild) {
      frag.appendChild(temp.firstChild);
    }
    if (sentinel && sentinel.parentNode === el.next) {
      el.next.insertBefore(frag, sentinel);
    } else {
      el.next.appendChild(frag);
    }

    hydrateRelated();

    if (renderedCount >= queue.length) {
      if (plObserver) { plObserver.disconnect(); plObserver = null; }
      const s = $('ytPlSentinel'); if (s) s.remove();
    }
  }

  function setupPlObserver() {
    if (plObserver) { plObserver.disconnect(); plObserver = null; }
    const sentinel = $('ytPlSentinel');
    if (!sentinel || renderedCount >= queue.length) return;
    if ('IntersectionObserver' in window) {
      plObserver = new IntersectionObserver(entries => {
        if (entries[0] && entries[0].isIntersecting) {
          appendNextChunk();
        }
      }, {
        root: el.next,
        rootMargin: '400px 0px 400px 0px'
      });
      plObserver.observe(sentinel);
    }
  }

  listen(el.next, 'scroll', () => {
    if (renderedCount < queue.length && el.next.scrollTop + el.next.clientHeight >= el.next.scrollHeight - 350) {
      appendNextChunk();
    }
  }, { passive: true });

  function renderNext(list, playlistInfo, playlistVideos) {
    if (plObserver) { plObserver.disconnect(); plObserver = null; }
    const currentList = getActiveList();
    const pl = (playlistInfo && playlistInfo.id && currentList) ? playlistInfo : null;
    let fresh;
    const keep = pendingKeep; pendingKeep = false;
    if (pl) {
      const plItems = (playlistVideos && playlistVideos.length) ? playlistVideos : list;
      fresh = plItems.map(toMeta);
      if (!keep || !queue.length) queue = fresh.slice();
    } else {
      fresh = list.filter(v => v && v.id && v.id !== S.id).map(toMeta);
      if (!keep && !queue.some(v => v.id === S.id)) queue = fresh.slice();
    }
    updatePlaylistUi(pl);
    const items = queue;
    let html = '';
    if (pl) {
      const curIdx = queue.findIndex(v => v.id === S.id);
      html += `<div class="yt-pl-banner">
        <div class="yt-pl-banner-head">
          <span style="display:inline-flex;align-items:center;gap:.35rem;"><svg viewBox="0 0 24 24" aria-hidden="true" fill="currentColor"><path d="M4 6h11M4 11h11M4 16h7M18 14v6l4-3-4-3z" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round"/></svg>Playlist</span>
          <span class="yt-pl-idx">${curIdx >= 0 ? curIdx + 1 : 1} / ${queue.length}</span>
        </div>
        <div class="yt-pl-banner-title">${esc(pl.title)}</div>
      </div>`;

      if (!items.length) {
        html += '<p class="yt-next-empty">No videos in this playlist.</p>';
        el.next.innerHTML = html;
      } else {
        const initCount = Math.min(items.length, Math.max(CHUNK_SIZE, curIdx >= 0 ? curIdx + 8 : CHUNK_SIZE));
        renderedCount = initCount;
        html += items.slice(0, initCount).map((v, i) => relHtml(v, i % 12)).join('');
        if (initCount < items.length) {
          html += '<div id="ytPlSentinel" style="height:1px;grid-column:1/-1;"></div>';
        }
        el.next.innerHTML = html;
        if (initCount < items.length) {
          setupPlObserver();
        }
      }

      // Populate "More videos" grid with recommendations below the player!
      const more = (list && list.length ? list : items.slice(CHUNK_SIZE)).filter(v => v.id !== S.id).slice(0, 24);
      $('ytMoreGrid').innerHTML = more.map(cardHtml).join('');
      $('ytMoreVideos').hidden = !more.length;
    } else {
      renderedCount = items.length;
      html += items.length ? items.map((v, i) => relHtml(v, i % 12)).join('') : '<p class="yt-next-empty">No suggestions for this video.</p>';
      el.next.innerHTML = html;
      const more = (list && list.length ? list : items).slice(0, 24);
      $('ytMoreGrid').innerHTML = more.map(cardHtml).join('');
      $('ytMoreVideos').hidden = !more.length;
    }
    markCurrent();
    hydrateRelated();
    const curEl = el.next.querySelector('.yt-rel.current');
    if (curEl && typeof curEl.scrollIntoView === 'function') {
      try { curEl.scrollIntoView({ block: 'nearest', behavior: 'smooth' }); } catch (e) {}
    }
    // the docked player plays the same queue, and uses the suggestions of the last video when the queue runs out
    SP.update({ related: queue.slice(0, 100), fresh: fresh.slice(0, 50), playlist: pl || null, list: pl ? pl.id : null });
  }
  // Up next and the grid under the video always show which video is playing now (also after Next, Previous or autoplay).
  function markCurrent() {
    const curIdx = queue.findIndex(v => v.id === S.id);
    if (curIdx >= renderedCount && renderedCount < queue.length) {
      while (curIdx >= renderedCount && renderedCount < queue.length) {
        appendNextChunk();
      }
    }
    document.querySelectorAll('#ytNext .yt-rel, #ytMoreGrid .yt-card').forEach(a => {
      const on = a.dataset.id === S.id;
      a.classList.toggle('current', on);
      if (on) a.setAttribute('aria-current', 'true'); else a.removeAttribute('aria-current');
    });
    const idxEl = document.querySelector('.yt-pl-idx');
    if (idxEl && curIdx >= 0) {
      idxEl.textContent = `${curIdx + 1} / ${queue.length}`;
    }
    const curRel = el.next.querySelector('.yt-rel.current');
    if (curRel && typeof curRel.scrollIntoView === 'function') {
      try { curRel.scrollIntoView({ block: 'nearest', behavior: 'smooth' }); } catch (e) {}
    }
    const target = nextTarget();
    if (target && target.v && SP && typeof SP.preload === 'function') {
      SP.preload(target.v.id);
    }
  }
  // The next video in the queue; when the queue runs out, the first suggestion of the last video.
  function nextTarget() {
    const i = queue.findIndex(v => v.id === S.id);
    if (i >= 0 && i + 1 < queue.length) return { v: queue[i + 1], list: queue };
    if (i < 0 && queue.length > 0) return { v: queue[0], list: queue };
    const fresh = ((S.meta && S.meta.fresh) || []).filter(v => v && v.id && v.id !== S.id);
    if (fresh.length) return { v: fresh[0], list: fresh };
    return null;
  }
  const playNext = auto => {
    const keepMini = auto === true;                   // autoplay keeps the mini player; the Next button opens the page
    // Only the Next button goes back through the history after Previous; autoplay follows the queue.
    const f = keepMini ? null : trail.fwd.pop();
    if (f) { openVideo(f.id, f.meta, { nav: 'next', keepMini, keepQueue: true, list: getActiveList() }); return; }
    const t = nextTarget();
    if (!t) return;
    if (t.list !== queue) queue = t.list.slice();
    openVideo(t.v.id, t.v, { nav: 'next', keepMini, keepQueue: true, list: getActiveList() });
  };
  const playPrev = () => {
    if (S.time > 3) { SP.seek(0); if (!S.playing) SP.toggle(); return; }   // like YouTube: restart first
    if (trail.back.length) {
      const b = trail.back.pop();
      openVideo(b.id, b.meta, { nav: 'prev', keepQueue: true, list: getActiveList() });
      return;
    }
    const i = queue.findIndex(v => v.id === S.id);
    if (i > 0) {
      openVideo(queue[i - 1].id, queue[i - 1], { nav: 'prev', keepQueue: true, list: getActiveList() });
    } else {
      SP.seek(0); if (!S.playing) SP.toggle();
    }
  };

  /* ------------------------------------------------------------------ opening videos */
  const metaOf = a => {
    const d = a.dataset, ch = a.querySelector('[data-chan]');
    const isRel = a.classList.contains('yt-rel');
    const urlList = a.href ? (new URL(a.href, location.origin).searchParams.get('list') || '') : '';
    const listId = d.list || urlList || (isRel ? getActiveList() : '');
    return {
      title: d.title, channel: d.channel, channel_id: ch ? ch.dataset.chan : '',
      views: d.views, published: d.published, duration: d.duration, thumb: d.thumb,
      list: listId
    };
  };
  const openFrom = a => {
    const isRel = a.classList.contains('yt-rel');
    const urlList = a.href ? (new URL(a.href, location.origin).searchParams.get('list') || '') : '';
    const explicitList = a.dataset.list || urlList;
    const listId = explicitList || (isRel ? getActiveList() : '');
    const inCurrentQueue = queue.some(v => v.id === a.dataset.id) || (isRel && queue.length > 0);
    openVideo(a.dataset.id, metaOf(a), { list: listId, keepQueue: inCurrentQueue });
  };
  root.addEventListener('click', e => {
    if (e.ctrlKey || e.metaKey || e.shiftKey || e.button === 1) return;
    const chan = e.target.closest('[data-chan]');          // a channel name on a card opens that channel, not the video
    if (chan) {
      e.preventDefault(); e.stopPropagation();              // stop the site's link handler from opening the video instead
      const url = channelUrl(chan.dataset.chan);
      if (window.PJAX) window.PJAX.go(url); else location.href = url;
      return;
    }
    const a = e.target.closest('.yt-card, .yt-rel, .yt-h');
    if (a) { e.preventDefault(); openFrom(a); }
  });

  /* ------------------------------------------------------------------ player events */
  spOn('expand', expand);
  spOn('closed', () => {
    el.watch.hidden = true;
    if (root.classList.contains('watching')) { root.classList.remove('watching'); jump(listScroll); }
    document.title = baseTitle;
    if (history.state && history.state.kind === 'watch') {
      const target = (history.state && history.state.fromUrl) || lastListUrl || listUrl();
      history.replaceState({ kind: 'list', url: target }, '', target);
    }
  });
  spOn('ended', () => { if (el.auto.checked && S.mode !== 'mini') playNext(true); });   // a docked player moves on by itself (player.js)
  let errSkipTimer = null;
  spOn('error', () => {
    clearInterval(errSkipTimer);
    const hasNext = !!nextTarget() || !!el.next.querySelector('.yt-rel');
    const btn = $('ytErrNext');
    if (btn) {
      btn.hidden = !hasNext;
      btn.textContent = 'Play next';
    }
    if (hasNext && el.auto && el.auto.checked) {
      let count = 4;
      if (btn) btn.textContent = `Play next (${count}s)`;
      errSkipTimer = setInterval(() => {
        count--;
        if (count > 0) {
          if (btn) btn.textContent = `Play next (${count}s)`;
        } else {
          clearInterval(errSkipTimer);
          if (btn) btn.textContent = 'Play next';
          playNext(true);
        }
      }, 1000);
    }
  });
  spOn('playing', () => {
    clearInterval(errSkipTimer);
    const btn = $('ytErrNext');
    if (btn) btn.textContent = 'Play next';
  });
  spOn('skip', () => playNext(true));
  spOn('next', playNext);
  spOn('prev', playPrev);

  /* ------------------------------------------------------------------ controls */
  $('ytBack').addEventListener('click', back);
  $('ytPrevB').addEventListener('click', () => playPrev());
  $('ytNextB').addEventListener('click', () => playNext());
  $('ytMiniBtn').addEventListener('click', () => minimize(false));
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

  listen(window, 'keydown', e => {
    const t = e.target;
    if ((t && /^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName)) || e.ctrlKey || e.metaKey || e.altKey) return;
    if (e.key === 'Escape' && !el.lexi.hidden) openLexi(false);
    else if ((e.key === 'Escape' || e.key === 'i' || e.key === 'I') && inWatch()) back();
    else if ((e.key === 'i' || e.key === 'I') && S.mode === 'mini' && S.id) expand();
  });

  /* ------------------------------------------------------------------ search and topics without leaving the page */
  let loaded = lastListUrl || listUrl();
  async function loadList(url, push) {
    minimize(true);                                         // dock into mini player cleanly without overwriting state
    el.results.classList.add('loading'); el.results.setAttribute('aria-busy', 'true');
    const u = new URL(url, location.origin);
    const cleanUrl = u.pathname + (u.search || '');
    lastListUrl = cleanUrl;
    const part = cleanUrl + (cleanUrl.includes('?') ? '&' : '?') + '_part=1';
    try {
      const r = await fetch(part, { credentials: 'same-origin', headers: { 'X-Requested-With': 'XMLHttpRequest' } });
      if (r.redirected) { location.href = cleanUrl; return; }
      if (!r.ok) throw new Error(r.status);
      el.results.innerHTML = await r.text();
      loaded = cleanUrl;
      lastListUrl = cleanUrl;
      if (push) history.pushState({ kind: 'list', url: cleanUrl }, '', cleanUrl);
      syncChrome(cleanUrl);
      prepGrid();
      scrollTo({ top: 0, behavior: reduce ? 'auto' : 'smooth' });
    } catch (e) {
      console.warn('loadList error:', e);
    } finally {
      el.results.classList.remove('loading');
      el.results.removeAttribute('aria-busy');
    }
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

  /* ------------------------------------------------------------------ search suggestions, as you type (YouTube's list) */
  const suggestBox = document.createElement('div');
  suggestBox.className = 'yt-suggest'; suggestBox.id = 'ytSuggest'; suggestBox.setAttribute('role', 'listbox'); suggestBox.hidden = true;
  el.form.appendChild(suggestBox);
  let suggestT = 0, suggestCtl = null, suggestIdx = -1, suggestItems = [];
  // the part the student has typed is bold, the rest is normal (as on YouTube)
  const hiLite = (text, q) => (text.toLowerCase().startsWith(q.toLowerCase()) ? `<b>${esc(text.slice(0, q.length))}</b>${esc(text.slice(q.length))}` : esc(text));
  function closeSuggest() { suggestBox.hidden = true; suggestIdx = -1; el.input.setAttribute('aria-expanded', 'false'); }
  function paintSuggest(list, q) {
    suggestItems = list; suggestIdx = -1;
    if (!list.length) { closeSuggest(); return; }
    suggestBox.innerHTML = list.map((txt, i) => `<button type="button" role="option" class="yt-sg" data-i="${i}" aria-selected="false"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M11 4a7 7 0 1 0 4.4 12.4L20 21" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round"/></svg><span>${hiLite(txt, q)}</span></button>`).join('');
    suggestBox.hidden = false; el.input.setAttribute('aria-expanded', 'true');
  }
  function fetchSuggest(q) {
    clearTimeout(suggestT);
    if (!q) { closeSuggest(); return; }
    suggestT = setTimeout(() => {
      if (suggestCtl) suggestCtl.abort();
      suggestCtl = new AbortController();
      fetch(`${root.dataset.suggestUrl}?q=${encodeURIComponent(q)}`, { credentials: 'same-origin', signal: suggestCtl.signal })
        .then(r => (r.ok ? r.json() : { suggestions: [] }))
        .then(d => { if (el.input.value.trim() === q) paintSuggest(d.suggestions || [], q); })
        .catch(() => {});
    }, 160);
  }
  function chooseSuggest(i) {
    const txt = suggestItems[i];
    if (!txt) return;
    el.input.value = txt; closeSuggest(); el.form.requestSubmit();
  }
  el.input.setAttribute('aria-autocomplete', 'list'); el.input.setAttribute('aria-controls', 'ytSuggest'); el.input.setAttribute('aria-expanded', 'false');
  listen(el.input, 'input', () => fetchSuggest(el.input.value.trim()));
  listen(el.input, 'keydown', e => {
    const opts = [...suggestBox.querySelectorAll('.yt-sg')];
    if (e.key === 'Escape') { closeSuggest(); return; }
    if (suggestBox.hidden || !opts.length) return;
    if (e.key === 'ArrowDown') { e.preventDefault(); suggestIdx = (suggestIdx + 1) % opts.length; }
    else if (e.key === 'ArrowUp') { e.preventDefault(); suggestIdx = (suggestIdx - 1 + opts.length) % opts.length; }
    else if (e.key === 'Enter' && suggestIdx >= 0) { e.preventDefault(); chooseSuggest(suggestIdx); return; }
    else return;
    opts.forEach((o, i) => { const on = i === suggestIdx; o.classList.toggle('on', on); o.setAttribute('aria-selected', String(on)); });
  });
  listen(suggestBox, 'mousedown', e => { const b = e.target.closest('.yt-sg'); if (b) { e.preventDefault(); chooseSuggest(+b.dataset.i); } });
  listen(el.input, 'blur', () => setTimeout(closeSuggest, 120));
  listen(document, 'pointerdown', e => { if (!el.form.contains(e.target)) closeSuggest(); });
  listen(el.form, 'submit', closeSuggest);
  el.chips.addEventListener('click', e => {
    const a = e.target.closest('a');
    if (!a || e.ctrlKey || e.metaKey || e.shiftKey) return;
    e.preventDefault();
    loadList(a.getAttribute('href'), true);
  });

  listen(window, 'popstate', e => {
    if (location.pathname !== myPath) return;                 // another page: the soft navigation handles it
    const st = e.state || {};
    const url = new URL(location.href);
    const vid = st.v || url.searchParams.get('v') || '';
    const pl = st.list !== undefined ? st.list : (url.searchParams.get('list') || '');

    if (vid) {
      if (vid === S.id) {
        if (!inWatch()) { showWatch(); SP.attach(el.stage); }
        ensureDetails();
      } else {
        openVideo(vid, null, { push: false, list: pl, keepQueue: queue.some(v => v.id === vid) });
      }
    } else {
      if (inWatch()) minimize(true);
      const target = (st && (st.fromUrl || st.from || st.url)) || lastListUrl || (pl ? playlistPageUrl(pl) : listUrl());
      if (target && (!target.startsWith(myPath) || target.includes('/playlist/') || target.includes('/channel/'))) {
        if (window.PJAX) window.PJAX.go(target);
        else location.href = target;
        return;
      }
      syncChrome(target);
      if (target !== loaded) {
        loadList(target, false);
      }
    }
  });

  /* ------------------------------------------------------------------ results grid: length filter, broken thumbnails */
  const seconds = s => { const p = (s || '').split(':').map(Number); return !p.length || p.some(Number.isNaN) ? 0 : p.reduce((a, n) => a * 60 + n, 0); };
  // Subscriber counts and channel pictures for the cards. The results show at once; these fill in a moment later (one request).
  function hydrateChannels() {
    const ids = [...new Set([...document.querySelectorAll('[data-subs-of]')].map(s => s.dataset.subsOf))];
    if (!ids.length || !root.dataset.channelsUrl) return;
    fetch(`${root.dataset.channelsUrl}?ids=${encodeURIComponent(ids.join(','))}`, { credentials: 'same-origin' })
      .then(r => { if (!r.ok) throw new Error(r.status); return r.json(); })
      .then(d => {
        const chans = d.channels || {};
        document.querySelectorAll('[data-subs-of]').forEach(s => { const c = chans[s.dataset.subsOf]; if (c && c.subscribers) s.textContent = c.subscribers; });
        document.querySelectorAll('.yt-card, .yt-rel').forEach(a => {
          const tag = a.querySelector('[data-chan]'), c = tag && chans[tag.dataset.chan], av = a.querySelector('.yt-avatar');
          if (c && c.avatar && av && !av.querySelector('img')) av.innerHTML = `<img src="${esc(c.avatar)}" alt="" referrerpolicy="no-referrer">`;
        });
      })
      .catch(() => {});
  }
  // Up next and the grid under the video: one request resolves each card's channel (picture, subscribers, link).
  function hydrateRelated() {
    const cards = () => document.querySelectorAll('.yt-rel[data-id], .yt-card[data-id]');
    const ids = [...new Set([...cards()].filter(c => !c.querySelector('[data-chan]')).map(c => c.dataset.id))];
    if (!ids.length || !root.dataset.videoChannelsUrl) return;
    fetch(`${root.dataset.videoChannelsUrl}?ids=${encodeURIComponent(ids.join(','))}`, { credentials: 'same-origin' })
      .then(r => { if (!r.ok) throw new Error(r.status); return r.json(); })
      .then(d => {
        const vids = d.videos || {};
        cards().forEach(c => {
          const v = vids[c.dataset.id];
          if (!v) return;
          const tags = c.querySelectorAll('.yt-chan-tap'), sub = c.querySelector('.yt-chan-subs'), av = c.querySelector('.yt-avatar');
          tags.forEach(t => { t.dataset.chan = v.channel_id; });
          if (sub && v.subscribers) sub.textContent = v.subscribers;
          if (av && v.avatar && !av.querySelector('img')) av.innerHTML = `<img src="${esc(v.avatar)}" alt="" referrerpolicy="no-referrer">`;
        });
      })
      .catch(() => {});
  }
  function prepGrid() {
    loaded = listUrl();
    hydrateChannels();
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
      const ok = c.dataset.keep === '1' || mode === 'all' || (mode === 'short' && s < 300) || (mode === 'mid' && s >= 300 && s <= 1200) || (mode === 'long' && s > 1200);
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
    // YouTube's placeholder for removed videos is a tiny thumbnail. Only thumbnails count: channel pictures are small too.
    if (img instanceof HTMLImageElement && img.closest('.yt-thumb') && img.naturalWidth > 0 && img.naturalWidth <= 120) deadCard(img);
  }, true);
  prepGrid();

  /* ------------------------------------------------------------------ history stub */
  const saveHistory = () => {};

  /* ------------------------------------------------------------------ Lexi about this video */
  function md(src) {
    const blocks = [];
    const t = esc(src).replace(/```(\w*)\n?([\s\S]*?)```/g, (m, l, code) => { blocks.push(`<pre><code>${code.replace(/\n$/, '')}</code></pre>`); return `\u0000${blocks.length - 1}\u0000`; });
    const inline = s => s.replace(/`([^`]+)`/g, '<code>$1</code>').replace(/\*\*([^*]+)\*\*/g, '<b>$1</b>').replace(/(^|[^*])\*([^*\s][^*]*)\*/g, '$1<i>$2</i>');
    // Markdown tables: a header row, a |---| separator row, then body rows. Each table becomes one placeholder line.
    const rowRe = /^\s*\|.*\|\s*$/, sepRe = /^\s*\|?\s*:?-{3,}/;
    const cells = r => r.trim().replace(/^\||\|$/g, '').split('|').map(c => c.trim());
    const withTables = text => {
      const ls = text.split('\n'), outLines = [];
      for (let i = 0; i < ls.length; i++) {
        if (rowRe.test(ls[i]) && i + 1 < ls.length && sepRe.test(ls[i + 1])) {
          const align = cells(ls[i + 1]).map(c => (/^:-+:$/.test(c) ? 'center' : /-:$/.test(c) ? 'right' : 'left'));
          const th = cells(ls[i]).map((c, k) => `<th style="text-align:${align[k] || 'left'}">${inline(c)}</th>`).join('');
          let j = i + 2; const body = [];
          while (j < ls.length && rowRe.test(ls[j])) { body.push(`<tr>${cells(ls[j]).map((c, k) => `<td style="text-align:${align[k] || 'left'}">${inline(c)}</td>`).join('')}</tr>`); j++; }
          blocks.push(`<div class="yt-md-table"><table><thead><tr>${th}</tr></thead><tbody>${body.join('')}</tbody></table></div>`);
          outLines.push(`\u0000${blocks.length - 1}\u0000`);
          i = j - 1;
        } else outLines.push(ls[i]);
      }
      return outLines.join('\n');
    };
    const out = []; let list = null;
    const flush = () => { if (list) { out.push(`<${list.t}>${list.items.join('')}</${list.t}>`); list = null; } };
    withTables(t).split('\n').forEach(line => {
      let m;
      if (/^\u0000\d+\u0000$/.test(line.trim())) { flush(); out.push(line.trim()); return; }
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
  const startList = root.dataset.startList || new URL(location.href).searchParams.get('list') || '';
  const prevFrom = (history.state && (history.state.from || history.state.fromUrl))
    || (document.referrer && document.referrer.includes(location.host) ? new URL(document.referrer).pathname + new URL(document.referrer).search : '');
  const initialListUrl = prevFrom || (startList ? playlistPageUrl(startList) : listUrl());
  lastListUrl = initialListUrl;
  loaded = listUrl();
  history.replaceState(Object.assign({}, history.state, {
    kind: root.dataset.start ? 'watch' : 'list',
    v: root.dataset.start || undefined,
    list: startList || undefined,
    fromUrl: initialListUrl,
    pushed: !!(history.state && (history.state.pushed || history.state.pjax || prevFrom))
  }), '', location.href);
  if (root.dataset.start) {
    const id = root.dataset.start;
    const card = $('ytGrid') && $('ytGrid').querySelector(`[data-id="${CSS.escape(id)}"]`);
    const t = +new URL(location.href).searchParams.get('t') || 0;
    openVideo(id, card ? metaOf(card) : (S.id === id ? S.meta : {}), { push: false, start: t, refresh: true, list: startList });
  }
  el.auto.checked = SP.autoplay;                       // the switch and the docked player share one setting
  el.auto.addEventListener('change', () => { SP.autoplay = el.auto.checked; });
})();
