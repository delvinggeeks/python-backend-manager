#!/usr/bin/env bash
# OpenAPI fuzzing gate (Schemathesis) — boots the app and asserts that no endpoint
# returns a 5xx server error under property-based, schema-aware fuzzing. This catches
# unhandled exceptions and injection / path-traversal payloads that crash a handler.
# Run it via `just fuzz`, directly as `bash scripts/run_fuzz.sh`, or from CI unchanged.
#
# Why a live server instead of in-process ASGI: Schemathesis drives the app from a sync
# context, so an in-pytest run would bind the async DB engine's pooled connections to a
# throwaway per-example loop and break on the second example. A real uvicorn process runs
# one persistent loop, so the connection pool stays consistent — the reliable path.
set -euo pipefail

PORT="${FUZZ_PORT:-8773}"

# Pin Python's hash seed so set/dict iteration order (hence the order Schemathesis explores
# operations and parameters) is identical across runs — part of making the gate reproducible.
export PYTHONHASHSEED=0

# Dummy, non-secret config so the app boots in any capability combination. A throwaway
# sqlite DB stands in for Postgres; the secrets are placeholders — fuzzing only hits the
# local app and provider SDKs are constructed, never invoked, so no real value is needed.
export DATABASE_URL="${DATABASE_URL:-sqlite+aiosqlite:///$PWD/.fuzz.sqlite3}"
export USERS_JWT_SECRET="${USERS_JWT_SECRET:-fuzz-only-not-a-real-secret}"
export PAYMENTS_PROVIDER="${PAYMENTS_PROVIDER:-stripe}"
export STRIPE_API_KEY="${STRIPE_API_KEY:-sk_test_fuzz}"
export STRIPE_WEBHOOK_SECRET="${STRIPE_WEBHOOK_SECRET:-whsec_fuzz}"
export RAZORPAY_KEY_ID="${RAZORPAY_KEY_ID:-rzp_test_fuzz}"
export RAZORPAY_KEY_SECRET="${RAZORPAY_KEY_SECRET:-fuzz-only}"

# Start from a clean throwaway DB so a local re-run is reproducible (CI is always fresh).
rm -f .fuzz.sqlite3 .fuzz.sqlite3-shm .fuzz.sqlite3-wal

# Create the schema on the throwaway DB so DB-backed endpoints exercise real queries
# instead of failing to boot. DB-less services ship no alembic.ini — nothing to migrate.
if [ -f alembic.ini ]; then
  uv run alembic upgrade head
fi

# Boot the app in the background and guarantee teardown on any exit.
uv run uvicorn app.main:app --port "$PORT" --log-level warning > .fuzz-server.log 2>&1 &
SERVER_PID=$!
cleanup() { kill "$SERVER_PID" 2>/dev/null || true; }
trap cleanup EXIT

# Wait for liveness; fail loudly with the server log if it never comes up.
for _ in $(seq 1 30); do
  if curl -sf "http://127.0.0.1:$PORT/health" >/dev/null 2>&1; then break; fi
  sleep 1
done
if ! curl -sf "http://127.0.0.1:$PORT/health" >/dev/null 2>&1; then
  echo "::error::app did not become healthy on port $PORT" >&2
  cat .fuzz-server.log >&2
  exit 1
fi

# Skip cleanly when there is no business API surface to fuzz (e.g. an observability-only
# service exposes nothing but the excluded health/agent probes) — that is "nothing to do",
# not a failure.
FUZZABLE=$(
  curl -s "http://127.0.0.1:$PORT/openapi.json" | uv run python -c "
import json, re, sys

excluded = re.compile(r'^/(agent|health|ready|metrics|livez)')
paths = json.load(sys.stdin).get('paths', {})
print(sum(1 for p in paths if not excluded.search(p)))
"
)
if [ "$FUZZABLE" -eq 0 ]; then
  echo "no fuzzable API operations (only health/agent probes present) — skipping"
  exit 0
fi

# Fuzz. `not_a_server_error` is the high-signal check: any 5xx fails the gate. The
# schema-conformance / undocumented-status checks are intentionally OFF — these APIs
# validate stricter than the schema documents and return 401/403/422 by design (not bugs).
# `/agent` (503 with no LLM backend) and the health/readiness/metrics probes are excluded.
#
# Reproducibility (a flaky gate would break auto-merge, and could intermittently catch —
# then miss — a real boundary bug). A PINNED seed + no example database + PYTHONHASHSEED
# above make the verdict identical across CI runs; only the schema-driven `coverage,fuzzing`
# phases run (the `stateful` phase feeds freshly-minted response UUIDs back into generation,
# so it is not reproducible). This is the same discipline as the pinned pytest-randomly
# seed: the blocking gate is a deterministic regression guard against 5xx on the inputs this
# seed explores; a deeper varying-seed sweep (raise FUZZ_MAX_EXAMPLES / FUZZ_SEED, or run it
# nightly) is the bug-hunting complement and is intentionally left out of the merge path.
uv run schemathesis run "http://127.0.0.1:$PORT/openapi.json" \
  --exclude-path-regex '^/(agent|health|ready|metrics|livez)' \
  --checks not_a_server_error \
  --suppress-health-check=filter_too_much,data_too_large,too_slow \
  --phases coverage,fuzzing \
  --seed "${FUZZ_SEED:-0}" \
  --generation-database=none \
  --warnings off \
  --max-examples "${FUZZ_MAX_EXAMPLES:-20}" \
  --no-color
