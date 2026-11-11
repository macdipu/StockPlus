/**
 * The short-lived access token lives only in memory (never localStorage): a script that gets into the page
 * cannot read it after a reload, and the HttpOnly refresh cookie silently mints a new one.
 */
let accessToken: string | null = null;

export const tokenStore = {
  get: (): string | null => accessToken,
  set: (t: string | null): void => {
    accessToken = t;
  },
};
