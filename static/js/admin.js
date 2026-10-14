/* Admin-only behaviour: turn Django's filter sidebar (a stack of <details>) into compact dropdown chips. */
(() => {
  'use strict';
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
