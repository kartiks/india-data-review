// Filter a list as you type: <input data-filter="CSS selector of the items">
document.querySelectorAll<HTMLInputElement>("input[data-filter]").forEach((input) => {
  const items = () => document.querySelectorAll<HTMLElement>(input.dataset.filter!);
  input.addEventListener("input", () => {
    const q = input.value.trim().toLowerCase();
    items().forEach((el) => { el.hidden = !!q && !el.textContent!.toLowerCase().includes(q); });
  });
});
