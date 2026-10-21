/* Custom select lists and date picker, so every dropdown on the site matches the design instead of the browser's default. */
(() => {
  'use strict';
  const CHEV = '<svg viewBox="0 0 256 256" aria-hidden="true"><path fill="currentColor" d="M213.66 101.66l-80 80a8 8 0 0 1-11.32 0l-80-80a8 8 0 0 1 11.32-11.32L128 164.69l74.34-74.35a8 8 0 0 1 11.32 11.32z"/></svg>';
  const TICK = '<svg viewBox="0 0 256 256" aria-hidden="true"><path fill="currentColor" d="M229.66 77.66l-128 128a8 8 0 0 1-11.32 0l-56-56a8 8 0 0 1 11.32-11.32L96 188.69 218.34 66.34a8 8 0 0 1 11.32 11.32z"/></svg>';
  const el = (tag, cls, html) => { const n = document.createElement(tag); if (cls) n.className = cls; if (html != null) n.innerHTML = html; return n; };
  const esc = s => String(s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  let openPop = null;

  document.addEventListener('pointerdown', e => { if (openPop && !openPop.wrap.contains(e.target)) openPop.close(); });
  document.addEventListener('keydown', e => { if (e.key === 'Escape' && openPop) { e.stopPropagation(); openPop.close(true); } }, true);

  /** Shared open/close: the panel opens below the trigger, or above when there is no room. */
  function popup(wrap, btn, panel, onOpen) {
    const api = {
      wrap,
      open() {
        if (openPop && openPop !== api) openPop.close();
        if (onOpen) onOpen();                         // fill the panel first so its height is known
        wrap.classList.add('open');
        btn.setAttribute('aria-expanded', 'true');
        const r = btn.getBoundingClientRect();
        const need = Math.min(panel.scrollHeight, 380) + 12;
        wrap.classList.toggle('up', innerHeight - r.bottom < need && r.top > need);
        openPop = api;
      },
      close(refocus) {
        wrap.classList.remove('open');
        btn.setAttribute('aria-expanded', 'false');
        if (openPop === api) openPop = null;
        if (refocus) btn.focus();
      },
      toggle() { wrap.classList.contains('open') ? api.close() : api.open(); },
    };
    return api;
  }

  /* ------------------------------------------------------------------ select */
  function enhanceSelect(sel) {
    if (sel.dataset.cs || sel.multiple) return;
    sel.dataset.cs = '1';
    const wrap = el('div', 'cs');
    const btn = el('button', 'input cs-btn', '<span class="cs-val"></span><span class="cs-chev">' + CHEV + '</span>');
    btn.type = 'button';
    btn.setAttribute('aria-haspopup', 'listbox');
    btn.setAttribute('aria-expanded', 'false');
    if (sel.id) document.querySelectorAll('label[for="' + sel.id + '"]').forEach(l => l.addEventListener('click', e => { e.preventDefault(); btn.focus(); }));
    const panel = el('div', 'cs-panel');
    panel.setAttribute('role', 'listbox');
    sel.parentNode.insertBefore(wrap, sel);
    wrap.append(sel, btn, panel);
    sel.classList.add('cs-native');
    sel.tabIndex = -1;
    sel.setAttribute('aria-hidden', 'true');

    let active = -1;
    const items = () => [...panel.children];
    const val = btn.querySelector('.cs-val');

    function sync() {
      const opt = sel.options[sel.selectedIndex];
      val.textContent = opt ? opt.text : '';
      val.classList.toggle('ph', !opt || !opt.value);
      items().forEach((li, i) => { const on = i === sel.selectedIndex; li.classList.toggle('sel', on); li.setAttribute('aria-selected', on); });
    }
    function build() {
      panel.innerHTML = '';
      [...sel.options].forEach((o, i) => {
        const li = el('div', 'cs-opt', '<span>' + esc(o.text) + '</span>' + TICK);
        li.setAttribute('role', 'option');
        if (o.disabled) li.classList.add('dis');
        li.addEventListener('click', () => choose(i));
        li.addEventListener('pointermove', () => highlight(i));
        panel.appendChild(li);
      });
      sync();
    }
    function highlight(i, scroll) {
      const list = items();
      if (!list.length) return;
      active = Math.max(0, Math.min(list.length - 1, i));
      list.forEach((li, k) => li.classList.toggle('act', k === active));
      if (scroll) list[active].scrollIntoView({ block: 'nearest' });
    }
    function choose(i) {
      if (sel.options[i] && sel.options[i].disabled) return;
      if (sel.selectedIndex !== i) {
        sel.selectedIndex = i;
        sel.dispatchEvent(new Event('input', { bubbles: true }));
        sel.dispatchEvent(new Event('change', { bubbles: true }));
      }
      sync();
      api.close(true);
    }
    const api = popup(wrap, btn, panel, () => highlight(Math.max(0, sel.selectedIndex), true));

    btn.addEventListener('click', () => api.toggle());
    btn.addEventListener('keydown', e => {
      const isOpen = wrap.classList.contains('open');
      if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
        e.preventDefault();
        if (!isOpen) api.open(); else highlight(active + (e.key === 'ArrowDown' ? 1 : -1), true);
      } else if (e.key === 'Home' && isOpen) { e.preventDefault(); highlight(0, true); }
      else if (e.key === 'End' && isOpen) { e.preventDefault(); highlight(items().length - 1, true); }
      else if ((e.key === 'Enter' || e.key === ' ') && isOpen) { e.preventDefault(); choose(active); }
      else if (e.key === 'Tab' && isOpen) api.close();
      else if (e.key.length === 1 && /\S/.test(e.key)) {
        const i = [...sel.options].findIndex(o => o.text.toLowerCase().startsWith(e.key.toLowerCase()));
        if (i > -1) { if (!isOpen) api.open(); highlight(i, true); }
      }
    });
    sel.addEventListener('change', sync);
    new MutationObserver(build).observe(sel, { childList: true });
    if (sel.form) sel.form.addEventListener('reset', () => setTimeout(sync));
    build();
  }

  /* -------------------------------------------------------------------- date */
  const MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];
  const DAYS = ['Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa', 'Su'];
  const pad = n => String(n).padStart(2, '0');
  const iso = d => d.getFullYear() + '-' + pad(d.getMonth() + 1) + '-' + pad(d.getDate());
  const parse = v => { const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(v || ''); return m ? new Date(+m[1], +m[2] - 1, +m[3]) : null; };
  const nice = d => d.toLocaleDateString(undefined, { weekday: 'short', day: 'numeric', month: 'short', year: 'numeric' });

  function enhanceDate(inp) {
    if (inp.dataset.cs) return;
    inp.dataset.cs = '1';
    const wrap = el('div', 'cs cs-date');
    const btn = el('button', 'input cs-btn' + (inp.closest('.input-icon') ? ' has-icon' : ''), '<span class="cs-val"></span><span class="cs-chev">' + CHEV + '</span>');
    btn.type = 'button';
    btn.setAttribute('aria-haspopup', 'dialog');
    btn.setAttribute('aria-expanded', 'false');
    const panel = el('div', 'cs-panel cs-cal');
    inp.parentNode.insertBefore(wrap, inp);
    wrap.append(inp, btn, panel);
    inp.classList.add('cs-native');
    inp.tabIndex = -1;
    inp.setAttribute('aria-hidden', 'true');
    const val = btn.querySelector('.cs-val');

    let view = parse(inp.value) || new Date();
    view = new Date(view.getFullYear(), view.getMonth(), 1);

    function sync() {
      const d = parse(inp.value);
      val.textContent = d ? nice(d) : (inp.getAttribute('placeholder') || 'Pick a date');
      val.classList.toggle('ph', !d);
    }
    function pick(d) {
      inp.value = iso(d);
      inp.dispatchEvent(new Event('input', { bubbles: true }));
      inp.dispatchEvent(new Event('change', { bubbles: true }));
      sync();
      api.close(true);
    }
    function render() {
      const sel = parse(inp.value), today = new Date();
      const first = new Date(view.getFullYear(), view.getMonth(), 1);
      const lead = (first.getDay() + 6) % 7;
      const count = new Date(view.getFullYear(), view.getMonth() + 1, 0).getDate();
      let h = '<div class="cal-head"><button type="button" class="cal-nav" data-m="-1" aria-label="Previous month">' + CHEV + '</button><b>' + MONTHS[view.getMonth()] + ' ' + view.getFullYear() + '</b><button type="button" class="cal-nav nx" data-m="1" aria-label="Next month">' + CHEV + '</button></div><div class="cal-grid">';
      DAYS.forEach(d => { h += '<span class="cal-dow">' + d + '</span>'; });
      for (let i = 0; i < lead; i++) h += '<span></span>';
      for (let d = 1; d <= count; d++) {
        const cur = new Date(view.getFullYear(), view.getMonth(), d);
        const cls = 'cal-day' + (sel && iso(cur) === iso(sel) ? ' sel' : '') + (iso(cur) === iso(today) ? ' today' : '');
        h += '<button type="button" class="' + cls + '" data-d="' + iso(cur) + '">' + d + '</button>';
      }
      h += '</div><div class="cal-foot"><button type="button" data-today>Today</button></div>';
      panel.innerHTML = h;
    }
    const api = popup(wrap, btn, panel, () => { const d = parse(inp.value) || new Date(); view = new Date(d.getFullYear(), d.getMonth(), 1); render(); });
    btn.addEventListener('click', () => api.toggle());
    panel.addEventListener('click', e => {
      const nav = e.target.closest('[data-m]'), day = e.target.closest('[data-d]');
      if (nav) { view = new Date(view.getFullYear(), view.getMonth() + +nav.dataset.m, 1); render(); }
      else if (day) pick(parse(day.dataset.d));
      else if (e.target.closest('[data-today]')) pick(new Date());
    });
    inp.addEventListener('change', sync);
    sync();
  }

  function scan() {
    document.querySelectorAll('select:not([data-cs])').forEach(enhanceSelect);
    document.querySelectorAll('input[type="date"]:not([data-cs])').forEach(enhanceDate);
  }
  scan();
  // pages swap in fragments after load, so enhance new fields as they appear
  new MutationObserver(m => { if (m.some(r => r.addedNodes.length)) scan(); }).observe(document.body, { childList: true, subtree: true });
})();
