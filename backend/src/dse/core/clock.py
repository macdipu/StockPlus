"""Real clock in exchange time (Asia/Dhaka)."""

from datetime import date, datetime
from zoneinfo import ZoneInfo

DHAKA = ZoneInfo("Asia/Dhaka")


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(DHAKA)

    def today(self) -> date:
        return self.now().date()
