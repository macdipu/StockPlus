/** Which symbols the open stream must carry. Components register what they show; the provider reads the union. */

export const MAX_STREAM_SYMBOLS = 50; // the API rejects more

export class SymbolRegistry {
  private primary = new Map<string, number>();
  private secondary = new Map<string, number>();
  private listeners = new Set<() => void>();

  register(symbols: readonly string[], primary: boolean): () => void {
    const bucket = primary ? this.primary : this.secondary;
    const codes = [...new Set(symbols.map((s) => s.toUpperCase()))];
    for (const s of codes) bucket.set(s, (bucket.get(s) ?? 0) + 1);
    this.emit();
    let done = false;
    return () => {
      if (done) return;
      done = true;
      for (const s of codes) {
        const left = (bucket.get(s) ?? 1) - 1;
        if (left <= 0) bucket.delete(s);
        else bucket.set(s, left);
      }
      this.emit();
    };
  }

  /** Primary symbols (the page being viewed) first, so a long watchlist can never crowd them out. */
  symbols(): string[] {
    const rest = [...this.secondary.keys()].filter((s) => !this.primary.has(s)).sort();
    return [...[...this.primary.keys()].sort(), ...rest].slice(0, MAX_STREAM_SYMBOLS);
  }

  onChange(l: () => void): () => void {
    this.listeners.add(l);
    return () => this.listeners.delete(l);
  }

  private emit(): void {
    for (const l of this.listeners) l();
  }
}
