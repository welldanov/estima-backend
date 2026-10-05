import asyncio
import json
import logging
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

logger = logging.getLogger(__name__)


class DailyQuotaExceededError(Exception):
    def __init__(
            self,
            api_name: str,
            limit: int,
            retry_after: int,
    ) -> None:
        super().__init__(
            f"Daily request limit for {api_name} "
            f"is exhausted ({limit}/day)."
        )

        self.api_name = api_name
        self.limit = limit
        self.retry_after = retry_after


class DailyRequestCounter:
    def __init__(
            self,
            *,
            storage_path: Path,
            limits: dict[str, int],
            tz: timezone,
    ) -> None:
        self.storage_path = Path(storage_path)
        self.limits = limits
        self.tz = tz

        self._lock = asyncio.Lock()

        self._day, self._counts = self._load()

    def _today(self) -> date:
        return datetime.now(self.tz).date()

    def _seconds_until_reset(self) -> int:
        now = datetime.now(self.tz)

        next_midnight = datetime.combine(
            now.date() + timedelta(days=1),
            datetime.min.time(),
            tzinfo=self.tz,
        )

        return max(
            int((next_midnight - now).total_seconds()),
            1,
        )

    def _load(self) -> tuple[date, dict[str, int]]:
        today = self._today()

        if not self.storage_path.exists():
            return today, {}

        try:
            data = json.loads(
                self.storage_path.read_text(
                    encoding="utf-8",
                )
            )

            day = date.fromisoformat(data["date"])
            counts = {
                str(name): int(count)
                for name, count in data["counts"].items()
            }

        except (OSError, ValueError, KeyError, TypeError, AttributeError):
            logger.warning(
                "Request counter file is corrupted, starting from zero: %s",
                self.storage_path,
            )

            return today, {}

        if day != today:
            return today, {}

        return day, counts

    def _save(self) -> None:
        self.storage_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        tmp_path = self.storage_path.with_suffix(".tmp")

        tmp_path.write_text(
            json.dumps(
                {
                    "date": self._day.isoformat(),
                    "counts": self._counts,
                },
                indent=2,
            ),
            encoding="utf-8",
        )

        tmp_path.replace(self.storage_path)

    def _reset_if_new_day(self) -> None:
        today = self._today()

        if today != self._day:
            self._day = today
            self._counts = {}

    async def acquire(
            self,
            api_name: str,
    ) -> None:
        limit = self.limits[api_name]

        async with self._lock:
            self._reset_if_new_day()

            used = self._counts.get(api_name, 0)

            if used >= limit:
                raise DailyQuotaExceededError(
                    api_name=api_name,
                    limit=limit,
                    retry_after=self._seconds_until_reset(),
                )

            self._counts[api_name] = used + 1

            self._save()

    def usage(self) -> dict[str, dict[str, int]]:
        self._reset_if_new_day()

        return {
            api_name: {
                "used": self._counts.get(api_name, 0),
                "limit": limit,
            }
            for api_name, limit in self.limits.items()
        }
