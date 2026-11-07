// The script for components/StateMap.astro: switches the metric the map is coloured by (the first is coloured at
// build time), and shows the state under the pointer, tapped or focused. The component passes its data in
// <script type="application/json" class="map-data">; it calls setupStateMap on each figure.

/** Make one StateMap figure interactive: the metric buttons, the legend and the hover/tap/focus readout. */
export function setupStateMap(fig: HTMLElement) {
  const data = JSON.parse(fig.querySelector(".map-data")!.textContent!) as {
    metrics: { id: string; title: string; note: string; legend: string[]; states: Record<string, { c: number; t: string }> }[];
    names: Record<string, string>;
  };
  let current = data.metrics[0];
  const readout = fig.querySelector<HTMLElement>(".readout")!;
  const show = (key: string | null) => {
    if (!key) return;
    const st = current.states[key];
    readout.innerHTML = "";
    const name = document.createElement("strong");
    name.textContent = data.names[key] ?? key;
    const val = document.createElement("span");
    val.textContent = ` ${st ? st.t : "no figure"}`;
    readout.append(name, val);
    fig.querySelectorAll("path.on").forEach((p) => p.classList.remove("on"));
    fig.querySelector(`path[data-key="${key}"]`)?.classList.add("on");
  };
  const paint = () => {
    fig.querySelector(".map-title")!.textContent = current.title;
    fig.querySelector(".map-note")!.textContent = current.note;
    fig.querySelectorAll<SVGPathElement>("path[data-key]").forEach((p) => {
      const st = current.states[p.dataset.key!];
      p.dataset.cls = String(st ? st.c : -1);
      p.setAttribute("aria-label", `${data.names[p.dataset.key!] ?? p.dataset.key}: ${st ? st.t : "no figure"}`);
    });
    fig.querySelectorAll<HTMLElement>(".legend .lg").forEach((el, i) => (el.textContent = current.legend[i] ?? ""));
    fig.querySelectorAll<HTMLElement>(".small-uts li").forEach((li) => {
      const st = current.states[li.dataset.key!];
      li.querySelector<HTMLElement>(".sw")!.dataset.cls = String(st ? st.c : -1);
      li.querySelector(".v")!.textContent = st ? st.t : "no figure";
    });
    const on = fig.querySelector<SVGPathElement>("path.on");
    if (on) show(on.dataset.key!);
  };
  fig.querySelectorAll<HTMLButtonElement>("button.metric").forEach((b) =>
    b.addEventListener("click", () => {
      current = data.metrics.find((m) => m.id === b.dataset.metric)!;
      fig.querySelectorAll("button.metric").forEach((x) => x.setAttribute("aria-pressed", String(x === b)));
      paint();
    }),
  );
  const svg = fig.querySelector("svg")!;
  svg.addEventListener("pointerover", (e) => show((e.target as SVGElement).dataset?.key ?? null));
  svg.addEventListener("click", (e) => show((e.target as SVGElement).dataset?.key ?? null));
  svg.addEventListener("focusin", (e) => show((e.target as SVGElement).dataset?.key ?? null));
}
