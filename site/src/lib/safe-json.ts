// JSON for an inline <script type="application/json"> block. JSON.stringify leaves "<", ">" and "&" as they are,
// so a string holding "</script>" or "<!--" would end or change the script element. Writing them (and the two
// JavaScript line terminators U+2028 and U+2029) as \u escapes keeps the text valid JSON that JSON.parse reads
// back unchanged.
const UNSAFE = /[<>&\u{2028}\u{2029}]/gu;

export const safeJson = (value: unknown): string =>
  JSON.stringify(value).replace(UNSAFE, (c) => `\\u${c.charCodeAt(0).toString(16).padStart(4, "0")}`);
