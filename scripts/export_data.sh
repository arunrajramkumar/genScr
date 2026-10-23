#!/usr/bin/env bash
# Export all genScr tables to gzipped CSVs (portable: works for TimescaleDB or plain Postgres targets).
#   scripts/export_data.sh            # from the docker compose db
#   SOURCE_URL=postgresql://... scripts/export_data.sh   # from any Postgres (needs psql)
set -euo pipefail

OUT="${OUT:-data/export}"
TABLES=(stocks prices fundamentals stock_metrics)
mkdir -p "$OUT"

run_psql() {
  if [[ -n "${SOURCE_URL:-}" ]]; then
    psql "$SOURCE_URL" -v ON_ERROR_STOP=1 "$@"
  else
    docker compose exec -T db psql -U genscr -d genscr -v ON_ERROR_STOP=1 "$@"
  fi
}

for t in "${TABLES[@]}"; do
  run_psql -c "\copy (SELECT * FROM $t) TO STDOUT WITH (FORMAT csv, HEADER)" | gzip > "$OUT/$t.csv.gz"
  echo "$t: $(gunzip -c "$OUT/$t.csv.gz" | tail -n +2 | wc -l | tr -d ' ') rows -> $OUT/$t.csv.gz"
done
