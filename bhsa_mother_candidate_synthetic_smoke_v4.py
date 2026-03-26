from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

from synthetic_bhsa_support import build_seed_resources, build_synthetic_api


HERE = Path(__file__).resolve().parent
MODULE_PATH = HERE / "bhsa_mother_candidate_skeleton_v4.py"


def load_module():
    spec = importlib.util.spec_from_file_location("bhsa_mother_candidate_skeleton_v4", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def main() -> None:
    mod = load_module()
    api = build_synthetic_api()
    seed = build_seed_resources(mod)

    generator = mod.build_generator(api, resources=seed)
    learned = mod.fit_resources_from_gold(generator)
    fitted_generator = mod.build_generator(api, resources=learned)

    out_dir = HERE / "synthetic_smoke_outputs_v4"
    out_dir.mkdir(parents=True, exist_ok=True)

    weights_path = out_dir / "synthetic_weights_v4.json"
    eval_json_path = out_dir / "synthetic_eval_v4.json"
    eval_md_path = out_dir / "synthetic_eval_v4.md"
    diag_json_path = out_dir / "synthetic_diagnose_v4.json"
    diag_md_path = out_dir / "synthetic_diagnose_v4.md"
    pred_jsonl_path = out_dir / "synthetic_predictions_v4.jsonl"

    learned.save_json(weights_path)

    eval_report = mod.evaluate_generator(fitted_generator, top_k=3)
    eval_json_path.write_text(json.dumps(eval_report, ensure_ascii=False, indent=2), encoding="utf-8")
    eval_md_path.write_text(mod.render_eval_markdown(eval_report, top_k=3), encoding="utf-8")

    diag_report = mod.diagnose_generator(fitted_generator, top_k=3)
    diag_json_path.write_text(json.dumps(diag_report, ensure_ascii=False, indent=2), encoding="utf-8")
    diag_md_path.write_text(mod.render_diagnostic_markdown(diag_report, top_k=3, top_n=25), encoding="utf-8")

    mod.export_predictions(fitted_generator, pred_jsonl_path, top_k=3, fmt="jsonl")

    print(
        json.dumps(
            {
                "weights": str(weights_path),
                "eval_json": str(eval_json_path),
                "eval_md": str(eval_md_path),
                "diag_json": str(diag_json_path),
                "diag_md": str(diag_md_path),
                "predictions": str(pred_jsonl_path),
                "eval_summary": eval_report["summary"],
                "diag_summary": diag_report["resource_audit"]["summary"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
