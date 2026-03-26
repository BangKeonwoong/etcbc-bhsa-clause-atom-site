#!/usr/bin/env bash
set -euo pipefail

OUTDIR="${1:-outputs_v5}"
RESOURCES="${2:-:official_seed}"
APP="${3:-ETCBC/bhsa}"
MIN_COUNT="${4:-2}"

mkdir -p "$OUTDIR"

python bhsa_mother_candidate_skeleton_v5.py fit "$OUTDIR/weights.json" \
  --app "$APP" \
  --resources "$RESOURCES"

python bhsa_mother_candidate_skeleton_v5.py eval \
  --app "$APP" \
  --resources "$OUTDIR/weights.json" \
  --json-out "$OUTDIR/eval.json" \
  --md-out "$OUTDIR/eval.md"

python bhsa_mother_candidate_skeleton_v5.py ablate \
  --app "$APP" \
  --resources "$OUTDIR/weights.json" \
  --json-out "$OUTDIR/ablate.json" \
  --md-out "$OUTDIR/ablate.md"

python bhsa_mother_candidate_skeleton_v5.py diagnose \
  --app "$APP" \
  --resources "$OUTDIR/weights.json" \
  --json-out "$OUTDIR/diagnose.json" \
  --md-out "$OUTDIR/diagnose.md"

python bhsa_mother_candidate_skeleton_v5.py mine \
  --app "$APP" \
  --resources "$OUTDIR/weights.json" \
  --min-count "$MIN_COUNT" \
  --json-out "$OUTDIR/mine.json" \
  --md-out "$OUTDIR/mine.md" \
  --patch-out "$OUTDIR/mined_patch.json"
