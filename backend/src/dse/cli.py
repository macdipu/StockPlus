"""Command-line composition root:  python -m dse.cli {sync,backfill,eod} ..."""

import argparse
import asyncio
import json
import sys

from dse.core.clock import SystemClock
from dse.core.config import get_settings
from dse.core.db import Database
from dse.core.logging import configure_logging
from dse.features.market_data.application.use_cases import AppendEndOfDay, BackfillUniverse
from dse.features.market_data.infrastructure.dse_source import DseHttpSource
from dse.features.market_data.presentation.dependencies import MarketDataContainer
from dse.shared_kernel.symbol import Symbol


async def _run(args: argparse.Namespace) -> int:
    s = get_settings()
    db = Database(s.database)
    clock = SystemClock()
    source = DseHttpSource(
        s.upstream.base_url,
        clock,
        timeout_s=s.upstream.timeout_s,
        min_page_interval_s=s.upstream.min_page_interval_s,
    )
    c = MarketDataContainer(db, source, clock)
    try:
        if args.cmd == "sync":
            for sym in args.symbols:
                print(json.dumps((await c.sync(Symbol(sym))).model_dump()))
        elif args.cmd == "backfill":
            syms = [Symbol(x) for x in args.symbols] or None
            report = await BackfillUniverse(c.uow, source, c.sync, clock)(
                syms,
                force=args.force,
                progress=lambda i, n: (
                    print(f"backfill {i}/{n}", file=sys.stderr) if i % 25 == 0 or i == n else None
                ),
            )
            print(report.model_dump_json(indent=1))
            return 1 if report.failed else 0
        elif args.cmd == "eod":
            print((await AppendEndOfDay(c.uow, source)()).model_dump_json())
        return 0
    finally:
        await source.aclose()
        await db.dispose()


def main() -> int:
    configure_logging(get_settings().log_level)
    ap = argparse.ArgumentParser(prog="python -m dse.cli")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("sync", help="sync one or more instruments now")
    p.add_argument("symbols", nargs="+")
    p = sub.add_parser(
        "backfill", help="sync every tradable instrument (skips those synced in the last 7 days)"
    )
    p.add_argument("symbols", nargs="*")
    p.add_argument("--force", action="store_true")
    sub.add_parser("eod", help="append today's bars from one post-close snapshot")
    return asyncio.run(_run(ap.parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
