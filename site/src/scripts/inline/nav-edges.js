// Navigation rows scroll sideways on narrow screens. Fade the edge where more items are hidden,
// and start with the current page's item in view. Runs before first paint, so nothing jumps.
for (const ul of document.querySelectorAll(".site-header nav ul")) {
  const cur = ul.querySelector("[aria-current]");
  if (cur && ul.scrollWidth > ul.clientWidth) {
    const a = cur.getBoundingClientRect(), u = ul.getBoundingClientRect();
    if (a.left < u.left || a.right > u.right) ul.scrollLeft += a.left - u.left - (u.width - a.width) / 2;
  }
  const edges = () => {
    const max = ul.scrollWidth - ul.clientWidth;
    ul.toggleAttribute("data-more-left", ul.scrollLeft > 1);
    ul.toggleAttribute("data-more-right", ul.scrollLeft < max - 1);
  };
  edges();
  ul.addEventListener("scroll", edges, { passive: true });
  addEventListener("resize", edges, { passive: true });
}
