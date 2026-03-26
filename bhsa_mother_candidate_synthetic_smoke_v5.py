from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

from synthetic_bhsa_support import build_seed_resources, build_synthetic_api


HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
MODULE_PATH = HERE / "bhsa_mother_candidate_skeleton_v5.py"
OUTDIR = HERE / "synthetic_smoke_outputs_v5"


def load_module():
    spec = importlib.util.spec_from_file_location("bhsa_mother_candidate_skeleton_v5", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def main() -> None:
    mod = load_module()
    api = build_synthetic_api()
    OUTDIR.mkdir(exist_ok=True)

    seed_resources = build_seed_resources(mod)
    gen_seed = mod.build_generator(api, resources=seed_resources)
    learned = mod.fit_resources_from_gold(gen_seed)
    gen_learned = mod.build_generator(api, resources=learned)

    eval_report = mod.evaluate_generator(gen_learned, top_k=3)
    diag_report = mod.diagnose_generator(gen_learned, top_k=3)
    preds = []
    for daughter in gen_learned.ctx.iter_atoms():
        pred_rows = [mod.candidate_to_dict(c, gen_learned.ctx) for c in gen_learned.predict_for_atom(daughter, top_k=3)]
        preds.append({
            "daughter": daughter,
            "predictions": pred_rows,
        })

    empty_resources = mod.ResourceTables()
    gen_empty = mod.build_generator(api, resources=empty_resources)
    mine_report = mod.mine_resource_suggestions(gen_empty, min_count=1)
    patched = mod.patch_resources_with_suggestions(empty_resources, mine_report, include_quote_verbs=True)

    (OUTDIR / "synthetic_eval_v5.json").write_text(json.dumps(eval_report, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUTDIR / "synthetic_eval_v5.md").write_text(mod.render_eval_markdown(eval_report, top_k=3), encoding="utf-8")
    (OUTDIR / "synthetic_diagnose_v5.json").write_text(json.dumps(diag_report, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUTDIR / "synthetic_diagnose_v5.md").write_text(mod.render_diagnostic_markdown(diag_report, top_k=3), encoding="utf-8")
    (OUTDIR / "synthetic_predictions_v5.jsonl").write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in preds),
        encoding="utf-8",
    )
    (OUTDIR / "synthetic_weights_v5.json").write_text(json.dumps(learned.to_json_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    (OUTDIR / "synthetic_mine_v5.json").write_text(json.dumps(mine_report, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUTDIR / "synthetic_mine_v5.md").write_text(mod.render_mining_markdown(mine_report, top_n=10, include_quote_verbs=True), encoding="utf-8")
    (OUTDIR / "synthetic_mined_patch_v5.json").write_text(json.dumps(patched.to_json_dict(), ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
