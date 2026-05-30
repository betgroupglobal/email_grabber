/** Normalize user input: https://mobileciti.com.au/path → mobileciti.com.au */
export function normalizeTargetInput(raw: string): string {
  let s = raw.trim();
  try {
    if (/^https?:\/\//i.test(s)) {
      const u = new URL(s);
      s = u.hostname;
    }
  } catch {
    /* keep s */
  }
  s = s.replace(/^\/+|\/+$/g, "");
  const slash = s.indexOf("/");
  if (slash > 0) s = s.slice(0, slash);
  const colon = s.indexOf(":");
  if (colon > 0 && /^\d+$/.test(s.slice(colon + 1))) s = s.slice(0, colon);
  return s.trim().toLowerCase();
}
