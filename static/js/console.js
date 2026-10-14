/* Admin console: theme toggle, mobile menu, copy buttons, show-password. No dependencies. */
(() => {
  'use strict';
  const $$ = (s, r = document) => [...r.querySelectorAll(s)];
  const root = document.documentElement;

  // theme (shares the student site's `theme` key)
  $$('[data-cs-theme]').forEach(b => b.addEventListener('click', () => {
    const cur = root.dataset.theme || (matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
    const next = cur === 'dark' ? 'light' : 'dark';
    root.dataset.theme = next;
    try { localStorage.setItem('theme', next); } catch (e) { /* private mode */ }
  }));

  // mobile sidebar
  const setOpen = open => {
    document.body.classList.toggle('cs-open', open);
    $$('[data-cs-menu]').forEach(b => b.setAttribute('aria-expanded', String(open)));
  };
  $$('[data-cs-menu]').forEach(b => b.addEventListener('click', () => setOpen(!document.body.classList.contains('cs-open'))));
  $$('[data-cs-close]').forEach(el => el.addEventListener('click', () => setOpen(false)));
  document.addEventListener('keydown', e => { if (e.key === 'Escape') setOpen(false); });

  // copy to clipboard
  $$('[data-copy]').forEach(b => b.addEventListener('click', async () => {
    const label = b.querySelector('span');
    try {
      await navigator.clipboard.writeText(b.dataset.copy);
      b.classList.add('done');
      if (label) label.textContent = 'Copied';
      setTimeout(() => { b.classList.remove('done'); if (label) label.textContent = 'Copy'; }, 1800);
    } catch (e) { if (label) label.textContent = 'Press Ctrl+C'; }
  }));

  // show / hide password
  $$('[data-cs-eye]').forEach(b => b.addEventListener('click', () => {
    const input = b.parentElement.querySelector('input');
    const show = input.type === 'password';
    input.type = show ? 'text' : 'password';
    b.setAttribute('aria-label', show ? 'Hide password' : 'Show password');
  }));

  // close the sort menu when clicking elsewhere
  document.addEventListener('click', e => { $$('.cs-menu[open]').forEach(d => { if (!d.contains(e.target)) d.removeAttribute('open'); }); });
})();
