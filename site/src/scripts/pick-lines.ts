// The script for components/PickLines.astro: redraws the chart, chips, notes and table as lines are added or
// removed, and keeps the choice in the address (#show=key,key). The component draws the starting set at build time
// and passes its data in <script type="application/json" class="pick-data">; it calls setupPickLines on each figure.
import { AXIS_FORMATS, assignSlots, linePlots, slotColor, yearsWithData, type AxisFormat } from "../lib/line-plot";
import { setupLine } from "./charts";

/** One line as components/PickLines.astro packs it: values, their formatted text and estimate labels. */
export interface Opt { key: string; name: string; note: string; v: (number | null)[]; t: (string | null)[]; k: string[]; kt: string[] }
export interface Data { years: string[]; options: Opt[]; reference: Opt | null; initial: string[]; max: number; axis: AxisFormat; label: string }

/** The keys an address names ("#show=a,b"): null if it names none ("#show" absent), [] for an empty "#show=". */
export function keysFromHash(hash: string): string[] | null {
  const keys = hash.startsWith("#show") ? new URLSearchParams(hash.slice(1)).get("show") : null;
  return keys == null ? null : keys.split(",").filter(Boolean);
}

/** Make one PickLines figure interactive: chips, the Choose panel, redrawing, the table and the address. */
export function setupPickLines(fig: HTMLElement) {
  const data = JSON.parse(fig.querySelector(".pick-data")!.textContent!) as Data;
  const ref = data.reference;
  const byKey = new Map([...data.options, ...(ref ? [ref] : [])].map((o) => [o.key, o]));
  const pick = (keys: string[], current: { key: string; slot: number }[] = []) =>
    assignSlots(keys, (k) => byKey.has(k), ref?.key, data.max, current);
  let chosen: { key: string; slot: number }[] = [];

  const chips = fig.querySelector<HTMLUListElement>(".chips")!;
  const boxes = [...fig.querySelectorAll<HTMLInputElement>(".choose input[type=checkbox]")];
  const summary = fig.querySelector<HTMLElement>(".choose summary")!;
  const plots = fig.querySelector<HTMLDivElement>(".plots")!;
  const notes = fig.querySelector<HTMLUListElement>(".pick-notes")!;
  const table = fig.querySelector<HTMLTableElement>(".table-view table")!;
  const limit = fig.querySelector<HTMLElement>(".limit")!;
  const el = <K extends keyof HTMLElementTagNameMap>(tag: K, text?: string) => {
    const e = document.createElement(tag);
    if (text != null) e.textContent = text;
    return e;
  };
  // A table cell: the value, after its estimate label (muted) so the numbers stay right-aligned.
  const cell = (t: string | null, k: string, title: string) => {
    const td = el("td");
    if (t != null && k) td.append(Object.assign(el("span", k), { className: "est", title }));
    if (t != null) td.append(t);
    else td.append(Object.assign(el("span"), { className: "no-data", innerHTML: '<span aria-hidden="true">–</span><span class="sr-only">no data</span>' }));
    return td;
  };

  /** Redraw everything from `chosen`. `focusKey`: after a chip is removed, the chip to move focus to ("" = none
   *  left, so focus goes to the Choose button). */
  const render = (focusKey?: string) => {
    const sel = chosen.map((c) => ({ c, o: byKey.get(c.key)! }));
    const years = yearsWithData(data.years, sel.map(({ o }) => ({ values: o.v })));

    // Chart (hidden when nothing is chosen, rather than an empty axis)
    plots.innerHTML = sel.length ? linePlots(years, sel.map(({ c, o }) => ({
      name: o.name, color: slotColor(c.slot), dashed: c.slot === 0, values: o.v.slice(0, years.length),
    })), AXIS_FORMATS[data.axis], data.label) : "";
    setupLine(fig, {
      years,
      series: sel.map(({ c, o }) => ({
        name: o.name, slot: c.slot, color: slotColor(c.slot),
        values: years.map((_, i) => (o.t[i] == null ? null : { t: o.t[i]!, k: o.k[i] })),
      })),
    });
    fig.querySelector<HTMLElement>(".empty")!.hidden = sel.length > 0;
    fig.querySelector<HTMLElement>(".table-view")!.hidden = sel.length === 0;

    // Chips (also the legend)
    chips.replaceChildren(...sel.map(({ c, o }) => {
      const li = el("li");
      const b = el("button");
      b.type = "button";
      b.className = "chip";
      b.dataset.key = o.key;
      b.setAttribute("aria-label", `Remove ${o.name}`);
      const sw = el("span");
      sw.className = c.slot === 0 ? "sw dashed" : "sw";
      if (c.slot !== 0) sw.style.background = slotColor(c.slot);
      sw.setAttribute("aria-hidden", "true");
      const x = el("span", "×");
      x.className = "x";
      x.setAttribute("aria-hidden", "true");
      b.append(sw, o.name, x);
      li.append(b);
      return li;
    }));
    if (focusKey != null) (chips.querySelector<HTMLButtonElement>(`[data-key="${focusKey}"]`) ?? summary).focus();

    // Checkboxes: ticked for lines shown; the rest disabled at the limit (the reference line never is).
    const full = chosen.filter((c) => c.key !== ref?.key).length >= data.max;
    for (const b of boxes) {
      b.checked = chosen.some((c) => c.key === b.value);
      b.disabled = full && !b.checked && b.value !== ref?.key;
    }
    limit.textContent = full ? `Up to ${data.max} at once: untick one to add another.` : "";

    // Notes for the lines shown
    notes.replaceChildren(...[...new Set(sel.map(({ o }) => o.note).filter(Boolean))].map((n) => el("li", n)));

    // Table
    const head = el("tr");
    head.append(el("th", "Year"), ...sel.map(({ o }) => el("th", o.name)));
    const body = years.map((yr, i) => {
      const tr = el("tr");
      tr.append(el("td", yr), ...sel.map(({ o }) => cell(o.t[i], o.k[i], o.kt[i])));
      return tr;
    });
    table.tHead!.replaceChildren(head);
    table.tBodies[0].replaceChildren(...body);

    // Address: #show=… when the choice differs from the starting set; otherwise drop only our own hash.
    const keys = chosen.map((c) => c.key);
    const same = keys.length === data.initial.length && keys.every((k, i) => k === data.initial[i]);
    if (!same) history.replaceState(null, "", `#show=${keys.join(",")}`);
    else if (location.hash.startsWith("#show")) history.replaceState(null, "", location.pathname + location.search);
  };

  // No "#show" = the starting set; an empty "#show=" = an empty chart; a list naming nothing we know = the
  // starting set.
  const fromAddress = () => {
    const keys = keysFromHash(location.hash);
    chosen = pick(keys ?? data.initial);
    if (!chosen.length && keys?.length) chosen = pick(data.initial);
    render();
  };
  fromAddress();
  // Going back to the page's own address restores the starting set; other in-page links leave the choice alone.
  window.addEventListener("hashchange", () => { if (location.hash === "" || location.hash.startsWith("#show")) fromAddress(); });
  fig.querySelector<HTMLElement>(".choose")!.hidden = false;

  chips.addEventListener("click", (e) => {
    const b = (e.target as HTMLElement).closest<HTMLButtonElement>("button.chip");
    const i = chosen.findIndex((c) => c.key === b?.dataset.key);
    if (i < 0) return;
    chosen.splice(i, 1);
    render(chosen[i]?.key ?? chosen[i - 1]?.key ?? "");
  });
  for (const b of boxes) {
    b.addEventListener("change", () => {
      chosen = b.checked ? pick([b.value], chosen) : chosen.filter((c) => c.key !== b.value);
      render();
    });
  }
  fig.querySelector(".reset")!.addEventListener("click", () => { chosen = pick(data.initial); render(); });
  fig.querySelector(".clear")!.addEventListener("click", () => { chosen = []; render(); });
}
