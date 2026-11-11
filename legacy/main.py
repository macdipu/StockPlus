"""DSE stock analyzer — CLI.

    python main.py                          # analyze SYMBOL below, write reports/
    python main.py GP SQURPHARMA BXPHARMA   # several symbols (one page load at a time), ranked
    python main.py ORIONINFU --json         # knowledge JSON on stdout (for AI agents)
    python main.py ORIONINFU --brief        # Markdown brief on stdout (for AI agents)
    python main.py serve --port 8000        # web view + REST API + live stream + scanners
    python main.py sync                     # backfill history + fundamentals for every instrument (once, ~20 min)
"""
from __future__ import annotations

import argparse
import json
import sys

import report
import scraper
import service

SYMBOL = "ORIONINFU"


def run_one(symbol: str, args) -> dict:
    k, ind = service.get_analysis(symbol, force=args.force, dump=args.dump)
    paths = [report.write_html(k, ind), report.write_json(k), report.write_brief(k)]
    if args.screenshot:
        paths.append(scraper.screenshot(k["symbol"]) or "")
    if args.json:
        print(json.dumps(report._clean(k), indent=2, ensure_ascii=False))
    elif args.brief:
        print(report.brief(k))
    else:
        print(f"\n{k['symbol']}  LTP {k['price']['ltp']}  signal {k['signal']['action']}  "
              f"score {k['setup']['score']}/{k['setup']['max']}  R/R {report._f(k['setup']['plan']['rr'])}")
        for line in k["summary"]:
            print("  •", line)
        print("  reports:", ", ".join(p for p in paths if p))
    return k


def serve(argv) -> int:
    ap = argparse.ArgumentParser(prog="main.py serve")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8000)
    a = ap.parse_args(argv)
    import uvicorn
    uvicorn.run("api:app", host=a.host, port=a.port, log_level="info")
    return 0


def sync(argv) -> int:
    import store
    ap = argparse.ArgumentParser(prog="main.py sync")
    ap.add_argument("symbols", nargs="*", help="default: every traded equity and mutual fund")
    ap.add_argument("--force", action="store_true", help="reload symbols fetched in the last 7 days too")
    a = ap.parse_args(argv)
    syms = [scraper.normalize_symbol(s) for s in a.symbols] or sorted(
        s for s, q in scraper.fetch_snapshot()["quotes"].items() if q.get("assetType") in ("EQ", "MF"))
    print(f"syncing {len(syms)} symbols, one page every {scraper.C.MIN_PAGE_INTERVAL_S}s…")
    r = store.backfill(syms, force=a.force)
    print(f"done: ok={r['ok']} skipped_fresh={r['skipped_fresh']} failed={len(r['failed'])}")
    for f in r["failed"][:20]:
        print("  ", f)
    print(store.status())
    return 0 if not r["failed"] else 1


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if argv[:1] == ["serve"]:
        return serve(argv[1:])
    if argv[:1] == ["sync"]:
        return sync(argv[1:])
    ap = argparse.ArgumentParser(description="Analyze DSE stocks from www.dse.com.bd.")
    ap.add_argument("symbols", nargs="*", default=[SYMBOL])
    ap.add_argument("--force", action="store_true", help="ignore today's cache and reload the company page")
    ap.add_argument("--dump", action="store_true", help="save the parsed upstream payload to captured/")
    ap.add_argument("--screenshot", action="store_true", help="full-page screenshot (needs playwright)")
    ap.add_argument("--json", action="store_true", help="print the knowledge JSON to stdout")
    ap.add_argument("--brief", action="store_true", help="print the Markdown brief to stdout")
    args = ap.parse_args(argv)

    results, failures = [], []
    for sym in args.symbols:   # sequential; scraper spaces page loads by MIN_PAGE_INTERVAL_S
        try:
            results.append(run_one(sym, args))
        except (scraper.ScrapeError, scraper.InvalidInput) as e:
            failures.append(sym)
            print(f"[{sym}] ERROR: {e}", file=sys.stderr)

    if len(results) > 1:
        results.sort(key=lambda k: (k["setup"]["score"], k["setup"]["plan"]["rr"] or 0), reverse=True)
        out = sys.stderr if (args.json or args.brief) else sys.stdout
        print("\nRANK  SYMBOL        SCORE  SIGNAL       R/R   P(hit)  LTP", file=out)
        for n, k in enumerate(results, 1):
            p = k["probability"]["similar_setups"]["p_target_first"]
            print(f"{n:>4}  {k['symbol']:<12}  {k['setup']['score']}/{k['setup']['max']}    "
                  f"{k['signal']['action']:<11}  {report._f(k['setup']['plan']['rr']):>4}  "
                  f"{report._f(p, '{:.0%}'):>6}  {k['price']['ltp']}", file=out)
    return 1 if failures and not results else 0


if __name__ == "__main__":
    sys.exit(main())
