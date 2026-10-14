/* Student Study Portal: front-end behaviour. Vanilla, no dependencies. */
(() => {
  'use strict';
  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => [...r.querySelectorAll(s)];
  const on = (el, ev, fn, o) => el && el.addEventListener(ev, fn, o);
  const reduce = matchMedia('(prefers-reduced-motion: reduce)').matches;
  const csrf = () => document.body.dataset.csrf || (document.cookie.match(/csrftoken=([^;]+)/) || [])[1] || '';
  const esc = s => s.replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

  /* ------------------------------------------------------------ toasts */
  const GLYPH = { success: 'check-circle', danger: 'alert-circle', warning: 'alert', info: 'info' };
  const norm = t => (/error|danger/.test(t) ? 'danger' : /success/.test(t) ? 'success' : /warning/.test(t) ? 'warning' : 'info');
  const box = $('#toasts');

  function dismiss(el) {
    if (!el || el.classList.contains('out')) return;
    el.classList.add('out');
    setTimeout(() => el.remove(), 320);
  }
  function upgrade(el) {
    if (el.dataset.up) return;
    el.dataset.up = 1;
    const type = norm(el.dataset.type || el.className);
    el.className = 'toast ' + type;
    el.insertAdjacentHTML('afterbegin', `<span class="ti"><svg class="ic"><use href="#i-${GLYPH[type]}"/></svg></span>`);
    el.insertAdjacentHTML('beforeend', '<button class="tx" type="button" aria-label="Dismiss"><svg class="ic ic-sm"><use href="#i-x"/></svg></button>');
    if (type === 'danger') el.style.setProperty('--d', '7s');
    on($('.tx', el), 'click', () => dismiss(el));
    on(el, 'animationend', e => { if (e.animationName === 'countdown') dismiss(el); });
  }
  function toast(type, text) {
    if (!box) return;
    while (box.children.length >= 4) dismiss(box.firstElementChild);
    const el = document.createElement('div');
    el.dataset.type = type;
    el.innerHTML = `<span class="tm">${esc(text)}</span>`;
    box.append(el);
    upgrade(el);
  }
  $$('.toast', box).forEach(upgrade);
  window.toast = toast;

  /* ------------------------------------------------------------ theme + menus */
  on($('[data-theme-toggle]'), 'click', () => {
    const d = document.documentElement;
    const cur = d.dataset.theme || (matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
    const next = cur === 'dark' ? 'light' : 'dark';
    d.dataset.theme = next;
    try { localStorage.setItem('theme', next); } catch (e) { /* private mode */ }
  });

  const menus = $$('[data-menu]');
  const isOpen = b => b.getAttribute('aria-expanded') === 'true';
  const setOpen = (b, open, refocus) => {
    b.setAttribute('aria-expanded', String(open));
    if (!open && refocus) b.focus();
  };
  const closeMenus = except => menus.forEach(b => { if (b !== except && isOpen(b)) setOpen(b, false); });
  menus.forEach(b => {
    on(b, 'click', e => {
      e.stopPropagation();
      const wasOpen = isOpen(b);
      closeMenus(b);
      setOpen(b, !wasOpen);
      // Opened from the keyboard (Enter/Space fires click with detail 0): move focus to the first item.
      if (!wasOpen && e.detail === 0) $('a, button', b.nextElementSibling)?.focus();
    });
    on(b.parentElement, 'focusout', e => {
      if (isOpen(b) && e.relatedTarget && !b.parentElement.contains(e.relatedTarget)) setOpen(b, false);
    });
  });
  on(document, 'click', e => { if (!e.target.closest('.menu-wrap')) closeMenus(); });
  on(document, 'keydown', e => {
    if (e.key !== 'Escape') return;
    const open = menus.find(isOpen);
    if (open) { e.preventDefault(); setOpen(open, false, true); }
  });

  const burger = $('[data-burger]');
  const setMenu = open => {
    document.body.classList.toggle('menu-open', open);
    burger?.setAttribute('aria-expanded', String(open));
    burger?.setAttribute('aria-label', open ? 'Close menu' : 'Open menu');
  };
  on(burger, 'click', () => setMenu(!document.body.classList.contains('menu-open')));
  on(document, 'click', e => { if (e.target.closest('.overlay a')) setMenu(false); });
  on(document, 'keydown', e => {
    if (e.key === 'Escape' && document.body.classList.contains('menu-open')) { setMenu(false); burger?.focus(); }
  });
  on(window, 'resize', () => { if (innerWidth > 980) setMenu(false); });

  /* ------------------------------------------------------------ dialogs */
  function openDlg(d) {
    if (!d || d.open) return;
    d.classList.remove('closing');
    d.showModal();
    document.documentElement.style.overflow = 'hidden';
  }
  function closeDlg(d) {
    if (!d || !d.open) return;
    d.classList.add('closing');
    const done = () => { d.close(); d.classList.remove('closing'); document.documentElement.style.overflow = ''; };
    reduce || d.classList.contains('palette') ? done() : setTimeout(done, 200);
  }
  $$('dialog').forEach(d => {
    on(d, 'click', e => { if (e.target === d) closeDlg(d); });
    on(d, 'cancel', e => { e.preventDefault(); closeDlg(d); });
    on(d, 'close', () => { document.documentElement.style.overflow = ''; });
  });
  on(document, 'click', e => {
    const o = e.target.closest('[data-open]');
    if (o) { e.preventDefault(); const d = document.getElementById(o.dataset.open); openDlg(d); const f = $('input,textarea,select', d); if (f && o.dataset.focus !== 'no') setTimeout(() => f.focus(), 120); }
    const c = e.target.closest('[data-close]');
    if (c) closeDlg(c.closest('dialog'));
    const a = e.target.closest('.sheet a[href]');
    if (a) closeDlg(a.closest('dialog'));
  });
  $$('dialog[data-open-on-load]').forEach(d => openDlg(d));

  /* confirm dialog for destructive forms */
  const confirmDlg = $('#confirm');
  let pending = null;
  function ask(form) {
    pending = form;
    $('#confirm-title').textContent = form.dataset.confirm || 'Are you sure?';
    $('#confirm-text').textContent = form.dataset.confirmText || "This can't be undone.";
    openDlg(confirmDlg);
    setTimeout(() => $('#confirm-ok').focus(), 80);
  }
  on($('#confirm-ok'), 'click', () => {
    const f = pending; pending = null;
    closeDlg(confirmDlg);
    if (f) { f._ok = true; f.requestSubmit(); }
  });

  /* ------------------------------------------------------------ loading + progress */
  const prog = $('#nprog');
  let progT;
  const progStart = () => { clearTimeout(progT); prog.className = ''; void prog.offsetWidth; prog.className = 'run'; };
  const progEnd = () => { prog.className = 'done'; progT = setTimeout(() => { prog.className = ''; }, 700); };
  on(window, 'pageshow', e => {
    progEnd();
    if (e.persisted) $$('.btn.loading').forEach(b => b.classList.remove('loading'));
    $$('.is-loading').forEach(n => n.classList.remove('is-loading'));
  });
  on(document, 'click', e => {
    const a = e.target.closest('a[href]');
    if (!a || e.defaultPrevented || e.button || e.metaKey || e.ctrlKey || e.shiftKey || a.target === '_blank' || a.hasAttribute('download')) return;
    const u = new URL(a.href, location.href);
    if (u.origin !== location.origin || (u.pathname === location.pathname && u.search === location.search)) return;
    progStart();
  });

  /* wrap a submit button's label so it can show a spinner */
  $$('.btn[type=submit]').forEach(b => {
    if (!$('.spin', b)) {
      const lbl = document.createElement('span');
      lbl.className = 'lbl';
      [...b.childNodes].forEach(n => { if (n.nodeType === 3 || !(n.classList?.contains('ic') || n.classList?.contains('btn-ico'))) lbl.append(n); });
      b.prepend(lbl);
      b.insertAdjacentHTML('beforeend', '<span class="spin"></span>');
    }
  });

  /* ------------------------------------------------------------ prefetch on intent */
  const seen = new Set();
  const canPrefetch = a => {
    if (!a || a.hasAttribute('data-noprefetch') || a.target || a.hasAttribute('download')) return false;
    const u = new URL(a.href, location.href);
    return u.origin === location.origin && !/^\/(logout|admin)/.test(u.pathname) && !seen.has(u.href) && u.href !== location.href && !(navigator.connection || {}).saveData;
  };
  const prefetch = a => {
    if (!canPrefetch(a)) return;
    const u = new URL(a.href, location.href).href;
    seen.add(u);
    const l = document.createElement('link');
    l.rel = 'prefetch'; l.href = u; l.as = 'document';
    document.head.append(l);
  };
  on(document, 'mousedown', e => { const a = e.target.closest('a[href]'); if (a) prefetch(a); }, { passive: true });
  on(document, 'touchstart', e => prefetch(e.target.closest('a[href]')), { passive: true });

  /* ------------------------------------------------------------ command palette */
  const pal = $('#palette'), palQ = $('#pal-q'), palList = $('#pal-list'), palEmpty = $('#pal-empty');
  if (pal) {
    let sel = 0;
    const rows = () => $$('.pal-item', palList).filter(r => !r.hidden);
    const mark = () => rows().forEach((r, i) => { r.classList.toggle('sel', i === sel); if (i === sel) r.scrollIntoView({ block: 'nearest' }); });
    const filter = () => {
      const q = palQ.value.trim().toLowerCase();
      $$('.pal-item', palList).forEach(r => { r.hidden = q && !r.textContent.toLowerCase().includes(q); });
      palEmpty.hidden = rows().length > 0;
      sel = 0; mark();
    };
    const open = () => { palQ.value = ''; filter(); openDlg(pal); setTimeout(() => palQ.focus(), 60); };
    on(document, 'click', e => { if (e.target.closest('[data-palette]')) open(); });
    on(document, 'keydown', e => {
      const typing = /input|textarea|select/i.test(e.target.tagName) || e.target.isContentEditable;
      if ((e.key.toLowerCase() === 'k' && (e.ctrlKey || e.metaKey)) || (e.key === '/' && !typing)) { e.preventDefault(); pal.open ? closeDlg(pal) : open(); }
    });
    on(palQ, 'input', filter);
    on(palQ, 'keydown', e => {
      const n = rows().length;
      if (e.key === 'ArrowDown') { e.preventDefault(); sel = (sel + 1) % n; mark(); }
      else if (e.key === 'ArrowUp') { e.preventDefault(); sel = (sel - 1 + n) % n; mark(); }
      else if (e.key === 'Enter') { e.preventDefault(); const r = rows()[sel]; if (r) { progStart(); location.href = r.href; } }
    });
    on(palList, 'pointermove', e => { const r = e.target.closest('.pal-item'); if (r) { const i = rows().indexOf(r); if (i >= 0 && i !== sel) { sel = i; mark(); } } });
  }

  /* ------------------------------------------------------------ reveal, spotlight, counters, rings */
  const reveal = $$('.reveal');
  if (reveal.length) {
    if ('IntersectionObserver' in window && !reduce) {
      const io = new IntersectionObserver(es => es.forEach(en => { if (en.isIntersecting) { en.target.classList.add('in'); io.unobserve(en.target); } }), { rootMargin: '0px 0px -8% 0px', threshold: .08 });
      reveal.forEach(el => io.observe(el));
    } else reveal.forEach(el => el.classList.add('in'));
  }
  $$('.bento a').forEach(a => on(a, 'pointermove', e => {
    const r = a.getBoundingClientRect();
    a.style.setProperty('--mx', e.clientX - r.left + 'px');
    a.style.setProperty('--my', e.clientY - r.top + 'px');
  }));
  function countUp(el) {
    const to = +el.dataset.countTo, from = +el.dataset.from || 0;
    if (reduce || to === from) { el.textContent = to; return; }
    const t0 = performance.now(), dur = 900;
    const tick = t => { const p = Math.min(1, (t - t0) / dur); el.textContent = Math.round(from + (to - from) * (1 - Math.pow(1 - p, 3))); if (p < 1) requestAnimationFrame(tick); };
    requestAnimationFrame(tick);
  }
  $$('[data-count-to]').forEach(countUp);
  const setRing = (ring, pct) => {
    const fg = $('.fg', ring);
    if (fg) fg.style.strokeDashoffset = 100 - pct;
    const n = $('[data-ring-num]', ring);
    if (n) { n.dataset.from = ring._init ? n.textContent : 0; ring._init = true; n.dataset.countTo = pct; countUp(n); }
  };
  requestAnimationFrame(() => $$('.ring[data-pct]').forEach(r => setRing(r, +r.dataset.pct)));

  /* ------------------------------------------------------------ confetti */
  function confetti(host) {
    if (reduce || !host) return;
    const cs = getComputedStyle(document.documentElement);
    const colors = [cs.getPropertyValue('--accent').trim() || '#e5501f', cs.getPropertyValue('--ink').trim() || '#0d0e10'];
    host.style.position ||= 'relative';
    for (let i = 0; i < 14; i++) {
      const b = document.createElement('i');
      b.className = 'confetti-bit';
      const a = (Math.PI * 2 * i) / 14 + Math.random() * .4, d = 34 + Math.random() * 34;
      b.style.cssText = `background:${colors[i % colors.length]};--x:${Math.cos(a) * d}px;--y:${Math.sin(a) * d}px;--r:${Math.random() * 360}deg`;
      host.append(b);
      setTimeout(() => b.remove(), 850);
    }
  }
  window.confetti = confetti;

  /* ------------------------------------------------------------ lists: counts, empty states, filters */
  function refreshCounts() {
    $$('[data-list]').forEach(list => {
      const items = $$('.item, .note', list).filter(i => !i.classList.contains('removing'));
      const done = items.filter(i => i.classList.contains('done')).length;
      const scope = list.closest('[data-scope]') || document;
      $$('[data-bind=total]', scope).forEach(n => n.textContent = items.length);
      $$('[data-bind=done]', scope).forEach(n => n.textContent = done);
      $$('[data-bind=pending]', scope).forEach(n => n.textContent = items.length - done);
      $$('.ring', scope).forEach(r => setRing(r, items.length ? Math.round(done * 100 / items.length) : 0));
      const empty = $('[data-empty]', scope);
      if (empty) { empty.hidden = items.length > 0; list.hidden = items.length === 0; }
    });
  }

  /* dashboard: keep the headline numbers in step with ticks made in the lists */
  function bumpStats(key, finished) {
    const step = finished ? -1 : 1;
    $$(`[data-stat="${key}-pending"]`).forEach(n => { n.textContent = Math.max(0, +n.textContent + step); });
    $$('[data-stat=done]').forEach(n => { n.textContent = Math.max(0, +n.textContent - step); });
    const ring = $('#overall-ring'), done = $('[data-stat=done]');
    if (ring && done) { const t = +ring.dataset.total || 0; setRing(ring, t ? Math.round(+done.textContent * 100 / t) : 0); }
  }

  function filterable(list) {
    const id = list.id;
    const q = $(`input[data-for="${id}"]`);
    const chips = $$(`[data-filter-for="${id}"] [data-filter]`);
    const none = $(`[data-nomatch-for="${id}"]`);
    let cat = 'all';
    const run = () => {
      const term = (q?.value || '').trim().toLowerCase();
      let shown = 0, k = 0;
      [...list.children].forEach(it => {
        if (it.classList.contains('removing')) return;
        const ok = (cat === 'all' || it.dataset.cat === cat) && (!term || (it.dataset.search || '').includes(term));
        const wasHidden = it.hidden;
        it.hidden = !ok;
        if (ok) {
          shown++;
          if (wasHidden && !reduce) {          // opacity + transform only, 200ms ease-out, staggered up to 8 items
            it.classList.remove('enter'); void it.offsetWidth;
            it.style.setProperty('--k', Math.min(k++, 8));
            it.classList.add('enter');
          }
        }
      });
      if (none) none.hidden = shown > 0 || !list.children.length;
    };
    on(list, 'animationend', e => { if (e.animationName === 'enter') e.target.classList.remove('enter'); });
    chips.forEach(c => on(c, 'click', () => {
      cat = c.dataset.filter;
      chips.forEach(x => { x.setAttribute('aria-pressed', String(x === c)); x.classList.toggle('active', x === c); });
      run();
    }));
    on(q, 'input', run);
    list._refilter = run;
  }
  $$('[data-filterable]').forEach(filterable);
  refreshCounts();

  /* ------------------------------------------------------------ ajax actions (toggle / delete / add) */
  async function post(form) {
    const r = await fetch(form.action, {
      method: 'POST',
      body: new FormData(form),
      headers: { 'X-Requested-With': 'XMLHttpRequest', 'X-CSRFToken': csrf(), Accept: 'application/json' },
      credentials: 'same-origin',
    });
    let data = {};
    try { data = await r.json(); } catch (e) { /* non-json */ }
    if (!r.ok && !data.error) data.error = 'Something went wrong. Please try again.';
    return data;
  }

  function applyDone(item, finished) {
    item.classList.toggle('done', finished);
    item.dataset.cat = finished ? 'done' : 'pending';
    const c = $('.check', item);
    if (c) { c.setAttribute('aria-pressed', String(finished)); c.setAttribute('aria-label', finished ? 'Mark as not done' : 'Mark as done'); }
  }

  function removeItem(item, list) {
    item.classList.add('removing');
    const flip = item.classList.contains('item') && !reduce;
    setTimeout(() => {
      const below = flip
        ? $$('.item', list).filter(i => i !== item && !i.hidden && (item.compareDocumentPosition(i) & Node.DOCUMENT_POSITION_FOLLOWING))
        : [];
      const first = below.map(i => i.getBoundingClientRect().top);
      item.remove();
      below.forEach((i, n) => {
        const dy = first[n] - i.getBoundingClientRect().top;
        if (dy) i.animate([{ transform: `translateY(${dy}px)` }, { transform: 'none' }], { duration: 220, easing: 'cubic-bezier(.23, 1, .32, 1)' });
      });
      refreshCounts();
      list?._refilter?.();
    }, reduce ? 0 : 180);
    refreshCounts();
  }

  on(document, 'submit', async e => {
    const form = e.target;
    if (!(form instanceof HTMLFormElement)) return;

    if (form.dataset.confirm && !form._ok) { e.preventDefault(); ask(form); return; }
    form._ok = false;

    const kind = form.dataset.ajax;
    if (kind) {
      e.preventDefault();
      const item = form.closest('.item, .note');
      const list = form.closest('[data-list]');
      if (kind === 'toggle') {
        const was = item.classList.contains('done');
        applyDone(item, !was);                         // optimistic
        try {
          const d = await post(form);
          if (!d.ok) throw new Error(d.error);
          applyDone(item, d.finished);
          if (list?.dataset.key) bumpStats(list.dataset.key, d.finished);
          if (d.finished) { confetti($('.check', item)); toast('success', form.dataset.doneMsg || 'Nice work, done.'); }
          if (list?.hasAttribute('data-remove-on-done') && d.finished) setTimeout(() => removeItem(item, list), 650);
          else { refreshCounts(); list?._refilter?.(); }
        } catch (err) { applyDone(item, was); toast('danger', err.message || 'Could not update. Check your connection.'); }
      } else if (kind === 'delete') {
        try {
          const d = await post(form);
          if (!d.ok) throw new Error(d.error);
          toast('success', form.dataset.doneMsg || 'Deleted.');
          removeItem(item, list);
        } catch (err) { toast('danger', err.message || 'Could not delete. Check your connection.'); }
      } else if (kind === 'add') {
        const input = $('input[name=title]', form), btn = $('.btn', form);
        if (!input.value.trim()) { input.focus(); input.setAttribute('aria-invalid', 'true'); setTimeout(() => input.removeAttribute('aria-invalid'), 500); return; }
        btn?.classList.add('loading');
        try {
          const d = await post(form);
          if (!d.ok) throw new Error(d.error);
          const target = $(form.dataset.target);
          const tpl = $('#item-tpl').innerHTML
            .replaceAll('__TITLE__', esc(d.title)).replaceAll('__TOGGLE__', d.toggle).replaceAll('__DELETE__', d.delete).replaceAll('__SEARCH__', esc(d.title.toLowerCase()));
          const holder = document.createElement('div');
          holder.innerHTML = tpl.trim();
          const li = holder.firstElementChild;
          li.classList.add('adding');
          const firstDone = $('.item.done', target);
          firstDone ? target.insertBefore(li, firstDone) : target.append(li);
          input.value = '';
          input.focus();
          toast('success', 'Task added.');
          refreshCounts();
        } catch (err) { toast('danger', err.message || 'Could not add the task.'); }
        btn?.classList.remove('loading');
      }
      return;
    }

    if (form.hasAttribute('data-skeleton')) {
      const wrap = $('[data-skeleton-wrap]');
      const q = $('input[name=q]', form);
      if (q && q.value.trim()) wrap?.classList.add('is-loading');
    }
    const b = form.querySelector('.btn[type=submit]');
    if (b && !form.hasAttribute('data-noload')) b.classList.add('loading');
    progStart();
  });

  /* ------------------------------------------------------------ inline validation (blur / change) */
  $$('form[novalidate]').forEach(form => {
    const fields = $$('input.input, textarea.input, select.input', form);
    const message = el => {
      const v = el.validity;
      if (v.valueMissing) return 'This field is required.';
      if (v.typeMismatch) return el.type === 'email' ? 'Enter a valid email address.' : 'Enter a valid value.';
      if (v.tooShort) return `Use at least ${el.minLength} characters.`;
      if (v.tooLong) return `Use at most ${el.maxLength} characters.`;
      if (v.badInput) return 'Enter a valid value.';
      return el.validationMessage || 'Check this field.';
    };
    const show = (el, text) => {
      const wrap = el.closest('.field');
      if (!wrap) return;
      wrap.classList.toggle('invalid', !!text);
      el.setAttribute('aria-invalid', String(!!text));
      let err = $('.field-error[data-live]', wrap);
      if (!text) {
        err?.remove();
        $$('.field-error', wrap).forEach(n => n.remove());
        el.removeAttribute('aria-describedby');
        return;
      }
      if (!err) {
        $$('.field-error', wrap).forEach(n => n.remove());
        err = document.createElement('div');
        err.className = 'field-error';
        err.dataset.live = '1';
        err.id = `${el.id || el.name}-err`;
        err.setAttribute('role', 'alert');
        wrap.append(err);
      }
      err.innerHTML = '<svg class="ic ic-sm" aria-hidden="true"><use href="#i-alert-circle"/></svg>';
      err.append(document.createTextNode(text));
      el.setAttribute('aria-describedby', err.id);
      document.dispatchEvent(new CustomEvent('field-error'));
    };
    const check = el => {
      let text = '';
      if (!el.checkValidity()) text = message(el);
      else if (el.id === 'id_password2' && el.value && el.value !== $('#id_password1', form)?.value) text = 'Passwords do not match.';
      show(el, text);
      return !text;
    };
    fields.forEach(el => {
      on(el, 'blur', () => { if (el.dataset.touched || el.value) check(el); });
      on(el, 'change', () => check(el));
      on(el, 'input', () => {
        el.dataset.touched = '1';
        if (el.closest('.field')?.classList.contains('invalid')) check(el);
        if (el.id === 'id_password1') { const p2 = $('#id_password2', form); if (p2?.value) check(p2); }
      });
    });
  });

  /* ------------------------------------------------------------ due dates */
  function renderDue() {
    const today = new Date(); today.setHours(0, 0, 0, 0);
    $$('[data-due]').forEach(el => {
      const [y, m, d] = el.dataset.due.split('-').map(Number);
      const diff = Math.round((new Date(y, m - 1, d) - today) / 864e5);
      const done = el.closest('.item')?.classList.contains('done');
      let txt, cls = 'ok';
      if (diff < 0) { txt = `Overdue by ${-diff} day${diff === -1 ? '' : 's'}`; cls = 'over'; }
      else if (diff === 0) { txt = 'Due today'; cls = 'soon'; }
      else if (diff === 1) { txt = 'Due tomorrow'; cls = 'soon'; }
      else if (diff < 7) { txt = `Due in ${diff} days`; }
      else txt = 'Due ' + new Date(y, m - 1, d).toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
      el.className = 'due ' + (done ? 'ok' : cls);
      $('span', el).textContent = done ? 'Completed' : txt;
    });
  }
  renderDue();
  setInterval(renderDue, 60000);
  on(document, 'submit', () => setTimeout(renderDue, 700));

  /* greeting + clock on the dashboard */
  const clock = $('[data-clock]');
  if (clock) {
    const t = () => {
      const n = new Date();
      clock.textContent = n.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });
      const dt = $('[data-date]'); if (dt) dt.textContent = n.toLocaleDateString(undefined, { weekday: 'long', month: 'long', day: 'numeric' });
      const g = $('[data-greet]'); if (g) { const h = n.getHours(); g.textContent = h < 5 ? 'Burning the midnight oil' : h < 12 ? 'Good morning' : h < 18 ? 'Good afternoon' : 'Good evening'; }
    };
    t(); setInterval(t, 15000);
  }

  /* ------------------------------------------------------------ form helpers */
  $$('.eye').forEach(b => on(b, 'click', () => {
    const i = b.parentElement.querySelector('input');
    const show = i.type === 'password';
    i.type = show ? 'text' : 'password';
    b.classList.toggle('on', show);
    b.setAttribute('aria-label', show ? 'Hide password' : 'Show password');
  }));
  const pw = $('[data-meter-for]');
  if (pw) {
    const input = document.getElementById(pw.dataset.meterFor), label = $('[data-meter-label]');
    const words = ['', 'Too weak', 'Getting there', 'Good', 'Strong'];
    on(input, 'input', () => {
      const v = input.value;
      let s = 0;
      if (v.length >= 8) s++;
      if (/[a-z]/.test(v) && /[A-Z]/.test(v)) s++;
      if (/\d/.test(v)) s++;
      if (/[^A-Za-z0-9]/.test(v) || v.length >= 14) s++;
      if (!v) s = 0;
      pw.dataset.s = s;
      if (label) label.textContent = words[s];
    });
  }
  $$('textarea[data-autosize]').forEach(t => {
    const fit = () => { t.style.height = 'auto'; t.style.height = Math.min(t.scrollHeight, 150) + 'px'; };
    on(t, 'input', fit); fit();
    addEventListener('load', fit); document.fonts?.ready.then(fit); new ResizeObserver(() => { if (!t.value) fit(); }).observe(t.parentElement);
  });
  $$('[data-copy]').forEach(b => on(b, 'click', async () => {
    try { await navigator.clipboard.writeText(b.dataset.copy); toast('success', 'Copied to clipboard.'); } catch (e) { toast('warning', 'Copy is not available here.'); }
  }));
  $$('[data-focus-on-load]').forEach(i => i.focus({ preventScroll: true }));

  /* pronunciation */
  $$('[data-speak]').forEach(b => on(b, 'click', () => {
    const done = () => b.classList.remove('playing');
    b.classList.add('playing');
    if (b.dataset.speak) {
      const a = new Audio(b.dataset.speak);
      a.onended = done; a.onerror = () => { done(); say(); };
      a.play().catch(() => { done(); say(); });
    } else say();
    function say() {
      if (!('speechSynthesis' in window)) return toast('warning', 'Audio isn’t available for this word.');
      const u = new SpeechSynthesisUtterance(b.dataset.word); u.lang = 'en-US'; u.onend = done;
      b.classList.add('playing'); speechSynthesis.speak(u);
    }
  }));

  /* ------------------------------------------------------------ Lexi */
  const chat = $('#chat');
  if (chat) {
    const log = $('#chat-log'), form = $('#chat-form'), ta = $('textarea', form), send = $('button[type=submit]', form);
    const url = form.action;
    const md = t => {
      if (!t) return '';
      const mathTokens = [];
      let text = String(t);
      const saveMath = (expr, isDisplay) => {
        const id = 'KMATH' + mathTokens.length + 'TOKEN';
        mathTokens.push({ id, expr: expr.trim(), isDisplay });
        return isDisplay ? '\n\n' + id + '\n\n' : id;
      };

      // 1. Math extraction phase (display and inline)
      text = text.replace(/\$\$([\s\S]+?)\$\$/g, (_, m) => saveMath(m, true));
      text = text.replace(/\\\[([\s\S]+?)\\\]/g, (_, m) => saveMath(m, true));
      text = text.replace(/\\\(([\s\S]+?)\\\)/g, (_, m) => saveMath(m, false));
      text = text.replace(/(^|[^\\])\$([^\$\n\r]+?)\$(?!\$)/g, (match, prefix, m) => {
        if (/^\d+(\.\d{1,2})?$/.test(m.trim())) return match;
        return prefix + saveMath(m, false);
      });

      // Highlight syntax: ==highlight== -> <mark>
      text = text.replace(/==([^=\n]+)==/g, '<mark>$1</mark>');

      // 2. Markdown parsing phase (Marked with fallback)
      let html = '';
      if (window.marked && typeof window.marked.parse === 'function') {
        try {
          window.marked.setOptions({ gfm: true, breaks: true });
          html = window.marked.parse(text);
        } catch (e) {
          html = fallbackParse(text);
        }
      } else {
        html = fallbackParse(text);
      }

      // 3. Math hydration via KaTeX
      mathTokens.forEach(({ id, expr, isDisplay }) => {
        let rendered = '';
        if (window.katex && typeof window.katex.renderToString === 'function') {
          try {
            rendered = window.katex.renderToString(expr, {
              displayMode: isDisplay,
              throwOnError: false,
              output: 'htmlAndMathml'
            });
          } catch (err) {
            rendered = isDisplay
              ? `<div class="math-display-fallback">${esc(expr)}</div>`
              : `<span class="math-fallback">${esc(expr)}</span>`;
          }
        } else {
          rendered = isDisplay
            ? `<div class="math-display-fallback">${esc(expr)}</div>`
            : `<span class="math-fallback">${esc(expr)}</span>`;
        }
        html = html.replace(new RegExp('<p>\\s*' + id + '\\s*<\\/p>', 'g'), rendered);
        html = html.split(id).join(rendered);
      });

      // Wrap tables for smooth responsive horizontal scroll
      html = html.replace(/<table>([\s\S]*?)<\/table>/g, '<div class="table-wrap"><table>$1</table></div>');
      return html;
    };

    function fallbackParse(src) {
      let h = esc(src);
      const blocks = [];
      h = h.replace(/```(\w*)\n?([\s\S]*?)```/g, (_, l, c) => {
        blocks.push(`<pre><code class="lang-${l || 'text'}">${c.replace(/\n$/, '')}</code></pre>`);
        return `\u0000${blocks.length - 1}\u0000`;
      });
      h = h.replace(/`([^`\n]+)`/g, '<code>$1</code>');
      h = h.replace(/\*\*([^*\n]+)\*\*/g, '<strong>$1</strong>');
      h = h.replace(/__([^_\n]+)__/g, '<strong>$1</strong>');
      h = h.replace(/(^|[\s(])\*([^*\n]+)\*/g, '$1<em>$2</em>');
      h = h.replace(/(^|[\s(])_([^_\n]+)_/g, '$1<em>$2</em>');
      h = h.replace(/~~([^~\n]+)~~/g, '<del>$1</del>');
      h = h.replace(/==([^=\n]+)==/g, '<mark>$1</mark>');

      const lines = h.split('\n');
      const out = [];
      let inUl = false, inOl = false;

      for (let i = 0; i < lines.length; i++) {
        const line = lines[i];
        const trimmed = line.trim();

        if (/^(\*{3,}|-{3,}|_{3,})$/.test(trimmed)) {
          if (inUl) { out.push('</ul>'); inUl = false; }
          if (inOl) { out.push('</ol>'); inOl = false; }
          out.push('<hr>');
          continue;
        }

        const hMatch = trimmed.match(/^(#{1,6})\s+(.*)$/);
        if (hMatch) {
          if (inUl) { out.push('</ul>'); inUl = false; }
          if (inOl) { out.push('</ol>'); inOl = false; }
          const lvl = hMatch[1].length;
          out.push(`<h${lvl}>${hMatch[2]}</h${lvl}>`);
          continue;
        }

        const ulMatch = trimmed.match(/^([*\-•])\s+(.*)$/);
        if (ulMatch) {
          if (inOl) { out.push('</ol>'); inOl = false; }
          if (!inUl) { out.push('<ul>'); inUl = true; }
          out.push(`<li>${ulMatch[2]}</li>`);
          continue;
        }

        const olMatch = trimmed.match(/^(\d+)\.\s+(.*)$/);
        if (olMatch) {
          if (inUl) { out.push('</ul>'); inUl = false; }
          if (!inOl) { out.push('<ol>'); inOl = true; }
          out.push(`<li>${olMatch[2]}</li>`);
          continue;
        }

        if (trimmed.startsWith('&gt;') || trimmed.startsWith('>')) {
          if (inUl) { out.push('</ul>'); inUl = false; }
          if (inOl) { out.push('</ol>'); inOl = false; }
          out.push(`<blockquote>${trimmed.replace(/^(&gt;|>)\s*/, '')}</blockquote>`);
          continue;
        }

        if (inUl) { out.push('</ul>'); inUl = false; }
        if (inOl) { out.push('</ol>'); inOl = false; }
        if (trimmed !== '') {
          out.push(`<p>${line}</p>`);
        }
      }
      if (inUl) out.push('</ul>');
      if (inOl) out.push('</ol>');

      return out.join('').replace(/\u0000(\d+)\u0000/g, (_, i) => blocks[i]);
    }
    const initial = (document.body.dataset.initial || 'U');

    const enhanceBubble = (b, rawText) => {
      // 1. Convert <pre> blocks into interactive code/prompt cards
      $$('pre', b).forEach(pre => {
        if (pre.closest('.code-card')) return;
        const code = $('code', pre);
        const codeText = code ? code.textContent : pre.textContent;

        let lang = 'code';
        if (code && code.className) {
          const match = code.className.match(/(?:language|lang)-(\w+)/);
          if (match) lang = match[1].toLowerCase();
        }

        const langLabels = {
          prompt: 'Prompt',
          prompts: 'Prompt',
          python: 'Python',
          py: 'Python',
          javascript: 'JavaScript',
          js: 'JavaScript',
          typescript: 'TypeScript',
          ts: 'TypeScript',
          html: 'HTML',
          css: 'CSS',
          json: 'JSON',
          sql: 'SQL',
          bash: 'Bash',
          sh: 'Shell',
          shell: 'Shell',
          cpp: 'C++',
          c: 'C',
          java: 'Java',
          markdown: 'Markdown',
          md: 'Markdown',
          text: 'Text'
        };
        const displayLabel = langLabels[lang] || (lang.charAt(0).toUpperCase() + lang.slice(1));
        const isPrompt = lang === 'prompt' || lang === 'prompts';

        const card = document.createElement('div');
        card.className = 'code-card' + (isPrompt ? ' is-prompt' : '');

        const head = document.createElement('div');
        head.className = 'code-head';
        head.innerHTML = `
          <div class="code-badge">
            <span class="code-dot"></span>
            <span class="code-lang">${esc(displayLabel)}</span>
          </div>
          <div class="code-actions">
            <button class="code-copy-btn" type="button" aria-label="Copy to clipboard" title="Copy to clipboard">
              <svg class="ic ic-xs"><use href="#i-copy"/></svg>
              <span class="copy-lbl">Copy</span>
            </button>
          </div>
        `;

        pre.parentNode.insertBefore(card, pre);
        card.appendChild(head);
        pre.classList.add('code-body');
        card.appendChild(pre);

        const copyBtn = $('.code-copy-btn', head);
        if (copyBtn) {
          on(copyBtn, 'click', async e => {
            e.stopPropagation();
            try {
              await navigator.clipboard.writeText(codeText.replace(/\n$/, ''));
              copyBtn.classList.add('copied');
              copyBtn.innerHTML = `
                <svg class="ic ic-xs"><use href="#i-check"/></svg>
                <span class="copy-lbl">Copied!</span>
              `;
              toast('success', (isPrompt ? 'Prompt' : 'Code') + ' copied to clipboard!');
              setTimeout(() => {
                copyBtn.classList.remove('copied');
                copyBtn.innerHTML = `
                  <svg class="ic ic-xs"><use href="#i-copy"/></svg>
                  <span class="copy-lbl">Copy</span>
                `;
              }, 2000);
            } catch (err) {
              toast('warning', 'Could not copy to clipboard.');
            }
          });
        }
      });

      // 2. Enhance blockquotes to detect callout syntax
      $$('blockquote', b).forEach(bq => {
        const text = bq.innerHTML;
        if (/\[!NOTE\]|<strong>Note:<\/strong>/i.test(text)) {
          bq.classList.add('callout-info');
          bq.innerHTML = text.replace(/\[!NOTE\]\s*/gi, '');
        } else if (/\[!TIP\]|<strong>Tip:<\/strong>/i.test(text)) {
          bq.classList.add('callout-tip');
          bq.innerHTML = text.replace(/\[!TIP\]\s*/gi, '');
        } else if (/\[!WARNING\]|<strong>Warning:<\/strong>/i.test(text)) {
          bq.classList.add('callout-warning');
          bq.innerHTML = text.replace(/\[!WARNING\]\s*/gi, '');
        } else if (/\[!IMPORTANT\]|<strong>Important:<\/strong>/i.test(text)) {
          bq.classList.add('callout-important');
          bq.innerHTML = text.replace(/\[!IMPORTANT\]\s*/gi, '');
        }
      });

      // 3. Add message-level copy button at footer
      if (rawText && !$('.msg-foot', b)) {
        const foot = document.createElement('div');
        foot.className = 'msg-foot';
        foot.innerHTML = `
          <button class="msg-copy" type="button" aria-label="Copy whole answer" title="Copy answer">
            <svg class="ic ic-xs"><use href="#i-copy"/></svg>
            <span>Copy answer</span>
          </button>
        `;
        b.appendChild(foot);

        const footBtn = $('.msg-copy', foot);
        if (footBtn) {
          on(footBtn, 'click', async e => {
            e.stopPropagation();
            try {
              await navigator.clipboard.writeText(rawText);
              footBtn.classList.add('copied');
              footBtn.innerHTML = `
                <svg class="ic ic-xs"><use href="#i-check"/></svg>
                <span>Copied!</span>
              `;
              toast('success', 'Full response copied.');
              setTimeout(() => {
                footBtn.classList.remove('copied');
                footBtn.innerHTML = `
                  <svg class="ic ic-xs"><use href="#i-copy"/></svg>
                  <span>Copy answer</span>
                `;
              }, 2000);
            } catch (err) {
              toast('warning', 'Could not copy to clipboard.');
            }
          });
        }
      }
    };

    // First message: the centered composer glides down to the bottom (FLIP animation).
    const dock = $('#chat-dock');
    const leaveEmpty = () => {
      if (!chat.classList.contains('is-empty')) return;
      const first = dock.getBoundingClientRect();
      chat.classList.remove('is-empty');
      const dy = first.top - dock.getBoundingClientRect().top;
      if (dy && !matchMedia('(prefers-reduced-motion: reduce)').matches) {
        dock.animate([{ transform: `translateY(${dy}px)` }, { transform: 'none' }], { duration: 650, easing: 'cubic-bezier(.22,1,.36,1)' });
      }
    };

    const addMsg = (role, text) => {
      leaveEmpty();
      $('#chat-clear')?.removeAttribute('hidden');
      const m = document.createElement('div');
      m.className = 'msg ' + (role === 'user' ? 'user' : 'bot tone-pink');
      const av = role === 'user' ? esc(initial) : '<svg class="ic"><use href="#i-cap"/></svg>';
      m.innerHTML = `<div class="av">${av}</div><div class="bubble"></div>`;
      const b = $('.bubble', m);
      if (role === 'user') b.textContent = text;
      else {
        b.innerHTML = md(text);
        enhanceBubble(b, text);
      }
      log.append(m);
      log.scrollTop = log.scrollHeight;
      return m;
    };

    $$('.bubble[data-md]', log).forEach(b => {
      const t = b.textContent;
      b.innerHTML = md(t);
      enhanceBubble(b, t);
    });
    log.scrollTop = log.scrollHeight;

    // Send button state management
    if (ta && send) {
      send.disabled = !ta.value.trim();
    }

    // History lives in the browser: nothing to load or save on the server per message.
    const HKEY = 'lexi-chat-' + (chat.dataset.user || 'u');
    let hist = [];
    try { hist = JSON.parse(localStorage.getItem(HKEY) || '[]'); if (!Array.isArray(hist)) hist = []; } catch (e) { hist = []; }
    const saveHist = () => { try { localStorage.setItem(HKEY, JSON.stringify(hist.slice(-30))); } catch (e) {} };
    if (!$$('.msg', log).length) hist.forEach(m => addMsg(m.role === 'user' ? 'user' : 'bot', m.text));
    else { hist = []; saveHist(); }

    const PHASES = ['Thinking', 'Reading your question', 'Working out the answer', 'Putting it together', 'Almost there'];
    let busy = false;
    async function ask(text) {
      if (busy || !text.trim()) return;
      busy = true;
      if (send) send.disabled = true;
      addMsg('user', text.trim());
      ta.value = '';
      ta.dispatchEvent(new Event('input'));
      const t = document.createElement('div');
      t.className = 'msg bot typing tone-pink';
      t.innerHTML = `
        <div class="av lexi-orb" aria-hidden="true"><svg class="ic"><use href="#i-cap"/></svg></div>
        <div class="bubble" role="status" aria-label="Lexi is thinking...">
          <span class="think-text"><span class="think-word">${PHASES[0]}</span><span class="think-dots" aria-hidden="true"><i></i><i></i><i></i></span></span>
        </div>
      `;
      log.append(t); log.scrollTop = log.scrollHeight;
      const word = $('.think-word', t);
      let step = 0;
      const phaseTimer = setInterval(() => {
        step = Math.min(step + 1, PHASES.length - 1);
        word.style.animation = 'none';
        word.classList.add('swap');
        setTimeout(() => { word.textContent = PHASES[step]; word.style.animation = ''; word.classList.remove('swap'); }, 180);
      }, 2200);
      try {
        const fd = new FormData(); fd.append('prompt', text); fd.append('history', JSON.stringify(hist.slice(-6)));
        const r = await fetch(url, { method: 'POST', body: fd, headers: { 'X-Requested-With': 'XMLHttpRequest', 'X-CSRFToken': csrf() }, credentials: 'same-origin' });
        const d = await r.json().catch(() => ({}));
        clearInterval(phaseTimer); t.remove();
        if (d.ok) {
          addMsg('bot', d.reply);
          hist.push({ role: 'user', text: text.trim() }, { role: 'model', text: d.reply });
          saveHist();
        } else { toast('danger', d.error || 'Lexi is unavailable right now.'); }
      } catch (e) {
        clearInterval(phaseTimer); t.remove();
        toast('danger', 'You appear to be offline.');
      }
      busy = false;
      if (send) send.disabled = !ta.value.trim();
      ta.focus();
    }
    on(form, 'submit', e => { e.preventDefault(); e.stopPropagation(); ask(ta.value); }, true);
    on(ta, 'keydown', e => { if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) { e.preventDefault(); ask(ta.value); } });
    on(ta, 'input', () => {
      form.classList.toggle('multiline', ta.scrollHeight > 54);
      if (send && !busy) send.disabled = !ta.value.trim();
    });
    $$('[data-suggest]').forEach(b => on(b, 'click', () => ask(b.dataset.suggest)));
    on($('#chat-clear'), 'click', () => {
      hist = []; try { localStorage.removeItem(HKEY); } catch (e) {}
      location.reload();
    });
  }

  /* ------------------------------------------------------------ auth characters (login / register) */
  const bud = $('[data-buddies]');
  const budForm = $('form.form-grid');
  if (bud && budForm) {
    const chars = $$('.char', bud);
    let target = null, pointer = { x: innerWidth * .7, y: innerHeight * .4 }, raf = 0, moodT = 0, active = null;
    const set = (k, v) => { bud.dataset[k] = v; };
    const aim = () => {
      raf = 0;
      const t = target || pointer, pr = bud.getBoundingClientRect(), mid = pr.left + pr.width / 2;
      chars.forEach(c => {
        const r = $('.face', c).getBoundingClientRect(), cx = r.left + r.width / 2, cy = r.top + r.height / 2;
        const dx = t.x - cx, dy = t.y - cy, d = Math.hypot(dx, dy) || 1, k = Math.min(1, d / 200);
        c.style.setProperty('--px', (dx / d * k).toFixed(3));
        c.style.setProperty('--py', (dy / d * k).toFixed(3));
      });
      bud.style.setProperty('--lean', Math.max(-1, Math.min(1, (t.x - mid) / (innerWidth / 2))).toFixed(3));
    };
    const schedule = () => { if (!raf && !reduce) raf = requestAnimationFrame(aim); };
    const fieldPoint = el => {
      const r = el.getBoundingClientRect(), f = Math.min(1, (el.value || '').length / 24);
      return { x: r.left + 36 + f * Math.max(0, r.width - 72), y: r.top + r.height / 2 };
    };
    const mood = () => {
      const u = $('#id_username', budForm), m = $('.meter', budForm);
      let v = u && u.value ? 'smile' : 'neutral';
      if (m && +m.dataset.s >= 3) v = 'happy';
      set('mood', v);
    };
    on(document, 'pointermove', e => { pointer = { x: e.clientX, y: e.clientY }; if (!target) schedule(); });
    on(budForm, 'focusin', e => {
      const el = e.target.closest('input');
      if (!el) return;
      active = el;
      set('state', el.type === 'password' ? 'password' : 'typing');
      target = fieldPoint(el);
      schedule();
    });
    on(budForm, 'focusout', e => {
      if (e.relatedTarget && budForm.contains(e.relatedTarget)) return;
      active = null; target = null; set('state', 'idle'); schedule();
    });
    on(budForm, 'input', e => {
      const el = e.target.closest('input');
      if (!el) return;
      if (el === active) { target = fieldPoint(el); schedule(); }
      mood();
    });
    on(budForm, 'click', e => {
      const eye = e.target.closest('.eye');
      if (!eye) return;
      setTimeout(() => {                                   // after the show/hide toggle has flipped the input type
        const el = eye.closest('.input-icon')?.querySelector('input');
        if (!el) return;
        active = el; target = fieldPoint(el);
        set('state', el.type === 'password' ? 'password' : 'peek');
        schedule();
      });
    });
    on(document, 'field-error', () => {
      set('mood', 'sad');
      bud.classList.remove('shake'); void bud.offsetWidth; bud.classList.add('shake');
      clearTimeout(moodT);
      moodT = setTimeout(() => { bud.classList.remove('shake'); mood(); }, 1400);
    });
    on(budForm, 'submit', () => { set('state', 'success'); set('mood', 'happy'); });
    if ($('.form-alert, .field.invalid', budForm)) document.dispatchEvent(new CustomEvent('field-error'));
    schedule();
  }

  /* ------------------------------------------------------------ connectivity */
  on(window, 'offline', () => toast('warning', 'You are offline. Changes will fail until you reconnect.'));
  on(window, 'online', () => toast('success', 'Back online.'));
})();
