#!/usr/bin/env bash
set -euo pipefail

PYTHON_BIN="${PYTHON_BIN:-python3}"
VENV_DIR="${1:-.venv-bhsa}"

"${PYTHON_BIN}" -m venv "${VENV_DIR}"
# shellcheck disable=SC1090
source "${VENV_DIR}/bin/activate"
python -m pip install --upgrade pip
python -m pip install text-fabric
python - <<'PY'
from tf.app import use
A = use("ETCBC/bhsa", silent="deep")
print("TF app ready:", A)
PY
