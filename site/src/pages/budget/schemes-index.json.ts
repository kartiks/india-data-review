// Search index for the schemes page: one compact row per scheme.
import { SCHEMES, SCHEME_YEARS, schemeValue, best, ministryOfScheme } from "../../lib/budget/data";

export function GET() {
  const latest = SCHEME_YEARS[SCHEME_YEARS.length - 1];
  const rows = SCHEMES.map((s) => {
    const v = best((k) => schemeValue(latest, s.key, k));
    const m = ministryOfScheme(s);
    const other = s.aliases.filter((a) => a !== s.name).join(" | ");
    return [s.slug, s.name, s.type === "css" ? 1 : 0, m?.name.replace(/^Ministry of /, "") ?? s.department, v ? Math.round(v.value * 100) / 100 : null, other];
  });
  return new Response(JSON.stringify({ year: latest, rows }), { headers: { "Content-Type": "application/json" } });
}
