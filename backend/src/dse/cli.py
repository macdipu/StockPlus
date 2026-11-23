"""Command-line composition root.

python -m dse.cli {sync,backfill,eod,backtest-picks,create-user,set-role} ...
"""

import argparse
import asyncio
import getpass
import json
import sys
from pathlib import Path

from dse.core.clock import SystemClock
from dse.core.config import get_settings
from dse.core.db import Database
from dse.core.logging import configure_logging
from dse.core.security import Argon2PasswordHasher
from dse.features.identity.application.use_cases import PromoteUser, Register
from dse.features.identity.infrastructure.repositories import SqlIdentityUnitOfWork
from dse.features.market_data.application.use_cases import AppendEndOfDay, BackfillUniverse
from dse.features.market_data.infrastructure.dse_source import DseHttpSource
from dse.features.market_data.presentation.dependencies import MarketDataContainer
from dse.features.scanner.application.backtest import run_backtest
from dse.features.scanner.infrastructure.gateways import load_universe_history
from dse.shared_kernel.errors import DomainError
from dse.shared_kernel.principal import Role
from dse.shared_kernel.symbol import Symbol


async def _identity(args: argparse.Namespace) -> int:
    """Operator account commands. Passwords come from a prompt or stdin, never from argv (visible in `ps`)."""
    s = get_settings()
    db, clock = Database(s.database), SystemClock()

    def uow() -> SqlIdentityUnitOfWork:
        return SqlIdentityUnitOfWork(db.sessions)

    try:
        if args.cmd == "create-user":
            password = (
                sys.stdin.readline().rstrip("\n") if args.password_stdin else getpass.getpass("Password: ")
            )
            register = Register(uow, Argon2PasswordHasher(), clock, s.security.min_password_length)
            user = await register(args.email, password, Role(args.role))
        else:  # set-role
            user = await PromoteUser(uow, clock)(args.email, Role(args.role))
        print(json.dumps({"id": str(user.id), "email": user.email, "role": user.role}))
        return 0
    except DomainError as e:
        print(f"error: {e.detail}", file=sys.stderr)
        return 1
    finally:
        await db.dispose()


async def _run(args: argparse.Namespace) -> int:
    if args.cmd in ("create-user", "set-role"):
        return await _identity(args)
    s = get_settings()
    db = Database(s.database)
    clock = SystemClock()
    source = DseHttpSource(
        s.upstream.base_url,
        clock,
        user_agent=s.upstream.user_agent,
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
        elif args.cmd == "backtest-picks":
            history = await load_universe_history(c.facade)
            horizons = tuple(int(x) for x in args.horizons.split(","))
            result = await asyncio.to_thread(
                run_backtest, history, horizons=horizons, step=args.step, min_history=args.min_history
            )
            result["generated_at"] = clock.today().isoformat()
            text = json.dumps(result, indent=1, default=str)
            if args.out:
                await asyncio.to_thread(Path(args.out).write_text, text)
            print(text)
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
    p = sub.add_parser(
        "backtest-picks", help="replay the Picks score over past sessions (research; prints JSON)"
    )
    p.add_argument("--horizons", default="5,10,20", help="sessions ahead, comma separated")
    p.add_argument("--step", type=int, default=3, help="replay every Nth session")
    p.add_argument("--min-history", type=int, default=120, help="sessions of history before the first replay")
    p.add_argument(
        "--out",
        help="also write the JSON here (the published track record is scanner/data/picks_backtest.json)",
    )
    p = sub.add_parser("create-user", help="create an account (use --role admin for the first admin)")
    p.add_argument("email")
    p.add_argument("--role", choices=[r.value for r in Role], default=Role.USER.value)
    p.add_argument("--password-stdin", action="store_true", help="read the password from stdin, not a prompt")
    p = sub.add_parser("set-role", help="change an account's role (signs it out everywhere)")
    p.add_argument("email")
    p.add_argument("role", choices=[r.value for r in Role])
    return asyncio.run(_run(ap.parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
