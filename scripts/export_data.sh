#!/usr/bin/env bash
# Export all genScr tables to gzipped CSVs (portable: works for TimescaleDB or plain Postgres targets).
#   scripts/export_data.sh            # from the docker compose db
#   SOURCE_URL=postgresql://... scripts/export_data.sh   # from any Postgres (needs psql)
#   SINCE=2021-01-01 scripts/export_data.sh            # only recent prices (smaller, e.g. for a free-tier db)
set -euo pipefail

OUT="${OUT:-data/export}"
TABLES=(stocks prices fundamentals stock_metrics corporate_actions)
mkdir -p "$OUT"

run_psql() {
  if [[ -n "${SOURCE_URL:-}" ]]; then
    psql "$SOURCE_URL" -v ON_ERROR_STOP=1 "$@"
  else
    docker compose exec -T db psql -U genscr -d genscr -v ON_ERROR_STOP=1 "$@"
  fi
}

for t in "${TABLES[@]}"; do
  where=""
  [[ "$t" == "prices" && -n "${SINCE:-}" ]] && where="WHERE trade_date >= DATE '$SINCE'"
  run_psql -c "\copy (SELECT * FROM $t $where) TO STDOUT WITH (FORMAT csv, HEADER)" | gzip > "$OUT/$t.csv.gz"
  echo "$t: $(gunzip -c "$OUT/$t.csv.gz" | tail -n +2 | wc -l | tr -d ' ') rows -> $OUT/$t.csv.gz"
done
