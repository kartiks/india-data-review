// @vitest-environment happy-dom
// The script behind components/PickLines.astro (src/scripts/pick-lines.ts), on markup shaped like the component's.
import { beforeEach, describe, expect, it } from "vitest";
import { type Data, type Opt, keysFromHash, setupPickLines } from "../src/scripts/pick-lines";

describe("keysFromHash", () => {
  it("reads the keys in #show=…", () => {
    expect(keysFromHash("#show=a,b")).toEqual(["a", "b"]);
    expect(keysFromHash("#show=a%2Cb")).toEqual(["a", "b"]);
  });
  it("is null with no #show, and empty for an empty one", () => {
    expect(keysFromHash("")).toBeNull();
    expect(keysFromHash("#notes")).toBeNull();
    expect(keysFromHash("#show=")).toEqual([]);
    expect(keysFromHash("#show")).toEqual([]);
  });
});

const YEARS = ["2020-21", "2021-22", "2022-23"];
const opt = (key: string, name: string, v: (number | null)[], note = ""): Opt => ({
  key, name, note, v, t: v.map((x) => (x == null ? null : `${x}%`)), k: v.map(() => ""), kt: v.map(() => ""),
});
const DATA: Data = {
  years: YEARS,
  options: [opt("a", "Assam", [1, 2, 3]), opt("b", "Bihar", [4, 5, null], "Bihar note."), opt("c", "Goa", [7, null, null])],
  reference: { ...opt("india", "All India", [2, 3, 4]), k: ["", "", "PE"], kt: ["", "", "Provisional estimate"] },
  initial: ["a", "b"],
  max: 2,
  axis: "pct",
  label: "Growth. Values are listed in the table below.",
};

function figure(): HTMLElement {
  document.body.innerHTML = `
    <figure class="chart pick-lines">
      <ul class="chips"></ul>
      <details class="choose" hidden>
        <summary>Choose states</summary>
        <div class="choose-bar"><button type="button" class="reset">Reset</button><button type="button" class="clear">Clear</button><span class="limit"></span></div>
        <fieldset>${["india", "a", "b", "c"].map((k) => `<label><input type="checkbox" value="${k}"></label>`).join("")}</fieldset>
      </details>
      <div class="plots"></div>
      <p class="empty" hidden></p>
      <ul class="pick-notes"></ul>
      <details class="table-view"><table><thead></thead><tbody></tbody></table></details>
      <script type="application/json" class="pick-data">${JSON.stringify(DATA)}</script>
    </figure>`;
  const fig = document.querySelector<HTMLElement>("figure")!;
  setupPickLines(fig);
  return fig;
}
const chips = (fig: HTMLElement) => [...fig.querySelectorAll<HTMLButtonElement>(".chips button.chip")].map((b) => b.dataset.key);
const box = (fig: HTMLElement, key: string) => fig.querySelector<HTMLInputElement>(`input[value="${key}"]`)!;
const head = (fig: HTMLElement) => [...fig.querySelectorAll(".table-view thead th")].map((th) => th.textContent);
const tick = (fig: HTMLElement, key: string, on: boolean) => {
  box(fig, key).checked = on;
  box(fig, key).dispatchEvent(new Event("change"));
};

beforeEach(() => history.replaceState(null, "", "/gdp/states/"));

describe("setupPickLines", () => {
  it("starts with the starting set, and shows the Choose panel", () => {
    const fig = figure();
    expect(chips(fig)).toEqual(["a", "b"]);
    expect(fig.querySelector<HTMLElement>(".choose")!.hidden).toBe(false);
    expect(fig.querySelectorAll(".plots svg.plot").length).toBeGreaterThan(0);
    expect(head(fig)).toEqual(["Year", "Assam", "Bihar"]);
    expect([...fig.querySelectorAll(".pick-notes li")].map((li) => li.textContent)).toEqual(["Bihar note."]);
    expect(location.hash).toBe("");
  });
  it("disables the other boxes at the limit, but never the reference line", () => {
    const fig = figure();
    expect([box(fig, "a").checked, box(fig, "b").checked, box(fig, "c").checked]).toEqual([true, true, false]);
    expect(box(fig, "c").disabled).toBe(true);
    expect(box(fig, "india").disabled).toBe(false);
    expect(fig.querySelector(".limit")!.textContent).toMatch(/Up to 2 at once/);
  });
  it("adds the reference line as a dashed line, and keeps the choice in the address", () => {
    const fig = figure();
    tick(fig, "india", true);
    expect(chips(fig)).toEqual(["a", "b", "india"]);
    expect(fig.querySelector('.chips [data-key="india"] .sw')!.className).toBe("sw dashed");
    expect(location.hash).toBe("#show=a,b,india");
    // Its estimate label goes before the value in the table.
    const last = fig.querySelectorAll(".table-view tbody tr")[2];
    expect(last.lastElementChild!.textContent).toBe("PE4%");
  });
  it("removes a line from its chip, and frees a place", () => {
    const fig = figure();
    fig.querySelector<HTMLButtonElement>('.chips [data-key="a"]')!.click();
    expect(chips(fig)).toEqual(["b"]);
    expect(document.activeElement).toBe(fig.querySelector('.chips [data-key="b"]'));
    expect(box(fig, "c").disabled).toBe(false);
    expect(location.hash).toBe("#show=b");
  });
  it("shows years up to the last one any line shown has", () => {
    const fig = figure();
    tick(fig, "a", false);
    tick(fig, "b", false);
    tick(fig, "c", true);
    expect(fig.querySelectorAll(".table-view tbody tr").length).toBe(1);
  });
  it("reads the choice from the address", () => {
    history.replaceState(null, "", "#show=c,india");
    expect(chips(figure())).toEqual(["c", "india"]);
  });
  it("draws nothing for an empty #show=, and the starting set for keys it does not know", () => {
    history.replaceState(null, "", "#show=");
    let fig = figure();
    expect(chips(fig)).toEqual([]);
    expect(fig.querySelector(".plots")!.innerHTML).toBe("");
    expect(fig.querySelector<HTMLElement>(".empty")!.hidden).toBe(false);
    expect(fig.querySelector<HTMLElement>(".table-view")!.hidden).toBe(true);
    history.replaceState(null, "", "#show=nowhere");
    fig = figure();
    expect(chips(fig)).toEqual(["a", "b"]);
  });
  it("clears, and resets to the starting set (dropping its own #show)", () => {
    const fig = figure();
    fig.querySelector<HTMLButtonElement>(".clear")!.click();
    expect(chips(fig)).toEqual([]);
    expect(location.hash).toBe("#show=");
    fig.querySelector<HTMLButtonElement>(".reset")!.click();
    expect(chips(fig)).toEqual(["a", "b"]);
    expect(location.hash).toBe("");
  });
});
