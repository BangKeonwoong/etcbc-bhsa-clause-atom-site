from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
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


class MotherCandidatePrototypeV4Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = load_module()
        cls.api = build_synthetic_api()
        cls.seed_resources = build_seed_resources(cls.mod)

    def test_top_k_3_eval_summary_is_not_double_counted(self):
        gen = self.mod.build_generator(self.api, resources=self.seed_resources)
        learned = self.mod.fit_resources_from_gold(gen)
        gen2 = self.mod.build_generator(self.api, resources=learned)
        report = self.mod.evaluate_generator(gen2, top_k=3)
        summary = report["summary"]
        self.assertEqual(summary["hit@1"], 1.0)
        self.assertEqual(summary["hit@3"], 1.0)
        md = self.mod.render_eval_markdown(report, top_k=3)
        self.assertEqual(md.count("- hit@3:"), 1)
        self.assertIn("| Book | with_gold | pool_cov | scored_cov | hit@1 | hit@3 | top1_rela_acc |", md)

    def test_diagnose_resource_audit_reports_expected_coverages(self):
        gen = self.mod.build_generator(self.api, resources=self.seed_resources)
        learned = self.mod.fit_resources_from_gold(gen)
        gen2 = self.mod.build_generator(self.api, resources=learned)
        diag = self.mod.diagnose_generator(gen2, top_k=3)
        audit = diag["resource_audit"]["summary"]
        self.assertEqual(audit["opening_conjunction_occurrence_coverage"], 0.5)
        self.assertEqual(audit["opening_conjunction_type_coverage"], 0.5)
        self.assertEqual(audit["relative_marker_occurrence_coverage"], 1.0)
        self.assertEqual(audit["quote_governor_candidate_coverage"], 1.0)

    def test_render_diagnostic_markdown_avoids_duplicate_topk_column(self):
        gen = self.mod.build_generator(self.api, resources=self.seed_resources)
        learned = self.mod.fit_resources_from_gold(gen)
        gen2 = self.mod.build_generator(self.api, resources=learned)
        diag = self.mod.diagnose_generator(gen2, top_k=3)
        md = self.mod.render_diagnostic_markdown(diag, top_k=3, top_n=10)
        self.assertEqual(md.count("- hit@3:"), 1)
        relation_header = next(line for line in md.splitlines() if line.startswith("| gold_rela |"))
        self.assertEqual(relation_header.count("hit@3"), 1)
        self.assertIn("## Top uncovered opening conjunction lexemes", md)

    def test_diagnose_json_roundtrip(self):
        gen = self.mod.build_generator(self.api, resources=self.seed_resources)
        learned = self.mod.fit_resources_from_gold(gen)
        gen2 = self.mod.build_generator(self.api, resources=learned)
        diag = self.mod.diagnose_generator(gen2, top_k=3)
        with tempfile.TemporaryDirectory() as tmpdir:
            out_path = Path(tmpdir) / "diag.json"
            out_path.write_text(json.dumps(diag, ensure_ascii=False, indent=2), encoding="utf-8")
            loaded = json.loads(out_path.read_text(encoding="utf-8"))
        self.assertIn("resource_audit", loaded)
        self.assertIn("per_relation", loaded)
        self.assertIn("gold_evidence_coverage", loaded)


if __name__ == "__main__":
    unittest.main()
