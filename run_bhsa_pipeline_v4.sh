#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3}"
OUT_DIR="${1:-${SCRIPT_DIR}/bhsa_run_outputs_v4}"
RESOURCE_JSON="${2:-:official_seed}"
APP_NAME="${APP_NAME:-ETCBC/bhsa}"
TOP_K="${TOP_K:-5}"
POOL_MODE="${POOL_MODE:-instruction}"
TOP_N="${TOP_N:-25}"

mkdir -p "${OUT_DIR}"

"${PYTHON_BIN}" "${SCRIPT_DIR}/bhsa_mother_candidate_skeleton_v4.py" fit \
  "${OUT_DIR}/weights.json" \
  --resources "${RESOURCE_JSON}" \
  --app "${APP_NAME}" \
  --pool-mode "${POOL_MODE}"

"${PYTHON_BIN}" "${SCRIPT_DIR}/bhsa_mother_candidate_skeleton_v4.py" eval \
  --resources "${OUT_DIR}/weights.json" \
  --app "${APP_NAME}" \
  --pool-mode "${POOL_MODE}" \
  --top-k "${TOP_K}" \
  --json-out "${OUT_DIR}/eval.json" \
  --md-out "${OUT_DIR}/eval.md"

"${PYTHON_BIN}" "${SCRIPT_DIR}/bhsa_mother_candidate_skeleton_v4.py" diagnose \
  --resources "${OUT_DIR}/weights.json" \
  --app "${APP_NAME}" \
  --pool-mode "${POOL_MODE}" \
  --top-k "${TOP_K}" \
  --top-n "${TOP_N}" \
  --json-out "${OUT_DIR}/diagnose.json" \
  --md-out "${OUT_DIR}/diagnose.md"

"${PYTHON_BIN}" "${SCRIPT_DIR}/bhsa_mother_candidate_skeleton_v4.py" ablate \
  --resources "${OUT_DIR}/weights.json" \
  --app "${APP_NAME}" \
  --pool-mode "${POOL_MODE}" \
  --top-k "${TOP_K}" \
  --json-out "${OUT_DIR}/ablate.json" \
  --md-out "${OUT_DIR}/ablate.md"

"${PYTHON_BIN}" "${SCRIPT_DIR}/bhsa_mother_candidate_skeleton_v4.py" export \
  "${OUT_DIR}/predictions.jsonl" \
  --resources "${OUT_DIR}/weights.json" \
  --app "${APP_NAME}" \
  --pool-mode "${POOL_MODE}" \
  --top-k "${TOP_K}" \
  --format jsonl

printf 'Saved v4 outputs in %s\n' "${OUT_DIR}"
