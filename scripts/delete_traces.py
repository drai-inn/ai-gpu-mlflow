# /// script
# requires-python = ">=3.12"
# dependencies = ["mlflow-skinny==3.12.0"]
# ///
"""Delete traces from one MLflow experiment, oldest first, in small batches.

Each trace's spans, tags, request metadata, assessments and trace metrics are removed with it
(ON DELETE CASCADE from trace_info). The experiment and its runs are kept.

Small batches keep each delete transaction, and the WAL it writes to the database volume, small.
Freed space is reused inside Postgres; returning it to the filesystem needs `VACUUM FULL spans`.

Needs an MLflow admin: set MLFLOW_TRACKING_URI, MLFLOW_TRACKING_USERNAME and
MLFLOW_TRACKING_PASSWORD (an access token).

    uv run scripts/delete_traces.py vdsai-dev
    uv run scripts/delete_traces.py vdsai-prod --before 2026-09-01
"""

import argparse
import time
from datetime import datetime, timezone

from mlflow import MlflowClient


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("experiment_name")
    parser.add_argument("--before", help="only delete traces older than this UTC date (YYYY-MM-DD)")
    parser.add_argument("--batch-size", type=int, default=200)
    parser.add_argument("--pause", type=float, default=2.0, help="seconds to wait between batches")
    args = parser.parse_args()

    client = MlflowClient()
    experiment = client.get_experiment_by_name(args.experiment_name)
    if experiment is None:
        raise SystemExit(f"no experiment named {args.experiment_name!r}")

    cutoff = datetime.now(timezone.utc)
    if args.before:
        cutoff = datetime.fromisoformat(args.before).replace(tzinfo=timezone.utc)
    cutoff_ms = int(cutoff.timestamp() * 1000)
    print(f"deleting traces in {experiment.name} (id {experiment.experiment_id}) older than {cutoff.isoformat()}")

    total = 0
    while deleted := client.delete_traces(
        experiment.experiment_id, max_timestamp_millis=cutoff_ms, max_traces=args.batch_size
    ):
        total += deleted
        print(f"{datetime.now():%H:%M:%S} deleted {deleted} (total {total})", flush=True)
        time.sleep(args.pause)

    print(f"done: {total} traces deleted")


if __name__ == "__main__":
    main()
