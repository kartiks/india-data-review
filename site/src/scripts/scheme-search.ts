// Scheme search on /budget/schemes/. The index (pages/budget/schemes-index.json.ts, ~200 KB) is fetched once,
// on the first search.
import { money } from "../lib/format";
import { link } from "../lib/url";

/** [slug, name, centrally sponsored (1) or central sector (0), ministry, latest allocation (crore), names in other budgets] */
export type SchemeRow = [string, string, number, string, number | null, string];
export interface SchemeIndex { year: string; rows: SchemeRow[] }

/** Schemes whose name, ministry or other names contain every word of `text`, of `type` ("" = any), largest first. */
export function searchSchemes(index: SchemeIndex, text: string, type: string): SchemeRow[] {
  const words = text.toLowerCase().split(/\s+/).filter(Boolean);
  return index.rows
    .filter((r) => (type === "" || String(r[2]) === type) && words.every((w) => `${r[1]} ${r[3]} ${r[5]}`.toLowerCase().includes(w)))
    .sort((a, b) => (b[4] ?? -1) - (a[4] ?? -1));
}

async function fetchIndex(): Promise<SchemeIndex> {
  const res = await fetch(link("/budget/schemes-index.json"));
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

/** Wire the search box and type filter. Returns run() (also called on every input) for tests. */
export function setupSchemeSearch(doc: Document = document, load: () => Promise<SchemeIndex> = fetchIndex) {
  const q = doc.querySelector<HTMLInputElement>("#q")!;
  const type = doc.querySelector<HTMLSelectElement>("#type")!;
  const box = doc.querySelector<HTMLElement>("#results")!;
  const list = doc.querySelector<HTMLOListElement>("#results-list")!;
  const title = doc.querySelector<HTMLElement>("#results-title")!;
  const top = doc.querySelector<HTMLElement>("#top")!;

  // One request however fast the reader types; after a failure the next search tries again.
  let pending: Promise<SchemeIndex> | null = null;
  const index = () => (pending ??= load().catch((e) => { pending = null; throw e; }));
  // Only the latest search may change the page: an earlier one finishing late is ignored.
  let latest = 0;

  async function run() {
    const id = ++latest;
    const text = q.value.trim();
    if (!text && !type.value) { box.hidden = true; top.hidden = false; return; }
    let idx: SchemeIndex;
    try {
      idx = await index();
    } catch {
      if (id !== latest) return;
      title.textContent = "Search isn't available right now. Please try again.";
      list.replaceChildren();
      box.hidden = false;
      top.hidden = false;
      return;
    }
    if (id !== latest) return;
    const hits = searchSchemes(idx, text, type.value);
    title.textContent = `${hits.length} scheme${hits.length === 1 ? "" : "s"}`;
    list.replaceChildren(...hits.slice(0, 100).map((r) => {
      const li = doc.createElement("li");
      const a = doc.createElement("a");
      a.href = link(`/budget/schemes/${r[0]}/`);
      a.textContent = r[1];
      const meta = doc.createElement("span");
      meta.className = "meta";
      meta.textContent = `${r[3]}${r[4] != null ? ` · ${money(r[4])} (${idx.year})` : " · no allocation in " + idx.year}`;
      li.append(a, meta);
      return li;
    }));
    box.hidden = false;
    top.hidden = true;
  }

  q.addEventListener("input", run);
  type.addEventListener("change", run);
  // The browser may restore the box's text on "back": show those results again.
  if (q.value.trim() || type.value) void run();
  return { run };
}
