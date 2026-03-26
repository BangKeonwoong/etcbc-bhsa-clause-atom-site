from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import bhsa_static_site_builder as site_builder
from synthetic_bhsa_support import build_synthetic_api


class StaticSiteBuilderTests(unittest.TestCase):
    def test_build_site_dataset_with_synthetic_fixture(self):
        dataset = site_builder.build_site_dataset(
            build_synthetic_api(),
            app_name="synthetic-bhsa",
            resource_spec=":official_seed",
            fit=True,
            top_k=3,
            source_kind="synthetic",
        )

        self.assertEqual(dataset["meta"]["atom_count"], 4)
        self.assertEqual(dataset["meta"]["resource_mode"], "fit_from_gold")
        self.assertEqual(dataset["meta"]["source_kind"], "synthetic")

        atom_two = dataset["details"]["2"]
        self.assertEqual(atom_two["atom"], 2)
        self.assertEqual(atom_two["prev_atom"], 1)
        self.assertEqual(atom_two["next_atom"], 3)
        self.assertEqual(atom_two["gold_mother"], 1)
        self.assertTrue(atom_two["predictions"])
        self.assertEqual(atom_two["predictions"][0]["rank"], 1)

    def test_write_static_site_outputs_index_meta_and_atom_pages(self):
        dataset = site_builder.build_site_dataset(
            build_synthetic_api(),
            app_name="synthetic-bhsa",
            resource_spec=":official_seed",
            fit=False,
            top_k=2,
            source_kind="synthetic",
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            site_src = tmp_path / "site-src"
            site_src.mkdir()
            (site_src / "index.html").write_text("<!doctype html><title>test</title>", encoding="utf-8")

            out_dir = site_builder.write_static_site(
                dataset,
                output_dir=tmp_path / "dist",
                site_dir=site_src,
            )

            self.assertTrue((out_dir / "index.html").exists())
            self.assertTrue((out_dir / "data" / "meta.json").exists())
            self.assertTrue((out_dir / "data" / "index.json").exists())
            self.assertTrue((out_dir / "data" / "catalog.json").exists())
            self.assertTrue((out_dir / "data" / "atoms" / "1.json").exists())

            meta = json.loads((out_dir / "data" / "meta.json").read_text(encoding="utf-8"))
            index = json.loads((out_dir / "data" / "index.json").read_text(encoding="utf-8"))
            catalog = json.loads((out_dir / "data" / "catalog.json").read_text(encoding="utf-8"))
            atom_one = json.loads((out_dir / "data" / "atoms" / "1.json").read_text(encoding="utf-8"))

            self.assertEqual(meta["atom_count"], 4)
            self.assertEqual(len(index["atoms"]), 4)
            self.assertEqual(len(catalog["books"]), 1)
            self.assertEqual(atom_one["atom"], 1)
            self.assertIn("view", atom_one)
            self.assertIn("predictions", atom_one)


if __name__ == "__main__":
    unittest.main()
