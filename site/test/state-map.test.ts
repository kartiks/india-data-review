// @vitest-environment happy-dom
// The script behind components/StateMap.astro (src/scripts/state-map.ts), on markup shaped like the component's.
import { describe, expect, it } from "vitest";
import { setupStateMap } from "../src/scripts/state-map";

const DATA = {
  names: { goa: "Goa", bihar: "Bihar" },
  metrics: [
    { id: "ur", title: "Unemployment, 2024", note: "Usual status.", legend: ["1% to 2%", "3% to 4%"],
      states: { goa: { c: 1, t: "4.0%" }, bihar: { c: 0, t: "1.5%" } } },
    { id: "wage", title: "Rural farm wage, 2024", note: "Men.", legend: ["₹300 to ₹400", ""],
      states: { bihar: { c: 0, t: "₹350" } } },
  ],
};

function figure(): HTMLElement {
  document.body.innerHTML = `
    <figure class="state-map">
      <button type="button" class="metric" data-metric="ur" aria-pressed="true"></button>
      <button type="button" class="metric" data-metric="wage" aria-pressed="false"></button>
      <h2 class="map-title">Unemployment, 2024</h2><p class="map-note">Usual status.</p>
      <svg><path data-key="goa" data-cls="1"></path><path data-key="bihar" data-cls="0"></path></svg>
      <ol class="legend"><li><span class="lg"></span></li><li><span class="lg"></span></li></ol>
      <p class="readout"></p>
      <div class="small-uts"><ul><li data-key="goa"><span class="sw"></span><strong class="v"></strong></li></ul></div>
      <script type="application/json" class="map-data">${JSON.stringify(DATA)}</script>
    </figure>`;
  const fig = document.querySelector<HTMLElement>("figure")!;
  setupStateMap(fig);
  return fig;
}
const $ = (fig: HTMLElement, s: string) => fig.querySelector<HTMLElement>(s)!;

describe("setupStateMap", () => {
  it("switches the measure: title, note, colours, labels, legend and the small states", () => {
    const fig = figure();
    $(fig, '[data-metric="wage"]').click();
    expect($(fig, ".map-title").textContent).toBe("Rural farm wage, 2024");
    expect($(fig, ".map-note").textContent).toBe("Men.");
    expect([...fig.querySelectorAll("button.metric")].map((b) => b.getAttribute("aria-pressed"))).toEqual(["false", "true"]);
    expect($(fig, 'path[data-key="goa"]').dataset.cls).toBe("-1");
    expect($(fig, 'path[data-key="goa"]').getAttribute("aria-label")).toBe("Goa: no figure");
    expect($(fig, 'path[data-key="bihar"]').getAttribute("aria-label")).toBe("Bihar: ₹350");
    expect([...fig.querySelectorAll(".legend .lg")].map((l) => l.textContent)).toEqual(["₹300 to ₹400", ""]);
    expect($(fig, ".small-uts .v").textContent).toBe("no figure");
    expect($(fig, ".small-uts .sw").dataset.cls).toBe("-1");
  });
  it("shows the state tapped, and keeps it shown, updated, when the measure changes", () => {
    const fig = figure();
    $(fig, 'path[data-key="goa"]').dispatchEvent(new Event("click", { bubbles: true }));
    expect($(fig, ".readout").textContent).toBe("Goa 4.0%");
    expect($(fig, 'path[data-key="goa"]').classList.contains("on")).toBe(true);
    $(fig, '[data-metric="wage"]').click();
    expect($(fig, ".readout").textContent).toBe("Goa no figure");
  });
});
