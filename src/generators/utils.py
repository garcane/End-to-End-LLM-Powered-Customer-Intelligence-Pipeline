"""Shared helpers: deterministic RNG, streaming CSV output and date arithmetic."""

from __future__ import annotations

import csv
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Iterable, Mapping, Sequence

import numpy as np

EPOCH = date(1970, 1, 1)


# --------------------------------------------------------------------------------------
# Randomness
# --------------------------------------------------------------------------------------


def make_rng(seed: int, stream: str = "") -> np.random.Generator:
    """Return a generator seeded from ``seed`` and a named sub-stream.

    Using a named sub-stream per table means that changing the number of draws in one
    generator does not shift the output of every other generator.
    """
    if stream:
        seed = int(np.random.SeedSequence([seed, *[ord(c) for c in stream]]).generate_state(1)[0])
    return np.random.default_rng(seed)


def pick(rng: np.random.Generator, choices: Sequence[tuple[str, float]], size: int | None = None):
    """Sample from a list of ``(value, probability)`` pairs."""
    values = [c[0] for c in choices]
    probs = np.array([c[1] for c in choices], dtype=float)
    probs = probs / probs.sum()
    return rng.choice(values, size=size, p=probs)


def sigmoid(x):
    return 1.0 / (1.0 + np.exp(-np.asarray(x, dtype=float)))


def clip01(x):
    return np.clip(x, 0.0, 1.0)


# --------------------------------------------------------------------------------------
# Dates
# --------------------------------------------------------------------------------------


def to_ordinal(d: date) -> int:
    """Days since the Unix epoch.  All internal date maths uses these integers."""
    return (d - EPOCH).days


def from_ordinal(n: int | float) -> date:
    return EPOCH + timedelta(days=int(n))


def iso(n: int | float) -> str:
    return from_ordinal(n).isoformat()


def iso_ts(n: int | float, minute_of_day: int) -> str:
    """Render a day ordinal plus a minute-of-day as an ISO-8601 timestamp (second precision)."""
    dt = datetime.combine(from_ordinal(n), datetime.min.time()) + timedelta(minutes=int(minute_of_day))
    return dt.isoformat(sep=" ", timespec="seconds")


def add_years(day_ordinal: int, years: int) -> int:
    """Add whole calendar years to a day ordinal, handling 29 February."""
    d = from_ordinal(day_ordinal)
    try:
        return to_ordinal(d.replace(year=d.year + years))
    except ValueError:  # 29 February in a non-leap target year
        return to_ordinal(d.replace(year=d.year + years, day=28))


def week_start(day_ordinal: int) -> int:
    """Monday of the week containing ``day_ordinal``."""
    return day_ordinal - ((day_ordinal + 3) % 7)


def seasonality(day_ordinals: np.ndarray) -> np.ndarray:
    """Multiplicative seasonal factor for member activity.

    Professional bodies are quiet in mid-summer and over the winter holidays, and busy
    in the spring and autumn conference seasons.
    """
    doy = np.array([from_ordinal(int(d)).timetuple().tm_yday for d in np.atleast_1d(day_ordinals)], dtype=float)
    factor = (
        1.0
        + 0.18 * np.sin(2 * np.pi * (doy - 60) / 365.25)
        - 0.28 * np.exp(-(((doy - 225) / 22.0) ** 2))  # August lull
        - 0.35 * np.exp(-(((doy - 360) / 12.0) ** 2))  # Christmas shutdown
    )
    return np.clip(factor, 0.25, 1.6)


# --------------------------------------------------------------------------------------
# Output
# --------------------------------------------------------------------------------------


class TableWriter:
    """Append-only CSV writer that writes its header once and counts rows."""

    def __init__(self, path: Path, columns: Sequence[str]):
        self.path = path
        self.columns = list(columns)
        self.rows_written = 0
        path.parent.mkdir(parents=True, exist_ok=True)
        self._fh = path.open("w", newline="", encoding="utf-8")
        self._writer = csv.writer(self._fh, quoting=csv.QUOTE_MINIMAL, lineterminator="\n")
        self._writer.writerow(self.columns)

    def write_rows(self, rows: Iterable[Sequence]) -> None:
        n = 0
        for row in rows:
            self._writer.writerow(row)
            n += 1
        self.rows_written += n

    def write_dicts(self, rows: Iterable[Mapping]) -> None:
        self.write_rows([[r.get(c, "") for c in self.columns] for r in rows])

    def close(self) -> None:
        self._fh.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


class WriterSet:
    """A named collection of :class:`TableWriter` objects opened together."""

    def __init__(self, out_dir: Path, schemas: Mapping[str, Sequence[str]]):
        self.writers = {name: TableWriter(out_dir / f"{name}.csv", cols) for name, cols in schemas.items()}

    def __getitem__(self, name: str) -> TableWriter:
        return self.writers[name]

    def row_counts(self) -> dict[str, int]:
        return {name: w.rows_written for name, w in self.writers.items()}

    def close(self) -> None:
        for w in self.writers.values():
            w.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


def money(x: float) -> float:
    return float(np.round(x, 2))


def pct(x: float) -> float:
    return float(np.round(x, 4))
