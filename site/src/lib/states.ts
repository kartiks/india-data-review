// State and UT names, shared by every area, so a page that matches states needs no area's dataset.

/** One key for a state however a source spells it: "The Dadra And Nagar Haveli And Daman And Diu",
 * "Dadra & Nagar Haveli & Daman & Diu" and "Dadra and Nagar Haveli and Daman and Diu" all give the same key.
 * The pipelines' checks use the same rule (jobs-prices/pipeline/jobs_prices_pipeline/checks/states.py, state_key);
 * both are tested against shared/fixtures/state-names.json, so change the fixture with either. */
export const stateKey = (s: string) =>
  s.toLowerCase().replace(/&/g, "and").replace(/^the |^nct of |\bislands?\b/g, "").replace(/[^a-z]/g, "");
