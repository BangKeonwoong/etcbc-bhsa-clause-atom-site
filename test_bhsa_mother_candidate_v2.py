from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

from synthetic_bhsa_support import build_seed_resources, build_synthetic_api


def load_module():
    path = Path(__file__).with_name("bhsa_mother_candidate_skeleton_v2.py")
    spec = importlib.util.spec_from_file_location("bhsa_mother_candidate_skeleton_v2", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class MotherCandidatePrototypeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = load_module()
        cls.api = build_synthetic_api()
        cls.seed_resources = build_seed_resources(cls.mod)

    def test_root_rightward_candidate_is_zeroed(self):
        gen = self.mod.build_generator(self.api, resources=self.seed_resources)
        preds = gen.predict_for_atom(1, top_k=None)
        self.assertEqual(preds, [])

    def test_instruction_pool_contains_expected_candidates(self):
        gen = self.mod.build_generator(self.api, resources=self.seed_resources)
        pool = gen.pool_builder.build(3)
        self.assertEqual(pool, (2, 1, 4))

    def test_fit_then_eval_is_perfect_on_synthetic_corpus(self):
        gen = self.mod.build_generator(self.api, resources=self.seed_resources)
        learned = self.mod.fit_resources_from_gold(gen)
        gen2 = self.mod.build_generator(self.api, resources=learned)
        report = self.mod.evaluate_generator(gen2, top_k=3)
        summary = report["summary"]
        self.assertEqual(summary["candidate_pool_coverage"], 1.0)
        self.assertEqual(summary["scored_coverage"], 1.0)
        self.assertEqual(summary["hit@1"], 1.0)
        self.assertEqual(summary["hit@3"], 1.0)
        self.assertEqual(summary["mrr"], 1.0)
        md = self.mod.render_eval_markdown(report, top_k=3)
        self.assertEqual(md.count("- hit@3:"), 1)
        self.assertIn("| Book | with_gold | pool_cov | scored_cov | hit@1 | hit@3 | top1_rela_acc |", md)

    def test_export_jsonl_writes_predictions(self):
        gen = self.mod.build_generator(self.api, resources=self.seed_resources)
        learned = self.mod.fit_resources_from_gold(gen)
        gen2 = self.mod.build_generator(self.api, resources=learned)
        with tempfile.TemporaryDirectory() as tmpdir:
            out_path = Path(tmpdir) / "predictions.jsonl"
            self.mod.export_predictions(gen2, out_path, top_k=3, fmt="jsonl")
            lines = [json.loads(line) for line in out_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        self.assertEqual(len(lines), 4)
        daughter2 = next(row for row in lines if row["daughter"] == 2)
        self.assertEqual(daughter2["predictions"][0]["mother"], 1)


if __name__ == "__main__":
    unittest.main()
