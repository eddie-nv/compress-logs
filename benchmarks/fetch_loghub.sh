#!/usr/bin/env bash
# Downloads the OpenSSH 2k subset from LogHub-2.0 for back-pocket benchmarking.
# Usage: bash benchmarks/fetch_loghub.sh
set -euo pipefail

DEST="benchmarks/loghub"
mkdir -p "$DEST"

BASE="https://raw.githubusercontent.com/logpai/loghub/master/OpenSSH"

echo "Fetching OpenSSH_2k.log_structured.csv ..."
curl -fsSL "$BASE/OpenSSH_2k.log_structured.csv" -o "$DEST/OpenSSH_2k.log_structured.csv"

echo "Fetching OpenSSH_2k.log ..."
curl -fsSL "$BASE/OpenSSH_2k.log" -o "$DEST/OpenSSH_2k.log"

echo "Done. Files in $DEST/"
ls -lh "$DEST/"
