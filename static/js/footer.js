/* The site footer: plays its entrance when the footer scrolls into view, and runs the back-to-top buttons. */
(() => {
  'use strict';
  const foot = document.getElementById('siteFoot');
  if (!foot) return;
  const reduce = matchMedia('(prefers-reduced-motion: reduce)').matches;

  const show = () => foot.classList.add('in');
  if (!('IntersectionObserver' in window)) show();
  else {
    const io = new IntersectionObserver(entries => {
      if (entries.some(e => e.isIntersecting)) { show(); io.disconnect(); }
    }, { threshold: 0.15 });
    io.observe(foot);
  }

  const toTop = e => { e.preventDefault(); scrollTo({ top: 0, behavior: reduce ? 'auto' : 'smooth' }); };
  foot.querySelectorAll('.site-foot-up, [data-foot-top]').forEach(b => b.addEventListener('click', toTop));
})();
