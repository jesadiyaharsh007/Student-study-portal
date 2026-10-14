/* Admin-only behaviour.
   1. Custom dropdown for <select> (replaces the browser's default list).
   2. Django's filter sidebar (a stack of <details>) becomes compact dropdown chips. */
(() => {
  'use strict';
  const $$ = (s, r = document) => [...r.querySelectorAll(s)];

  /* ------------------------------------------------------------ 1. custom select */
  let uid = 0;
  const closeAll = except => $$('.sd-select.open').forEach(w => { if (w !== except) close(w); });
  function close(w) {
    w.classList.remove('open');
    w.querySelector('.sd-select-btn').setAttribute('aria-expanded', 'false');
  }

  function enhance(select) {
    if (select.dataset.sd || select.multiple || select.size > 1 || select.classList.contains('admin-autocomplete')
        || select.closest('.select2') || select.classList.contains('select2-hidden-accessible')) return;
    select.dataset.sd = '1';
    const id = 'sd-select-' + (++uid);

    const wrap = document.createElement('div');
    wrap.className = 'sd-select';
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'sd-select-btn';
    btn.setAttribute('aria-haspopup', 'listbox');
    btn.setAttribute('aria-expanded', 'false');
    btn.setAttribute('aria-controls', id);
    const label = document.createElement('span');
    label.className = 'sd-select-label';
    btn.append(label);
    const list = document.createElement('ul');
    list.className = 'sd-select-list';
    list.id = id;
    list.setAttribute('role', 'listbox');

    select.parentNode.insertBefore(wrap, select);
    wrap.append(btn, list, select);
    select.classList.add('sd-native');
    select.tabIndex = -1;
    select.setAttribute('aria-hidden', 'true');

    const options = () => [...select.options];
    const sync = () => {
      const cur = select.options[select.selectedIndex];
      label.textContent = cur ? cur.text : '';
      wrap.classList.toggle('is-placeholder', !!cur && (cur.value === '' || /^-+\s/.test(cur.text)));
      list.querySelectorAll('li').forEach((li, i) => {
        const on = i === select.selectedIndex;
        li.classList.toggle('selected', on);
        li.setAttribute('aria-selected', String(on));
      });
    };
    options().forEach((o, i) => {
      const li = document.createElement('li');
      li.setAttribute('role', 'option');
      li.textContent = o.text;
      li.tabIndex = -1;
      if (o.disabled) li.setAttribute('aria-disabled', 'true');
      li.addEventListener('click', () => choose(i));
      list.append(li);
    });

    function choose(i) {
      if (options()[i]?.disabled) return;
      select.selectedIndex = i;
      select.dispatchEvent(new Event('change', { bubbles: true }));
      sync(); close(wrap); btn.focus();
    }
    function open() {
      closeAll(wrap);
      wrap.classList.add('open');
      btn.setAttribute('aria-expanded', 'true');
      (list.querySelector('li.selected') || list.firstElementChild)?.scrollIntoView({ block: 'nearest' });
    }
    function move(dir) {
      const items = [...list.querySelectorAll('li:not([aria-disabled])')];
      const at = items.indexOf(document.activeElement);
      items[(at + dir + items.length) % items.length]?.focus();
    }

    btn.addEventListener('click', () => (wrap.classList.contains('open') ? close(wrap) : open()));
    btn.addEventListener('keydown', e => {
      if (['ArrowDown', 'ArrowUp'].includes(e.key)) { e.preventDefault(); open(); (list.querySelector('li.selected') || list.firstElementChild)?.focus(); }
    });
    list.addEventListener('keydown', e => {
      if (e.key === 'ArrowDown') { e.preventDefault(); move(1); }
      else if (e.key === 'ArrowUp') { e.preventDefault(); move(-1); }
      else if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); const i = [...list.children].indexOf(document.activeElement); if (i >= 0) choose(i); }
      else if (e.key === 'Escape') { close(wrap); btn.focus(); }
      else if (e.key === 'Tab') close(wrap);
    });
    select.addEventListener('change', sync);        // keeps in step when Django's scripts change it
    sync();
  }

  $$('select').forEach(enhance);
  document.addEventListener('click', e => { if (!e.target.closest('.sd-select')) closeAll(); });
  document.addEventListener('keydown', e => { if (e.key === 'Escape') closeAll(); });

  /* search help text becomes the placeholder (keeps the toolbar to one tidy row) */
  const help = document.getElementById('searchbar_helptext');
  const box = document.getElementById('searchbar');
  if (help && box && !box.placeholder) box.placeholder = help.textContent.trim();

  /* ------------------------------------------------------------ 2. filter chips */
  const bar = document.getElementById('changelist-filter');
  if (!bar) return;
  const groups = [...bar.querySelectorAll('details[data-filter-title]')];
  const cap = s => s.charAt(0).toUpperCase() + s.slice(1);

  groups.forEach(d => {
    d.removeAttribute('open');
    const links = [...d.querySelectorAll('li a')];
    const selected = d.querySelector('li.selected a');
    const active = !!selected && selected !== links[0];            // the first choice is always "All"
    const title = cap(d.dataset.filterTitle || '');
    d.querySelector('summary').textContent = active ? `${title}: ${selected.textContent.trim()}` : title;
    d.classList.toggle('is-active', active);
    d.addEventListener('toggle', () => { if (d.open) groups.forEach(o => { if (o !== d) o.removeAttribute('open'); }); });
  });

  document.addEventListener('click', e => { groups.forEach(d => { if (!d.contains(e.target)) d.removeAttribute('open'); }); });
  document.addEventListener('keydown', e => { if (e.key === 'Escape') groups.forEach(d => d.removeAttribute('open')); });
})();
