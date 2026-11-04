#!/usr/bin/env bash
# Runs the whole pipeline. Reads the FAERS zips and Canada Vigilance extract
# that Safety Signal Explorer downloaded (~/ssx_data/raw), and writes the
# database to $GLP_DATA (default ~/glp1_data), outside OneDrive.
# Usage: bash run_all.sh [python]
set -euo pipefail
PY="${1:-python3}"
cd "$(dirname "$0")"
"$PY" scripts/01_download_faers.py
"$PY" scripts/02_load_faers.py
"$PY" scripts/03_deduplicate.py
"$PY" scripts/04_signals.py
"$PY" scripts/05_validate.py || { echo "Validation failed; stop and read the table above."; exit 1; }
CV="${GLP_CV_RAW:-$HOME/ssx_data/raw/canada_vigilance}"
if [ -d "$CV" ]; then
  "$PY" scripts/06_canada_vigilance.py
else
  echo "No Canada Vigilance extract at $CV; skipping 06."
fi
"$PY" scripts/07_export.py
