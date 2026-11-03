// @vitest-environment happy-dom
import { beforeEach, describe, expect, it, vi } from "vitest";
import { type SchemeIndex, searchSchemes, setupSchemeSearch } from "../src/scripts/scheme-search";

const INDEX: SchemeIndex = {
  year: "2026-27",
  rows: [
    ["jal-jeevan", "Jal Jeevan Mission", 1, "Jal Shakti", 67000, "National Rural Drinking Water Programme"],
    ["pm-kisan", "PM-KISAN", 0, "Agriculture and Farmers Welfare", 63500, ""],
    ["swachh", "Swachh Bharat Mission (Gramin)", 1, "Jal Shakti", 7192, ""],
    ["old", "Old Water Scheme", 0, "Jal Shakti", null, ""],
  ],
};

function page() {
  document.body.innerHTML = `
    <input id="q"><select id="type"><option value=""></option><option value="1"></option><option value="0"></option></select>
    <section id="results" hidden><h2 id="results-title"></h2><ol id="results-list"></ol></section>
    <section id="top"></section>`;
  const $ = <T extends HTMLElement>(s: string) => document.querySelector<T>(s)!;
  return { q: $<HTMLInputElement>("#q"), type: $<HTMLSelectElement>("#type"), box: $("#results"), title: $("#results-title"), list: $("#results-list"), top: $("#top") };
}

/** A promise the test settles by hand. */
function deferred<T>() {
  let resolve!: (v: T) => void, reject!: (e: unknown) => void;
  const promise = new Promise<T>((a, b) => { resolve = a; reject = b; });
  return { promise, resolve, reject };
}

const type = (el: HTMLInputElement, text: string) => { el.value = text; return el.dispatchEvent(new Event("input")); };
const settle = () => new Promise((r) => setTimeout(r, 0));

describe("searchSchemes", () => {
  it("matches every word in name, ministry or other names, largest first", () => {
    expect(searchSchemes(INDEX, "jal", "").map((r) => r[0])).toEqual(["jal-jeevan", "swachh", "old"]);
    expect(searchSchemes(INDEX, "drinking water", "").map((r) => r[0])).toEqual(["jal-jeevan"]);
    expect(searchSchemes(INDEX, "  KISAN ", "").map((r) => r[0])).toEqual(["pm-kisan"]);
    expect(searchSchemes(INDEX, "", "0").map((r) => r[0])).toEqual(["pm-kisan", "old"]);
    expect(searchSchemes(INDEX, "nothing like this", "")).toEqual([]);
  });
});

describe("setupSchemeSearch", () => {
  let el: ReturnType<typeof page>;
  beforeEach(() => { el = page(); });

  it("fetches the index once however many searches start before it arrives", async () => {
    const d = deferred<SchemeIndex>();
    const load = vi.fn(() => d.promise);
    setupSchemeSearch(document, load);
    type(el.q, "j"); type(el.q, "ja"); type(el.q, "jal");
    d.resolve(INDEX);
    await settle();
    expect(load).toHaveBeenCalledTimes(1);
    expect(el.title.textContent).toBe("3 schemes");
    expect(el.box.hidden).toBe(false);
    expect(el.top.hidden).toBe(true);
    type(el.q, "kisan");
    await settle();
    expect(load).toHaveBeenCalledTimes(1);
    expect(el.title.textContent).toBe("1 scheme");
    expect(el.list.querySelector("a")!.getAttribute("href")).toBe("/budget/schemes/pm-kisan/");
    expect(el.list.querySelector(".meta")!.textContent).toBe("Agriculture and Farmers Welfare · ₹63,500 crore (2026-27)");
  });

  it("keeps the page as it is when the box is cleared while the index loads", async () => {
    const d = deferred<SchemeIndex>();
    setupSchemeSearch(document, () => d.promise);
    type(el.q, "jal");
    type(el.q, "");
    d.resolve(INDEX);
    await settle();
    expect(el.box.hidden).toBe(true);
    expect(el.top.hidden).toBe(false);
  });

  it("says so when the index can't be loaded, without an unhandled rejection, and tries again next time", async () => {
    const load = vi.fn<() => Promise<SchemeIndex>>()
      .mockRejectedValueOnce(new Error("HTTP 503"))
      .mockResolvedValueOnce(INDEX);
    setupSchemeSearch(document, load);
    type(el.q, "jal");
    await settle();
    expect(el.title.textContent).toMatch(/isn't available/);
    expect(el.list.children).toHaveLength(0);
    expect(el.top.hidden).toBe(false);
    type(el.q, "jal jeevan");
    await settle();
    expect(load).toHaveBeenCalledTimes(2);
    expect(el.title.textContent).toBe("1 scheme");
  });

  it("filters by type alone and shows schemes with no allocation", async () => {
    setupSchemeSearch(document, async () => INDEX);
    el.type.value = "0";
    el.type.dispatchEvent(new Event("change"));
    await settle();
    expect(el.title.textContent).toBe("2 schemes");
    expect(el.list.textContent).toContain("Old Water Scheme");
    expect(el.list.textContent).toContain("no allocation in 2026-27");
  });

  it("searches straight away if the browser restored the box's text", async () => {
    el.q.value = "swachh";
    setupSchemeSearch(document, async () => INDEX);
    await settle();
    expect(el.title.textContent).toBe("1 scheme");
  });
});
