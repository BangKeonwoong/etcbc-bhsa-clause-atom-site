from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

from synthetic_bhsa_support import build_synthetic_api


HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
MODULE_PATH = HERE / "bhsa_mother_candidate_skeleton_v5.py"


def load_module():
    spec = importlib.util.spec_from_file_location("bhsa_mother_candidate_skeleton_v5", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class MotherCandidatePrototypeV5Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = load_module()
        cls.api = build_synthetic_api()
        cls.empty_resources = cls.mod.ResourceTables()

    def test_miner_finds_quote_relative_and_manual_conjunction_candidates(self):
        gen = self.mod.build_generator(self.api, resources=self.empty_resources)
        report = self.mod.mine_resource_suggestions(gen, min_count=1)

        relative_rows = report["safe_additions"]["relative_lexemes"]["rows"]
        quote_rows = report["safe_additions"]["quote_verbs"]["rows"]
        conj_rows = report["manual_review"]["opening_conjunctions"]["rows"]

        self.assertIn("ASR[", {row["lex"] for row in relative_rows})
        self.assertIn("DBR[", {row["lex"] for row in quote_rows})
        w_row = next(row for row in conj_rows if row["lex"] == "W")
        self.assertEqual(w_row["hint"], "likely_coordinate_opener")

    def test_patch_resources_respects_quote_toggle(self):
        gen = self.mod.build_generator(self.api, resources=self.empty_resources)
        report = self.mod.mine_resource_suggestions(gen, min_count=1)

        patched_safe = self.mod.patch_resources_with_suggestions(self.empty_resources, report, include_quote_verbs=False)
        patched_quote = self.mod.patch_resources_with_suggestions(self.empty_resources, report, include_quote_verbs=True)

        self.assertIn("ASR[", patched_safe.relative_lexemes)
        self.assertNotIn("DBR[", patched_safe.quote_verbs)
        self.assertIn("DBR[", patched_quote.quote_verbs)

    def test_render_mining_markdown_contains_expected_sections(self):
        gen = self.mod.build_generator(self.api, resources=self.empty_resources)
        report = self.mod.mine_resource_suggestions(gen, min_count=1)
        md = self.mod.render_mining_markdown(report, top_n=10)
        self.assertIn("## Safe additions: relative_lexemes", md)
        self.assertIn("## Safe additions: quote_verbs", md)
        self.assertIn("## Manual review: opening conjunctions", md)

    def test_mine_json_roundtrip(self):
        gen = self.mod.build_generator(self.api, resources=self.empty_resources)
        report = self.mod.mine_resource_suggestions(gen, min_count=1)
        with tempfile.TemporaryDirectory() as tmpdir:
            out_path = Path(tmpdir) / "mine.json"
            out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
            loaded = json.loads(out_path.read_text(encoding="utf-8"))
        self.assertIn("safe_additions", loaded)
        self.assertIn("manual_review", loaded)
        self.assertIn("summary", loaded)


if __name__ == "__main__":
    unittest.main()
