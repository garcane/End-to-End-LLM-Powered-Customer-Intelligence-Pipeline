"""Command-line entry point for the synthetic membership dataset.

    python -m src.generators.run --scale full

Run ``--help`` for options.  Every run writes ``generation_manifest.json`` alongside the
data so that any extract can be traced back to the seed, scale and code version that
produced it.
"""

from __future__ import annotations

import argparse
import json
import platform
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from . import config
from .activity import SCHEMAS, RunContext, prediction_run_dates, simulate_member
from .catalogues import (
    CAMPAIGN_COLUMNS,
    COURSE_COLUMNS,
    EVENT_COLUMNS,
    generate_campaigns,
    generate_courses,
    generate_events,
)
from .data_quality import DQ_COLUMNS, generate_data_quality
from .members import MEMBER_COLUMNS, generate_members
from .seed import load_calibration
from .utils import TableWriter, WriterSet, from_ordinal, iso, make_rng, to_ordinal


def parse_args(argv=None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Generate the Synthetic Professional Membership Engagement and Retention Dataset.")
    p.add_argument("--scale", choices=sorted(config.SCALE_PROFILES), default=config.DEFAULT_SCALE,
                   help="dataset size profile (default: %(default)s)")
    p.add_argument("--seed", type=int, default=config.DEFAULT_SEED, help="master random seed (default: %(default)s)")
    p.add_argument("--out", type=Path, default=config.SYNTHETIC_DIR, help="output directory for the CSV files")
    p.add_argument("--members", type=int, default=None, help="override the member count from the scale profile")
    p.add_argument("--sample-rows", type=int, default=250,
                   help="rows per table copied into data/sample/ for version control (0 to skip)")
    return p.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    profile = config.SCALE_PROFILES[args.scale]
    n_members = args.members or profile.n_members
    out_dir: Path = args.out
    out_dir.mkdir(parents=True, exist_ok=True)

    as_of = to_ordinal(config.AS_OF_DATE)
    window_start = to_ordinal(config.WINDOW_START)
    started = time.time()

    print(f"Synthetic Professional Membership Engagement and Retention Dataset")
    print(f"  scale={args.scale}  members={n_members:,}  seed={args.seed}")
    print(f"  window={config.WINDOW_START} .. {config.AS_OF_DATE}  out={out_dir}")

    calibration = load_calibration()

    # --- Dimensions -------------------------------------------------------------------
    print("  building member dimension and catalogues ...")
    members = generate_members(make_rng(args.seed, "members"), n_members, calibration)
    events = generate_events(make_rng(args.seed, "events"), profile.n_events)
    campaigns = generate_campaigns(make_rng(args.seed, "campaigns"), profile.n_campaigns)
    courses = generate_courses(make_rng(args.seed, "courses"), profile.n_courses)

    events[EVENT_COLUMNS].to_csv(out_dir / "events.csv", index=False)
    campaigns[CAMPAIGN_COLUMNS].to_csv(out_dir / "campaigns.csv", index=False)
    courses[COURSE_COLUMNS].to_csv(out_dir / "courses.csv", index=False)

    # --- Behavioural simulation -------------------------------------------------------
    runs = prediction_run_dates(profile.n_prediction_runs, as_of)
    ctx = RunContext(
        rng=make_rng(args.seed, "activity"),
        events=events,
        campaigns=campaigns,
        courses=courses,
        prediction_runs=runs,
        insight_run=runs[-1],
        as_of=as_of,
        window_start=window_start,
    )
    print(f"  scoring runs: {', '.join(iso(r) for r in runs)}")

    ids = {name: 0 for name in SCHEMAS}
    outcomes: list[dict] = []

    with WriterSet(out_dir, SCHEMAS) as writers:
        total = len(members)
        for start in range(0, total, profile.chunk_size):
            chunk = members.iloc[start : start + profile.chunk_size]
            for m in chunk.itertuples(index=False):
                outcomes.append(simulate_member(m, ctx, ids, writers))
            done = min(start + profile.chunk_size, total)
            elapsed = time.time() - started
            print(f"    members {done:,}/{total:,}  ({elapsed:5.1f}s)", end="\r", flush=True)
        print()
        row_counts = writers.row_counts()

    # --- Finalise the member dimension ------------------------------------------------
    out = pd.DataFrame(outcomes)
    members = members.merge(out, on="member_id", how="left", suffixes=("_initial", ""))
    members["churn_date"] = [iso(o) if pd.notna(o) else "" for o in members["churn_ord"]]
    members["renewal_date"] = [iso(o) if pd.notna(o) else "" for o in members["renewal_ord"]]
    members[MEMBER_COLUMNS].to_csv(out_dir / "members.csv", index=False)
    row_counts["members"] = len(members)
    row_counts["events"] = len(events)
    row_counts["campaigns"] = len(campaigns)
    row_counts["courses"] = len(courses)

    # --- Data quality -----------------------------------------------------------------
    print("  generating data-quality results ...")
    with TableWriter(out_dir / "data_quality_results.csv", DQ_COLUMNS) as w:
        w.write_rows(generate_data_quality(make_rng(args.seed, "dq"), row_counts, as_of, profile.n_pipeline_runs))
        row_counts["data_quality_results"] = w.rows_written

    # --- Manifest and summary ---------------------------------------------------------
    churn_rate = float(members["churn_flag"].mean())
    manifest = {
        "dataset": "Synthetic Professional Membership Engagement and Retention Dataset",
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "scale_profile": args.scale,
        "seed": args.seed,
        "n_members": int(n_members),
        "window_start": config.WINDOW_START.isoformat(),
        "as_of_date": config.AS_OF_DATE.isoformat(),
        "seed_calibration": {
            "source": calibration.source,
            "tenure_mean_months": calibration.tenure_mean_months,
            "month_to_month_share": calibration.month_to_month_share,
            "automatic_payment_share": calibration.automatic_payment_share,
            "churn_rate": calibration.churn_rate,
            "notes": calibration.notes,
        },
        "churn_coefficients": config.CHURN_COEFFICIENTS,
        "prediction_runs": [iso(r) for r in runs],
        "observed_cumulative_churn_rate": round(churn_rate, 4),
        "row_counts": {k: int(v) for k, v in sorted(row_counts.items())},
        "python": platform.python_version(),
        "numpy": np.__version__,
        "pandas": pd.__version__,
        "runtime_seconds": round(time.time() - started, 1),
    }
    (out_dir / "generation_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    if args.sample_rows:
        _write_samples(out_dir, config.SAMPLE_DIR, args.sample_rows)

    print("\nRow counts")
    for name, count in sorted(row_counts.items()):
        print(f"  {name:<28} {count:>12,}")
    print(f"\n  cumulative churn rate: {churn_rate:.1%}")
    print(f"  completed in {time.time() - started:.1f}s -> {out_dir}")
    return 0


def _write_samples(out_dir: Path, sample_dir: Path, n_rows: int) -> None:
    """Copy the first ``n_rows`` of each table into data/sample/ for version control."""
    sample_dir.mkdir(parents=True, exist_ok=True)
    for csv_path in sorted(out_dir.glob("*.csv")):
        df = pd.read_csv(csv_path, nrows=n_rows)
        df.to_csv(sample_dir / csv_path.name, index=False)
    # The manifest is the provenance record for the full extract, so it travels with
    # the sample even though the full data is not committed.
    manifest = out_dir / "generation_manifest.json"
    if manifest.exists():
        (sample_dir / "generation_manifest.json").write_text(manifest.read_text(encoding="utf-8"), encoding="utf-8")
    print(f"  wrote {n_rows}-row samples to {sample_dir}")


if __name__ == "__main__":
    raise SystemExit(main())
