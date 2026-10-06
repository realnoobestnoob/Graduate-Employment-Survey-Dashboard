#!/usr/bin/env python3
"""
GES Dashboard — Backend Ingestion Script
=========================================
Run this locally whenever you have a new GES CSV to add to the dataset.
The app does NOT need to be running; changes take effect on next app load.

Usage:
    python scripts/ingest.py <path_to_csv>

Example:
    python scripts/ingest.py ~/Downloads/ges_2025.csv

Expected CSV columns (order-independent, case-insensitive):
    year, university, school, degree,
    employment_rate_overall, employment_rate_ft_perm,
    basic_monthly_mean, basic_monthly_median,
    gross_monthly_mean, gross_monthly_median,
    gross_monthly_25th_percentile, gross_monthly_75th_percentile
"""

import sys
import io
import pathlib

# ── Resolve project root (one level up from scripts/) ──
ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

try:
    from src.etl import ingest_new_file
except ImportError as e:
    print(f"[ERROR] Could not import src.etl: {e}")
    print("        Make sure you run this script from the project root or that")
    print("        the virtual environment with all dependencies is active.")
    sys.exit(1)


def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(0)

    csv_path = pathlib.Path(sys.argv[1]).expanduser().resolve()

    if not csv_path.exists():
        print(f"[ERROR] File not found: {csv_path}")
        sys.exit(1)

    if csv_path.suffix.lower() != ".csv":
        print(f"[WARN]  File does not have a .csv extension: {csv_path.name}")

    print(f"[INFO]  Reading:  {csv_path}")

    # Wrap in a BytesIO so ingest_new_file receives the same interface
    # it would from Streamlit's file uploader.
    with open(csv_path, "rb") as f:
        buf      = io.BytesIO(f.read())
        buf.name = csv_path.name  # ingest_new_file may use the filename

    try:
        df_master, added = ingest_new_file(buf)
    except ValueError as e:
        print(f"[ERROR] Validation failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"[ERROR] Unexpected error during ingestion: {e}")
        raise

    if added == 0:
        print("[INFO]  No new rows added — all records already exist in the master dataset.")
    else:
        print(f"[OK]    Added {added:,} new row(s).")

    print(f"[INFO]  Master dataset now contains {len(df_master):,} rows "
          f"({df_master['year'].min()}–{df_master['year'].max()}).")
    print("[INFO]  The dashboard will pick up the changes on next load "
          "(or run `streamlit cache clear` if it is already running).")


if __name__ == "__main__":
    main()
