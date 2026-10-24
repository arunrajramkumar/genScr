#!/usr/bin/env bash
# Load exported CSVs into a (new) Postgres, e.g. Render / Neon / Supabase. Needs the psql client.
#   TARGET_URL='postgresql://user:pass@host:5432/db?sslmode=require' scripts/import_data.sh
# Creates the schema (db/init.sql is idempotent), then REPLACES the contents of each table.
set -euo pipefail

: "${TARGET_URL:?Set TARGET_URL to the external connection string of the hosted database}"
IN="${IN:-data/export}"
TABLES=(stocks prices fundamentals stock_metrics corporate_actions index_prices index_constituents symbol_changes)

psql "$TARGET_URL" -v ON_ERROR_STOP=1 -q -f db/init.sql

for t in "${TABLES[@]}"; do
  f="$IN/$t.csv.gz"
  [[ -f "$f" ]] || { echo "skipping $t: $f not found"; continue; }
  cols=$(gunzip -c "$f" 2>/dev/null | head -1 || true)
  psql "$TARGET_URL" -v ON_ERROR_STOP=1 -q -c "TRUNCATE $t"
  gunzip -c "$f" | psql "$TARGET_URL" -v ON_ERROR_STOP=1 -q -c "\copy $t ($cols) FROM STDIN WITH (FORMAT csv, HEADER)"
  psql "$TARGET_URL" -q -c "ANALYZE $t"  # just our tables; system catalogs need superuser
  echo "$t: $(psql "$TARGET_URL" -At -c "SELECT count(*) FROM $t") rows"
done
echo "Done."
