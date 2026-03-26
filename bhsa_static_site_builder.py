from __future__ import annotations

import argparse
import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

import bhsa_mother_candidate_skeleton_v5 as core


def slugify_book(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.strip().lower())
    return slug.strip("-") or "unknown"


def section_to_dict(section: Any) -> dict[str, Any]:
    if isinstance(section, (list, tuple)):
        book = section[0] if len(section) > 0 else None
        chapter = section[1] if len(section) > 1 else None
        verse = section[2] if len(section) > 2 else None
        label_parts = [str(part) for part in (book, chapter, verse) if part not in (None, "")]
        return {
            "book": None if book is None else str(book),
            "chapter": chapter,
            "verse": verse,
            "label": " ".join(label_parts),
        }
    return {
        "book": str(section),
        "chapter": None,
        "verse": None,
        "label": str(section),
    }


def phrase_to_dict(phrase: core.PhraseInfo) -> dict[str, Any]:
    return {
        "node": phrase.node,
        "first_slot": phrase.first_slot,
        "last_slot": phrase.last_slot,
        "function": phrase.function,
        "typ": phrase.typ,
        "text": phrase.text,
        "lexemes": list(phrase.lexemes),
    }


def view_to_dict(view: core.ClauseAtomView) -> dict[str, Any]:
    predicate = None
    if view.predicate is not None:
        predicate = {
            "lex": view.predicate.lex,
            "vt": view.predicate.vt,
            "vs": view.predicate.vs,
            "ps": view.predicate.ps,
            "nu": view.predicate.nu,
            "gn": view.predicate.gn,
            "prs": view.predicate.prs,
            "prs_ps": view.predicate.prs_ps,
            "prs_nu": view.predicate.prs_nu,
            "prs_gn": view.predicate.prs_gn,
        }
    return {
        "atom": view.node,
        "clause": view.clause,
        "first_slot": view.first_slot,
        "last_slot": view.last_slot,
        "tab": view.tab,
        "pargr": view.pargr,
        "instruction": view.instruction,
        "sub1": view.sub1,
        "sub2": view.sub2,
        "typ": view.typ,
        "txt": view.txt,
        "text": view.text,
        "predicate": predicate,
        "explicit_subject": view.explicit_subject,
        "has_fronting": view.has_fronting,
        "has_vocative": view.has_vocative,
        "relative_marker": view.relative_marker,
        "quote_verb": view.quote_verb,
        "question_marked": view.question_marked,
        "coordinating_conjunction": view.coordinating_conjunction,
        "subordinating_conjunction": view.subordinating_conjunction,
        "opening_conjunction_lexemes": list(view.opening_conjunction_lexemes),
        "opening_preposition_lexemes": list(view.opening_preposition_lexemes),
        "phrases": [phrase_to_dict(phrase) for phrase in view.phrases],
        "opening_phrases": [phrase_to_dict(phrase) for phrase in view.opening_phrases],
        "preverbal_phrases": [phrase_to_dict(phrase) for phrase in view.preverbal_phrases],
        "postverbal_phrases": [phrase_to_dict(phrase) for phrase in view.postverbal_phrases],
    }


def candidate_to_site_dict(
    candidate: core.Candidate,
    ctx: core.BhsaContext,
    *,
    rank: int,
    gold_mother: int | None,
) -> dict[str, Any]:
    row = core.candidate_to_dict(candidate, ctx)
    row["rank"] = rank
    row["is_gold"] = candidate.mother == gold_mother
    row["daughter_section"] = section_to_dict(row["daughter_section"])
    row["mother_section"] = section_to_dict(row["mother_section"])
    return row


def _resource_mode(resource_spec: str | None, fit: bool) -> str:
    if fit:
        return "fit_from_gold"
    if resource_spec == ":official_seed":
        return "official_seed"
    if resource_spec:
        return "json_file"
    return "empty_tables"


def parse_books(values: Sequence[str] | None) -> list[str] | None:
    return core.parse_books(values)


def resolve_resources(
    api: Any,
    *,
    resource_spec: str | None,
    fit: bool,
    alpha: float,
    books: Sequence[str] | None,
    limit: int | None,
    pool_mode: str,
) -> core.ResourceTables:
    base_resources = core.load_resources(resource_spec)
    if not fit:
        return base_resources
    generator = core.build_generator(api, resources=base_resources, pool_mode=pool_mode)
    return core.fit_resources_from_gold(
        generator,
        books=books,
        limit=limit,
        alpha=alpha,
    )


def build_atom_detail(
    generator: core.MotherCandidateGenerator,
    atom: int,
    *,
    top_k: int,
) -> dict[str, Any]:
    ctx = generator.ctx
    view = generator.extractor.extract(atom)
    gold_mother = ctx.mother_of(atom)
    gold_mother_text = ctx.text_of(gold_mother) if gold_mother is not None else None
    predictions = generator.predict_for_atom(atom, top_k=top_k)
    pool = generator.pool_builder.build(atom)
    section = section_to_dict(ctx.section_of(atom))
    book = section.get("book") or "Unknown"
    book_slug = slugify_book(book)

    detail = {
        "atom": atom,
        "section": section,
        "book": book,
        "book_slug": book_slug,
        "text": ctx.text_of(atom),
        "gold_mother": gold_mother,
        "gold_mother_text": gold_mother_text,
        "gold_relation": ctx.rela_of_atom(atom),
        "pool_size": len(pool),
        "pool_atoms": list(pool),
        "prev_atom": ctx.prev_atom(atom),
        "next_atom": ctx.next_atom(atom),
        "view": view_to_dict(view),
        "predictions": [
            candidate_to_site_dict(candidate, ctx, rank=rank, gold_mother=gold_mother)
            for rank, candidate in enumerate(predictions, start=1)
        ],
    }
    if detail["predictions"]:
        top1 = detail["predictions"][0]
        detail["top_prediction"] = {
            "mother": top1["mother"],
            "score": top1["score"],
            "predicted_rela": top1["predicted_rela"],
        }
    else:
        detail["top_prediction"] = None
    return detail


def build_site_dataset(
    api: Any,
    *,
    app_name: str,
    resource_spec: str | None = ":official_seed",
    fit: bool = False,
    alpha: float = 0.5,
    top_k: int = 5,
    books: Sequence[str] | None = None,
    limit: int | None = None,
    pool_mode: str = "instruction",
    source_kind: str = "bhsa",
) -> dict[str, Any]:
    resolved_books = parse_books(books)
    resources = resolve_resources(
        api,
        resource_spec=resource_spec,
        fit=fit,
        alpha=alpha,
        books=resolved_books,
        limit=limit,
        pool_mode=pool_mode,
    )
    generator = core.build_generator(api, resources=resources, pool_mode=pool_mode)
    ctx = generator.ctx

    index_rows: list[dict[str, Any]] = []
    details: dict[str, dict[str, Any]] = {}
    books_summary: dict[str, dict[str, Any]] = {}
    for atom in ctx.iter_atoms(books=resolved_books, limit=limit):
        detail = build_atom_detail(generator, atom, top_k=top_k)
        details[str(atom)] = detail
        row = {
            "atom": atom,
            "daughter": atom,
            "book": detail["book"],
            "book_slug": detail["book_slug"],
            "section": detail["section"],
            "text": detail["text"],
            "gold_mother": detail["gold_mother"],
            "prediction_count": len(detail["predictions"]),
            "top_prediction": detail["top_prediction"],
        }
        index_rows.append(row)
        bucket = books_summary.setdefault(
            detail["book_slug"],
            {
                "book": detail["book"],
                "book_slug": detail["book_slug"],
                "atom_count": 0,
                "first_atom": atom,
                "last_atom": atom,
            },
        )
        bucket["atom_count"] += 1
        bucket["last_atom"] = atom

    index_rows.sort(key=lambda row: row["atom"])
    atom_numbers = [row["atom"] for row in index_rows]
    book_rows = sorted(books_summary.values(), key=lambda row: (row["book"], row["first_atom"]))
    meta = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "app_name": app_name,
        "source_kind": source_kind,
        "resource_mode": _resource_mode(resource_spec, fit),
        "resource_spec": resource_spec,
        "top_k": top_k,
        "pool_mode": pool_mode,
        "books": list(resolved_books) if resolved_books else None,
        "limit": limit,
        "atom_count": len(index_rows),
        "first_atom": atom_numbers[0] if atom_numbers else None,
        "last_atom": atom_numbers[-1] if atom_numbers else None,
        "books": book_rows,
        "resources_snapshot": resources.to_json_dict(),
    }
    return {
        "meta": meta,
        "index": index_rows,
        "details": details,
        "catalog": {
            "books": book_rows,
            "atoms": index_rows,
        },
    }


def write_site_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def write_data_bundle(dataset: Mapping[str, Any], *, output_dir: str | Path) -> Path:
    data_dir = Path(output_dir)
    atoms_dir = data_dir / "atoms"
    if atoms_dir.exists():
        shutil.rmtree(atoms_dir)
    atoms_dir.mkdir(parents=True, exist_ok=True)

    write_site_json(data_dir / "meta.json", dataset["meta"])
    write_site_json(data_dir / "index.json", {"atoms": dataset["index"]})
    write_site_json(data_dir / "catalog.json", dataset["catalog"])
    write_site_json(data_dir / "resources.json", dataset["meta"]["resources_snapshot"])

    for atom, detail in dataset["details"].items():
        write_site_json(atoms_dir / f"{atom}.json", detail)
    return data_dir


def copy_site_assets(site_dir: str | Path, output_dir: str | Path) -> None:
    src = Path(site_dir)
    dst = Path(output_dir)
    if not src.exists():
        raise FileNotFoundError(f"Site source directory not found: {src}")
    dst.mkdir(parents=True, exist_ok=True)
    shutil.copytree(src, dst, dirs_exist_ok=True)


def write_static_site(
    dataset: Mapping[str, Any],
    *,
    output_dir: str | Path,
    site_dir: str | Path | None = None,
) -> Path:
    out_dir = Path(output_dir)
    if site_dir is not None:
        copy_site_assets(site_dir, out_dir)
    else:
        out_dir.mkdir(parents=True, exist_ok=True)

    write_data_bundle(dataset, output_dir=out_dir / "data")
    return out_dir


def build_and_write_static_site(
    api: Any,
    *,
    output_dir: str | Path,
    site_dir: str | Path | None,
    app_name: str,
    resource_spec: str | None = ":official_seed",
    fit: bool = False,
    alpha: float = 0.5,
    top_k: int = 5,
    books: Sequence[str] | None = None,
    limit: int | None = None,
    pool_mode: str = "instruction",
    source_kind: str = "bhsa",
) -> dict[str, Any]:
    dataset = build_site_dataset(
        api,
        app_name=app_name,
        resource_spec=resource_spec,
        fit=fit,
        alpha=alpha,
        top_k=top_k,
        books=books,
        limit=limit,
        pool_mode=pool_mode,
        source_kind=source_kind,
    )
    write_static_site(dataset, output_dir=output_dir, site_dir=site_dir)
    return dataset


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build a static BHSA clause atom candidate site")
    parser.add_argument("output_dir", nargs="?", help="Directory where the static site build will be written")
    parser.add_argument("--outdir", help="Alias for output_dir")
    parser.add_argument("--site-dir", default="site", help="Directory containing static site assets")
    parser.add_argument("--app", default="ETCBC/bhsa", help="Text-Fabric app name")
    parser.add_argument(
        "--resources",
        default=":official_seed",
        help="JSON file with ResourceTables, or :official_seed for the built-in starter set",
    )
    parser.add_argument("--fit", action="store_true", help="Fit weights from gold mother edges before export")
    parser.add_argument("--alpha", type=float, default=0.5, help="Laplace smoothing alpha for fit mode")
    parser.add_argument("--books", nargs="*", help="Limit to one or more books")
    parser.add_argument("--limit", type=int, help="Maximum number of clause atoms to export")
    parser.add_argument("--top-k", type=int, default=5, help="Number of candidates to include per atom")
    parser.add_argument(
        "--pool-mode",
        default="instruction",
        choices=("instruction", "tab_only"),
        help="Candidate-pool pruning mode",
    )
    parser.add_argument("--weights-out", help="Optional path to save fitted or resolved resource tables JSON")
    parser.add_argument("--synthetic", action="store_true", help="Build from the bundled synthetic BHSA fixture")
    return parser


def main(argv: Sequence[str] | None = None) -> None:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    output_dir = args.outdir or args.output_dir
    if not output_dir:
        parser.error("output_dir is required")

    if args.synthetic:
        from synthetic_bhsa_support import build_synthetic_api

        api = build_synthetic_api()
        app_name = "synthetic-bhsa"
        source_kind = "synthetic"
    else:
        api = core.load_bhsa(args.app)
        app_name = args.app
        source_kind = "bhsa"

    dataset = build_and_write_static_site(
        api,
        output_dir=output_dir,
        site_dir=args.site_dir,
        app_name=app_name,
        resource_spec=args.resources,
        fit=args.fit,
        alpha=args.alpha,
        top_k=args.top_k,
        books=args.books,
        limit=args.limit,
        pool_mode=args.pool_mode,
        source_kind=source_kind,
    )
    if args.weights_out:
        path = Path(args.weights_out)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(dataset["meta"]["resources_snapshot"], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    print(
        json.dumps(
            {
                "output_dir": str(Path(output_dir).resolve()),
                "data_dir": str((Path(output_dir).resolve() / "data")),
                "atom_count": dataset["meta"]["atom_count"],
                "source_kind": dataset["meta"]["source_kind"],
                "resource_mode": dataset["meta"]["resource_mode"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
