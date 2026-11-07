// The reader's light/dark choice, applied before first paint so the page never flashes the other theme.
try {
  const t = localStorage.getItem("theme");
  if (t === "dark" || t === "light") document.documentElement.dataset.theme = t;
} catch {}
