// Hover / touch / keyboard readouts for the build-time SVG charts.
// Every value is also in each chart's table view; this only makes reading easier.

interface TipRow { slot: number; value: string; name: string; kind?: string }
interface LineData { years: string[]; series: { name: string; slot: number; values: ({ t: string; k: string } | null)[] }[] }
interface ColumnData { columns: { title: string; rows: TipRow[] }[] }

const tip = document.querySelector<HTMLDivElement>(".tooltip")!;

function showTip(title: string, rows: TipRow[], clientX: number, clientY: number) {
  tip.replaceChildren();
  const h = document.createElement("div");
  h.className = "tip-title";
  h.textContent = title;
  tip.append(h);
  for (const r of rows) {
    const row = document.createElement("div");
    row.className = "tip-row";
    const key = document.createElement("span");
    key.className = "tip-key";
    key.style.background = `var(--s${r.slot})`;
    const val = document.createElement("strong");
    val.textContent = r.value;
    const name = document.createElement("span");
    name.className = "tip-name";
    name.textContent = r.kind && r.kind !== "Actual" ? `${r.name} (${r.kind})` : r.name;
    row.append(key, val, name);
    tip.append(row);
  }
  tip.hidden = false;
  const pad = 12;
  const { width, height } = tip.getBoundingClientRect();
  let x = clientX + pad;
  if (x + width > window.innerWidth - 8) x = clientX - width - pad;
  let y = clientY - height - pad;
  if (y < 8) y = clientY + pad;
  tip.style.transform = `translate(${Math.max(8, x)}px, ${y}px)`;
}
const hideTip = () => { tip.hidden = true; };

function toViewBoxX(svg: SVGSVGElement, clientX: number): number {
  const ctm = svg.getScreenCTM();
  if (!ctm) return 0;
  const pt = new DOMPoint(clientX, 0).matrixTransform(ctm.inverse());
  return pt.x;
}

function setupLine(fig: HTMLElement, data: LineData) {
  fig.querySelectorAll<SVGSVGElement>("svg.plot").forEach((svg) => {
    const xs = (svg.dataset.xs ?? "").split(",").map(Number);
    const cross = svg.querySelector<SVGLineElement>(".crosshair");
    let current = -1;
    const show = (i: number, clientX: number, clientY: number) => {
      current = i;
      cross?.setAttribute("x1", String(xs[i]));
      cross?.setAttribute("x2", String(xs[i]));
      cross?.setAttribute("visibility", "visible");
      const rows = data.series
        .map((s) => ({ s, v: s.values[i] }))
        .filter(({ v }) => v)
        .map(({ s, v }) => ({ slot: s.slot, value: v!.t, name: s.name, kind: v!.k }));
      showTip(data.years[i], rows.length ? rows : [{ slot: 0, value: "–", name: "No figure" }], clientX, clientY);
    };
    const nearest = (vx: number) => xs.reduce((best, x, i) => (Math.abs(x - vx) < Math.abs(xs[best] - vx) ? i : best), 0);
    svg.addEventListener("pointermove", (e) => show(nearest(toViewBoxX(svg, e.clientX)), e.clientX, e.clientY));
    svg.addEventListener("pointerdown", (e) => show(nearest(toViewBoxX(svg, e.clientX)), e.clientX, e.clientY));
    svg.addEventListener("pointerleave", () => { cross?.setAttribute("visibility", "hidden"); hideTip(); });
    svg.tabIndex = 0;
    svg.addEventListener("keydown", (e) => {
      if (e.key !== "ArrowLeft" && e.key !== "ArrowRight") return;
      e.preventDefault();
      const i = Math.max(0, Math.min(xs.length - 1, (current < 0 ? xs.length - 1 : current) + (e.key === "ArrowLeft" ? -1 : 1)));
      const r = svg.getBoundingClientRect();
      show(i, r.left + (xs[i] / (svg.viewBox.baseVal.width || 1)) * r.width, r.top + 20);
    });
    svg.addEventListener("blur", () => { cross?.setAttribute("visibility", "hidden"); hideTip(); });
  });
}

function setupColumns(fig: HTMLElement, data: ColumnData) {
  fig.querySelectorAll<SVGGElement>("[data-col]").forEach((g) => {
    const i = Number(g.dataset.col);
    const col = data.columns[i];
    const show = (x: number, y: number) => {
      fig.querySelectorAll("[data-col].active").forEach((el) => el.classList.remove("active"));
      g.classList.add("active");
      showTip(col.title, col.rows, x, y);
    };
    g.addEventListener("pointermove", (e) => show(e.clientX, e.clientY));
    g.addEventListener("pointerdown", (e) => show(e.clientX, e.clientY));
    g.addEventListener("pointerleave", () => { g.classList.remove("active"); hideTip(); });
    g.addEventListener("focus", () => { const r = g.getBoundingClientRect(); show(r.left + r.width / 2, r.top); });
    g.addEventListener("blur", () => { g.classList.remove("active"); hideTip(); });
  });
}

document.querySelectorAll<HTMLElement>("figure.chart").forEach((fig) => {
  const el = fig.querySelector<HTMLScriptElement>("script.chart-data");
  if (!el?.textContent) return;
  const data = JSON.parse(el.textContent);
  if ("years" in data) setupLine(fig, data);
  else if ("columns" in data) setupColumns(fig, data);
});
document.addEventListener("scroll", hideTip, { passive: true });
