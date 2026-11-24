/** Decides whether a click on a link starts a page change worth showing a progress bar for. Pure. */

export interface ClickInfo {
  href: string | null;
  target: string | null;
  download: boolean;
  defaultPrevented: boolean;
  button: number;
  modifier: boolean; // ctrl, meta, shift or alt: the browser opens it elsewhere
}

export function startsNavigation(c: ClickInfo, current: { pathname: string; origin: string }): boolean {
  if (!c.href || c.defaultPrevented || c.button !== 0 || c.modifier || c.download) return false;
  if (c.target && c.target !== "_self") return false;
  let url: URL;
  try {
    url = new URL(c.href, `${current.origin}${current.pathname}`);
  } catch {
    return false;
  }
  if (url.origin !== current.origin) return false; // leaving the site
  if (url.pathname === current.pathname) return false; // a hash or query change on the same page
  if (url.pathname.startsWith("/api/")) return false; // a file or JSON link, not a page
  return true;
}
