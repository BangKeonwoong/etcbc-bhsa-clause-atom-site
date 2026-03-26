#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3}"
OUT_DIR="${1:-${SCRIPT_DIR}/bhsa_run_outputs}"
RESOURCE_JSON="${2:-${SCRIPT_DIR}/resource_tables_template.json}"
APP_NAME="${APP_NAME:-ETCBC/bhsa}"
TOP_K="${TOP_K:-5}"
POOL_MODE="${POOL_MODE:-instruction}"

mkdir -p "${OUT_DIR}"

"${PYTHON_BIN}" "${SCRIPT_DIR}/bhsa_mother_candidate_skeleton_v2.py" fit \
  "${OUT_DIR}/weights.json" \
  --resources "${RESOURCE_JSON}" \
  --app "${APP_NAME}" \
  --pool-mode "${POOL_MODE}"

"${PYTHON_BIN}" "${SCRIPT_DIR}/bhsa_mother_candidate_skeleton_v2.py" eval \
  --resources "${OUT_DIR}/weights.json" \
  --app "${APP_NAME}" \
  --pool-mode "${POOL_MODE}" \
  --top-k "${TOP_K}" \
  --json-out "${OUT_DIR}/eval.json" \
  --md-out "${OUT_DIR}/eval.md"

"${PYTHON_BIN}" "${SCRIPT_DIR}/bhsa_mother_candidate_skeleton_v2.py" ablate \
  --resources "${OUT_DIR}/weights.json" \
  --app "${APP_NAME}" \
  --pool-mode "${POOL_MODE}" \
  --top-k "${TOP_K}" \
  --json-out "${OUT_DIR}/ablate.json" \
  --md-out "${OUT_DIR}/ablate.md"

"${PYTHON_BIN}" "${SCRIPT_DIR}/bhsa_mother_candidate_skeleton_v2.py" export \
  "${OUT_DIR}/predictions.jsonl" \
  --resources "${OUT_DIR}/weights.json" \
  --app "${APP_NAME}" \
  --pool-mode "${POOL_MODE}" \
  --top-k "${TOP_K}" \
  --format jsonl

printf 'Saved outputs in %s\n' "${OUT_DIR}"
