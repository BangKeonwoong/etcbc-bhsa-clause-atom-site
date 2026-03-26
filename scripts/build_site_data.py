from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import bhsa_mother_candidate_skeleton_v5 as core
import bhsa_static_site_builder as site_builder


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build BHSA clause-atom JSON data for the static site")
    parser.add_argument("--app", default="ETCBC/bhsa", help="Text-Fabric app name")
    parser.add_argument(
        "--resources",
        default=":official_seed",
        help="ResourceTables JSON file or :official_seed for the built-in seed",
    )
    parser.add_argument("--top-k", type=int, default=5, help="How many candidates to materialize per atom")
    parser.add_argument("--limit", type=int, help="Limit the number of clause atoms")
    parser.add_argument("--outdir", default="site/data", help="Output directory for generated JSON")
    parser.add_argument("--books", nargs="*", help="Limit to one or more book names")
    parser.add_argument(
        "--pool-mode",
        default="instruction",
        choices=("instruction", "tab_only"),
        help="Candidate pool pruning mode",
    )
    parser.add_argument(
        "--fit",
        dest="fit",
        action="store_true",
        default=True,
        help="Fit weights from gold mother edges before export (default: on)",
    )
    parser.add_argument(
        "--no-fit",
        dest="fit",
        action="store_false",
        help="Use the provided resources as-is without fitting",
    )
    parser.add_argument("--alpha", type=float, default=0.5, help="Laplace smoothing alpha for fit mode")
    parser.add_argument("--weights-out", help="Optional path to save the resolved resource tables")
    parser.add_argument("--synthetic", action="store_true", help="Use the bundled synthetic fixture")
    return parser


def main(argv: Sequence[str] | None = None) -> None:
    args = build_arg_parser().parse_args(argv)
    books = site_builder.parse_books(args.books)

    if args.synthetic:
        from synthetic_bhsa_support import build_synthetic_api

        api = build_synthetic_api()
        app_name = "synthetic-bhsa"
        source_kind = "synthetic"
    else:
        api = core.load_bhsa(args.app)
        app_name = args.app
        source_kind = "bhsa"

    dataset = site_builder.build_site_dataset(
        api,
        app_name=app_name,
        resource_spec=args.resources,
        fit=args.fit,
        alpha=args.alpha,
        top_k=args.top_k,
        books=books,
        limit=args.limit,
        pool_mode=args.pool_mode,
        source_kind=source_kind,
    )
    outdir = site_builder.write_data_bundle(dataset, output_dir=args.outdir)

    if args.weights_out:
        weights_path = Path(args.weights_out)
        weights_path.parent.mkdir(parents=True, exist_ok=True)
        weights_path.write_text(
            json.dumps(dataset["meta"]["resources_snapshot"], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    print(
        json.dumps(
            {
                "output_dir": str(outdir.resolve()),
                "atom_count": dataset["meta"]["atom_count"],
                "book_count": len(dataset["meta"]["books"]),
                "fit": args.fit,
                "source_kind": dataset["meta"]["source_kind"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
