
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from functools import lru_cache
from math import exp, log
from pathlib import Path
from statistics import NormalDist
from typing import Any, Iterable, Iterator, Mapping, Protocol, Sequence


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------


def load_bhsa(app_name: str = "ETCBC/bhsa", silent: str = "deep") -> Any:
    """Return a Text-Fabric API object for BHSA."""
    from tf.app import use

    A = use(app_name, silent=silent)
    return A.api


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PredicateInfo:
    lex: str | None
    vt: str | None
    vs: str | None
    ps: str | None
    nu: str | None
    gn: str | None
    prs: str | None
    prs_ps: str | None
    prs_nu: str | None
    prs_gn: str | None

    @property
    def png(self) -> tuple[str | None, str | None, str | None]:
        return (self.ps, self.nu, self.gn)

    @property
    def suffix_png(self) -> tuple[str | None, str | None, str | None]:
        return (self.prs_ps, self.prs_nu, self.prs_gn)


@dataclass(frozen=True)
class PhraseInfo:
    node: int
    first_slot: int
    last_slot: int
    function: str | None
    typ: str | None
    text: str
    lexemes: tuple[str, ...]


@dataclass(frozen=True)
class ClauseAtomView:
    node: int
    clause: int | None
    first_slot: int
    last_slot: int
    tab: int
    pargr: str | None
    instruction: str
    sub1: str
    sub2: str
    typ: str | None
    txt: str | None
    text: str
    phrases: tuple[PhraseInfo, ...]
    opening_phrases: tuple[PhraseInfo, ...]
    preverbal_phrases: tuple[PhraseInfo, ...]
    predicate_phrase: PhraseInfo | None
    postverbal_phrases: tuple[PhraseInfo, ...]
    predicate: PredicateInfo | None
    explicit_subject: bool
    has_fronting: bool
    has_vocative: bool
    relative_marker: bool
    opening_conjunction_lexemes: tuple[str, ...]
    opening_preposition_lexemes: tuple[str, ...]
    quote_verb: bool
    question_marked: bool
    coordinating_conjunction: bool
    subordinating_conjunction: bool

    def phrase_functions(self) -> tuple[str, ...]:
        return tuple(p.function or "" for p in self.phrases)

    def opening_signature(self, ignore_coord: bool = False) -> tuple[tuple[str | None, str | None], ...]:
        rows: list[tuple[str | None, str | None]] = []
        for p in self.opening_phrases:
            if ignore_coord and p.function == "Conj":
                continue
            rows.append((p.function, p.typ))
        return tuple(rows)

    def lexical_signature(self) -> tuple[str, ...]:
        lexs: list[str] = []
        for p in self.phrases:
            lexs.extend(p.lexemes)
        return tuple(lexs)

    def first_phrase(self) -> PhraseInfo | None:
        return self.phrases[0] if self.phrases else None


@dataclass(frozen=True)
class Evidence:
    label: str
    weight: float = 0.0
    mean_distance: float | None = None
    par: float = 0.0
    quo: float = 0.0
    freq: int = 0
    payload: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Candidate:
    daughter: int
    mother: int
    score: float
    evidences: tuple[Evidence, ...]
    predicted_sub1: str = "."
    predicted_sub2: str = "."
    predicted_rela: str | None = None
    predicted_typ: str | None = None
    parallel: bool = False
    quotation: bool = False


@dataclass(frozen=True)
class ArgWeight:
    label: str
    weight: float
    mean_distance: float | None = None
    par: float = 0.0
    quo: float = 0.0
    freq: int = 0


@dataclass
class ResourceTables:
    """External tables replacing ETCBC library data files."""

    arg_weights: Mapping[str, ArgWeight] = field(default_factory=dict)
    quote_verbs: frozenset[str] = field(default_factory=frozenset)
    object_clause_governors: frozenset[str] = field(default_factory=frozenset)
    subject_clause_governors: frozenset[str] = field(default_factory=frozenset)
    predicative_clause_governors: frozenset[str] = field(default_factory=frozenset)
    conjunction_classes: Mapping[str, str] = field(default_factory=dict)
    preposition_classes: Mapping[str, str] = field(default_factory=dict)
    infinitive_preposition_classes: Mapping[str, int] = field(default_factory=dict)
    relative_lexemes: frozenset[str] = field(default_factory=frozenset)

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "arg_weights": {k: asdict(v) for (k, v) in self.arg_weights.items()},
            "quote_verbs": sorted(self.quote_verbs),
            "object_clause_governors": sorted(self.object_clause_governors),
            "subject_clause_governors": sorted(self.subject_clause_governors),
            "predicative_clause_governors": sorted(self.predicative_clause_governors),
            "conjunction_classes": dict(self.conjunction_classes),
            "preposition_classes": dict(self.preposition_classes),
            "infinitive_preposition_classes": dict(self.infinitive_preposition_classes),
            "relative_lexemes": sorted(self.relative_lexemes),
        }

    def save_json(self, path: str | Path) -> None:
        Path(path).write_text(json.dumps(self.to_json_dict(), ensure_ascii=False, indent=2), encoding="utf-8")

    @classmethod
    def from_json_dict(cls, data: Mapping[str, Any]) -> "ResourceTables":
        return cls(
            arg_weights={
                k: (v if isinstance(v, ArgWeight) else ArgWeight(**v))
                for (k, v) in dict(data.get("arg_weights", {})).items()
            },
            quote_verbs=frozenset(data.get("quote_verbs", [])),
            object_clause_governors=frozenset(data.get("object_clause_governors", [])),
            subject_clause_governors=frozenset(data.get("subject_clause_governors", [])),
            predicative_clause_governors=frozenset(data.get("predicative_clause_governors", [])),
            conjunction_classes=dict(data.get("conjunction_classes", {})),
            preposition_classes=dict(data.get("preposition_classes", {})),
            infinitive_preposition_classes={str(k): int(v) for (k, v) in dict(data.get("infinitive_preposition_classes", {})).items()},
            relative_lexemes=frozenset(data.get("relative_lexemes", [])),
        )

    @classmethod
    def load_json(cls, path: str | Path) -> "ResourceTables":
        return cls.from_json_dict(json.loads(Path(path).read_text(encoding="utf-8")))


# ---------------------------------------------------------------------------
# TF context wrapper
# ---------------------------------------------------------------------------


class BhsaContext:
    def __init__(self, api: Any, resources: ResourceTables | None = None) -> None:
        self.api = api
        self.F = api.F
        self.E = api.E
        self.L = api.L
        self.T = api.T
        self.resources = resources or ResourceTables()
        self._clause_atoms: tuple[int, ...] = tuple(self.F.otype.s("clause_atom"))
        self._atom_index = {n: i for (i, n) in enumerate(self._clause_atoms)}

    @property
    def clause_atoms(self) -> tuple[int, ...]:
        return self._clause_atoms

    def has_feature(self, name: str) -> bool:
        return hasattr(self.F, name)

    def fval(self, name: str, node: int) -> Any:
        feat = getattr(self.F, name, None)
        return None if feat is None else feat.v(node)

    def atom_pos(self, clause_atom: int) -> int:
        return self._atom_index[clause_atom]

    def atom_distance(self, a: int, b: int) -> int:
        return self.atom_pos(a) - self.atom_pos(b)

    def first_slot(self, node: int) -> int:
        slots = tuple(self.E.oslots.s(node))
        return min(slots)

    def last_slot(self, node: int) -> int:
        slots = tuple(self.E.oslots.s(node))
        return max(slots)

    def words_of(self, node: int) -> tuple[int, ...]:
        return tuple(self.E.oslots.s(node))

    def text_of(self, node: int) -> str:
        return self.T.text(node)

    def section_of(self, node: int) -> Any:
        return self.T.sectionFromNode(node)

    def book_of(self, node: int) -> str:
        section = self.section_of(node)
        if isinstance(section, (list, tuple)) and section:
            return str(section[0])
        return str(section)

    def clause_of_atom(self, clause_atom: int) -> int | None:
        up = tuple(self.L.u(clause_atom, otype="clause"))
        return up[0] if up else None

    def mother_of(self, node: int) -> int | None:
        moms = tuple(self.E.mother.f(node) or ())
        return moms[0] if moms else None

    def rela_of_atom(self, node: int) -> str | None:
        rela = self.fval("rela", node)
        if rela:
            return rela
        clause = self.clause_of_atom(node)
        return self.fval("rela", clause) if clause else None

    def code_of_atom(self, node: int) -> int | None:
        raw = self.fval("code", node)
        if raw is None:
            clause = self.clause_of_atom(node)
            raw = self.fval("code", clause) if clause else None
        if raw is None:
            return None
        try:
            return int(raw)
        except Exception:
            return None

    def prev_atom(self, node: int) -> int | None:
        i = self._atom_index[node]
        return self._clause_atoms[i - 1] if i > 0 else None

    def next_atom(self, node: int) -> int | None:
        i = self._atom_index[node]
        return self._clause_atoms[i + 1] if i + 1 < len(self._clause_atoms) else None

    def atoms_between(self, left: int, right: int) -> tuple[int, ...]:
        i = self._atom_index[left]
        j = self._atom_index[right]
        return self._clause_atoms[min(i, j) : max(i, j) + 1]

    def iter_atoms(self, books: Sequence[str] | None = None, limit: int | None = None) -> Iterator[int]:
        seen = 0
        wanted = set(books or ())
        for node in self._clause_atoms:
            if wanted and self.book_of(node) not in wanted:
                continue
            yield node
            seen += 1
            if limit is not None and seen >= limit:
                break


# ---------------------------------------------------------------------------
# Clause-atom view extraction
# ---------------------------------------------------------------------------


PREDICATE_FUNCTIONS = {"Pred", "PreS", "PreO", "PtcO", "PrcS", "PreC"}
SUBJECT_FUNCTIONS = {"Subj"}
QUESTION_FUNCTIONS = {"Ques"}
VOCATIVE_FUNCTIONS = {"Voct"}
FRONTING_FUNCTIONS = {"Frnt", "Rela"}
COORD_CONJ_LEXEMES = {"W", ">W"}


class ClauseAtomExtractor:
    def __init__(self, ctx: BhsaContext) -> None:
        self.ctx = ctx

    @lru_cache(maxsize=32768)
    def extract(self, clause_atom: int) -> ClauseAtomView:
        ctx = self.ctx
        first_slot = ctx.first_slot(clause_atom)
        last_slot = ctx.last_slot(clause_atom)
        clause = ctx.clause_of_atom(clause_atom)
        txt = ctx.fval("txt", clause) if clause else None
        instruction = (ctx.fval("instruction", clause_atom) or "..")[:2].ljust(2, ".")
        sub1, sub2 = instruction[0], instruction[1]

        phrase_nodes = self._phrase_nodes_of_atom(clause_atom)
        phrases = tuple(self._phrase_info(p) for p in phrase_nodes)
        predicate_idx = self._predicate_index(phrases)

        if predicate_idx is None:
            opening = phrases
            preverbal = phrases
            predicate_phrase = None
            postverbal = ()
        else:
            opening = tuple(phrases[:predicate_idx])
            preverbal = tuple(phrases[:predicate_idx])
            predicate_phrase = phrases[predicate_idx]
            postverbal = tuple(phrases[predicate_idx + 1 :])

        predicate = self._predicate_info(predicate_phrase)
        opening_lexs = self._opening_conjunction_lexemes(opening)
        opening_preps = self._opening_preposition_lexemes(opening)
        explicit_subject = any((p.function in SUBJECT_FUNCTIONS) for p in phrases)
        has_fronting = any((p.function in FRONTING_FUNCTIONS) for p in phrases)
        has_vocative = any((p.function in VOCATIVE_FUNCTIONS) for p in phrases)
        relative_marker = any(
            (p.function == "Rela") or bool(set(p.lexemes) & set(ctx.resources.relative_lexemes)) for p in phrases
        )
        quote_verb = bool(predicate and predicate.lex in ctx.resources.quote_verbs)
        question_marked = any((p.function in QUESTION_FUNCTIONS) for p in phrases)
        coordinating_conjunction = any(
            (lex in COORD_CONJ_LEXEMES) or (ctx.resources.conjunction_classes.get(lex) == "coord")
            for lex in opening_lexs
        )
        subordinating_conjunction = any(
            (p.function in {"Conj", "Rela"}) for p in opening
        ) and not coordinating_conjunction

        return ClauseAtomView(
            node=clause_atom,
            clause=clause,
            first_slot=first_slot,
            last_slot=last_slot,
            tab=int(ctx.fval("tab", clause_atom) or 0),
            pargr=ctx.fval("pargr", clause_atom),
            instruction=instruction,
            sub1=sub1,
            sub2=sub2,
            typ=ctx.fval("typ", clause_atom),
            txt=txt,
            text=ctx.text_of(clause_atom),
            phrases=phrases,
            opening_phrases=tuple(opening),
            preverbal_phrases=tuple(preverbal),
            predicate_phrase=predicate_phrase,
            postverbal_phrases=tuple(postverbal),
            predicate=predicate,
            explicit_subject=explicit_subject,
            has_fronting=has_fronting,
            has_vocative=has_vocative,
            relative_marker=relative_marker,
            opening_conjunction_lexemes=opening_lexs,
            opening_preposition_lexemes=opening_preps,
            quote_verb=quote_verb,
            question_marked=question_marked,
            coordinating_conjunction=coordinating_conjunction,
            subordinating_conjunction=subordinating_conjunction,
        )

    def _phrase_nodes_of_atom(self, clause_atom: int) -> tuple[int, ...]:
        ctx = self.ctx
        first_slot = ctx.first_slot(clause_atom)
        last_slot = ctx.last_slot(clause_atom)

        candidates = set(ctx.L.i(clause_atom, otype="phrase")) | set(ctx.L.d(clause_atom, otype="phrase"))
        selected: list[int] = []
        for p in candidates:
            pf = ctx.first_slot(p)
            pl = ctx.last_slot(p)
            if pf >= first_slot and pl <= last_slot:
                selected.append(p)
        selected.sort(key=ctx.first_slot)
        return tuple(selected)

    def _phrase_info(self, phrase: int) -> PhraseInfo:
        ctx = self.ctx
        words = ctx.words_of(phrase)
        lexemes = tuple(ctx.fval("lex", w) for w in words if ctx.fval("lex", w))
        return PhraseInfo(
            node=phrase,
            first_slot=ctx.first_slot(phrase),
            last_slot=ctx.last_slot(phrase),
            function=ctx.fval("function", phrase),
            typ=ctx.fval("typ", phrase),
            text=ctx.text_of(phrase),
            lexemes=lexemes,
        )

    def _predicate_index(self, phrases: Sequence[PhraseInfo]) -> int | None:
        for i, p in enumerate(phrases):
            if p.function in PREDICATE_FUNCTIONS:
                return i
        return None

    def _predicate_info(self, predicate_phrase: PhraseInfo | None) -> PredicateInfo | None:
        if predicate_phrase is None:
            return None
        ctx = self.ctx
        for w in ctx.words_of(predicate_phrase.node):
            if ctx.fval("vt", w) not in (None, "NA") or ctx.fval("vs", w) not in (None, "NA"):
                return PredicateInfo(
                    lex=ctx.fval("lex", w),
                    vt=ctx.fval("vt", w),
                    vs=ctx.fval("vs", w),
                    ps=ctx.fval("ps", w),
                    nu=ctx.fval("nu", w),
                    gn=ctx.fval("gn", w),
                    prs=ctx.fval("prs", w),
                    prs_ps=ctx.fval("prs_ps", w),
                    prs_nu=ctx.fval("prs_nu", w),
                    prs_gn=ctx.fval("prs_gn", w),
                )
        words = ctx.words_of(predicate_phrase.node)
        if not words:
            return None
        w = words[0]
        return PredicateInfo(
            lex=ctx.fval("lex", w),
            vt=ctx.fval("vt", w),
            vs=ctx.fval("vs", w),
            ps=ctx.fval("ps", w),
            nu=ctx.fval("nu", w),
            gn=ctx.fval("gn", w),
            prs=ctx.fval("prs", w),
            prs_ps=ctx.fval("prs_ps", w),
            prs_nu=ctx.fval("prs_nu", w),
            prs_gn=ctx.fval("prs_gn", w),
        )

    def _opening_conjunction_lexemes(self, opening: Sequence[PhraseInfo]) -> tuple[str, ...]:
        lexs: list[str] = []
        for p in opening:
            if p.function in {"Conj", "Rela"} or p.typ == "CP":
                lexs.extend(p.lexemes)
        return tuple(lexs)

    def _opening_preposition_lexemes(self, opening: Sequence[PhraseInfo]) -> tuple[str, ...]:
        lexs: list[str] = []
        for p in opening:
            if p.typ == "PP" and p.lexemes:
                lexs.append(p.lexemes[0])
        return tuple(lexs)


# ---------------------------------------------------------------------------
# Candidate pool (ETCBC-compatible reconstruction)
# ---------------------------------------------------------------------------


class CandidatePoolBuilder:
    def __init__(self, ctx: BhsaContext, extractor: ClauseAtomExtractor, mode: str = "instruction") -> None:
        self.ctx = ctx
        self.extractor = extractor
        self.mode = mode

    def build(self, daughter: int) -> tuple[int, ...]:
        atoms = self.ctx.clause_atoms
        pos = self.ctx.atom_pos(daughter)
        pool: list[int] = []

        # left scan
        t = 10_000
        for i in range(pos - 1, -1, -1):
            m = atoms[i]
            m_view = self.extractor.extract(m)
            if m_view.tab <= t and (self.mode != "instruction" or m_view.sub2 != "e"):
                pool.append(m)
                t = m_view.tab - 1
                if t < 0:
                    break
                if self.mode == "instruction" and m_view.sub2 == "\\":
                    break

        # right scan
        t = 10_000
        for i in range(pos + 1, len(atoms)):
            m = atoms[i]
            m_view = self.extractor.extract(m)
            if m_view.tab <= t and (self.mode != "instruction" or m_view.sub2 != "e"):
                pool.append(m)
                t = m_view.tab - 1
                if t < 0:
                    break
                if self.mode == "instruction" and m_view.sub2 != "\\":
                    break

        return tuple(pool)


# ---------------------------------------------------------------------------
# Feature utilities
# ---------------------------------------------------------------------------


RIGHTWARD_LICENSE_LABELS = {"DOWN", "XPOS", "ATTR", "SUBJ", "PREC", "OBJC", "ADJU", "RESU", "REVO", "RGRC", "COOR"}
LICENSE_PREFIXES = ("DOWN", "XPOS", "ATTR", "SUBJ", "PREC", "OBJC", "ADJU", "RESU", "REVO", "RGRC", "COOR")


def has_label_prefix(labels: Iterable[str], *prefixes: str) -> bool:
    return any(any(label.startswith(prefix) for prefix in prefixes) for label in labels)


def first_class(lexemes: Sequence[str], mapping: Mapping[str, str]) -> tuple[str | None, str | None]:
    for lex in lexemes:
        cls = mapping.get(lex)
        if cls:
            return (lex, cls)
    return (None, None)


def clean_png(png: tuple[str | None, str | None, str | None]) -> tuple[str | None, str | None, str | None] | None:
    if all(x in (None, "NA", "unknown") for x in png):
        return None
    return png


def lexical_overlap(left: ClauseAtomView, right: ClauseAtomView) -> set[str]:
    return set(left.lexical_signature()) & set(right.lexical_signature())


def has_np_like_phrase(view: ClauseAtomView) -> bool:
    return any(p.typ in {"NP", "PrNP", "PP"} or p.function in {"Subj", "Objc", "PrAd"} for p in view.phrases)


def is_rightward(daughter: ClauseAtomView, mother: ClauseAtomView, ctx: BhsaContext) -> bool:
    return ctx.atom_pos(mother.node) > ctx.atom_pos(daughter.node)


class ArgumentFeature(Protocol):
    def extract(self, daughter: ClauseAtomView, mother: ClauseAtomView, ctx: BhsaContext) -> Sequence[Evidence]:
        ...


class BaseFeature:
    label: str = ""

    def ev(
        self,
        ctx: BhsaContext,
        label: str | None = None,
        *,
        default_weight: float = 0.0,
        default_par: float = 0.0,
        default_quo: float = 0.0,
        payload: Mapping[str, Any] | None = None,
    ) -> Evidence:
        lbl = label or self.label
        aw = ctx.resources.arg_weights.get(lbl)
        if aw is None:
            return Evidence(
                label=lbl,
                weight=default_weight,
                mean_distance=None,
                par=default_par,
                quo=default_quo,
                freq=0,
                payload=payload or {},
            )
        return Evidence(
            label=lbl,
            weight=aw.weight,
            mean_distance=aw.mean_distance,
            par=max(aw.par, default_par),
            quo=max(aw.quo, default_quo),
            freq=aw.freq,
            payload=payload or {},
        )


class VSeqFeature(BaseFeature):
    label = "VBT"

    def extract(self, daughter: ClauseAtomView, mother: ClauseAtomView, ctx: BhsaContext) -> Sequence[Evidence]:
        dvt = daughter.predicate.vt if daughter.predicate else None
        mvt = mother.predicate.vt if mother.predicate else None
        if dvt and mvt and dvt == mvt:
            return [self.ev(ctx, "VBT")]
        if daughter.typ and mother.typ and daughter.typ == mother.typ:
            return [self.ev(ctx, "TYP_MATCH")]
        return []


class VLexFeature(BaseFeature):
    label = "VLEX"

    def extract(self, daughter: ClauseAtomView, mother: ClauseAtomView, ctx: BhsaContext) -> Sequence[Evidence]:
        dlex = daughter.predicate.lex if daughter.predicate else None
        mlex = mother.predicate.lex if mother.predicate else None
        if dlex and mlex and dlex == mlex:
            return [self.ev(ctx)]
        return []


class ParallelOpeningFeature(BaseFeature):
    def extract(self, daughter: ClauseAtomView, mother: ClauseAtomView, ctx: BhsaContext) -> Sequence[Evidence]:
        if daughter.explicit_subject != mother.explicit_subject:
            return []

        if daughter.predicate is None or mother.predicate is None:
            if daughter.typ == mother.typ:
                return [self.ev(ctx, "PAR_TYP", default_par=1.0)]
            return []

        if daughter.opening_signature(False) == mother.opening_signature(False):
            return [self.ev(ctx, "PAR_OPEN", default_par=1.0)]
        if daughter.opening_signature(True) == mother.opening_signature(True):
            return [self.ev(ctx, "PAR_OPEN_NOCOOR", default_par=1.0)]
        return []


class LexicalParallelFeature(BaseFeature):
    label = "LEXPAR"

    def extract(self, daughter: ClauseAtomView, mother: ClauseAtomView, ctx: BhsaContext) -> Sequence[Evidence]:
        overlap = lexical_overlap(daughter, mother)
        if len(overlap) >= 2:
            return [self.ev(ctx, payload={"overlap": sorted(overlap)[:6]})]
        return []


class AsyndeticQuoteFeature(BaseFeature):
    label = "ASYNQ"

    def extract(self, daughter: ClauseAtomView, mother: ClauseAtomView, ctx: BhsaContext) -> Sequence[Evidence]:
        if mother.quote_verb and not daughter.subordinating_conjunction and not daughter.coordinating_conjunction:
            return [self.ev(ctx, default_quo=1.0)]
        return []


class PngAgreementFeature(BaseFeature):
    def extract(self, daughter: ClauseAtomView, mother: ClauseAtomView, ctx: BhsaContext) -> Sequence[Evidence]:
        out: list[Evidence] = []
        dp = daughter.predicate
        mp = mother.predicate
        if not dp or not mp:
            return out

        if clean_png(dp.png) == clean_png(mp.png) and clean_png(dp.png) is not None:
            out.append(self.ev(ctx, "PNG<<PNG"))
        if clean_png(dp.suffix_png) == clean_png(mp.png) and clean_png(dp.suffix_png) is not None:
            out.append(self.ev(ctx, "SFX<<PNG"))
        if clean_png(dp.png) == clean_png(mp.suffix_png) and clean_png(dp.png) is not None:
            out.append(self.ev(ctx, "PNG<<SFX"))
        return out


class CoordinationFeature(BaseFeature):
    label = "COOR"

    def extract(self, daughter: ClauseAtomView, mother: ClauseAtomView, ctx: BhsaContext) -> Sequence[Evidence]:
        if is_rightward(daughter, mother, ctx):
            return []
        dist = abs(ctx.atom_distance(daughter.node, mother.node))
        if dist > 3:
            return []
        if daughter.coordinating_conjunction:
            payload = {"coord": daughter.opening_conjunction_lexemes[:2]}
            return [self.ev(ctx, default_par=1.0, payload=payload)]
        if daughter.opening_signature(True) == mother.opening_signature(True) and daughter.explicit_subject == mother.explicit_subject:
            return [self.ev(ctx, "COOR_PAR", default_par=1.0)]
        return []


class ObjectClauseFeature(BaseFeature):
    label = "OBJC"

    def extract(self, daughter: ClauseAtomView, mother: ClauseAtomView, ctx: BhsaContext) -> Sequence[Evidence]:
        mp = mother.predicate
        if not mp or mp.lex not in ctx.resources.object_clause_governors:
            return []
        if daughter.coordinating_conjunction:
            return []
        if daughter.subordinating_conjunction or daughter.question_marked:
            return [self.ev(ctx)]
        if abs(ctx.atom_distance(daughter.node, mother.node)) == 1 and not is_rightward(daughter, mother, ctx):
            return [self.ev(ctx, "OBJC_ADJ")]
        return []


class PredicativeClauseFeature(BaseFeature):
    label = "PREC"

    def extract(self, daughter: ClauseAtomView, mother: ClauseAtomView, ctx: BhsaContext) -> Sequence[Evidence]:
        if daughter.subordinating_conjunction or daughter.coordinating_conjunction:
            return []
        mlex = mother.predicate.lex if mother.predicate else None
        mfuncs = set(mother.phrase_functions())
        if mlex and mlex in ctx.resources.predicative_clause_governors:
            return [self.ev(ctx)]
        if "Subj" in mfuncs and not (mfuncs & PREDICATE_FUNCTIONS):
            return [self.ev(ctx, "PREC_SUBJ")]
        return []


class OpeningConjunctionClassFeature(BaseFeature):
    def extract(self, daughter: ClauseAtomView, mother: ClauseAtomView, ctx: BhsaContext) -> Sequence[Evidence]:
        if daughter.coordinating_conjunction:
            return []
        lex, cls = first_class(daughter.opening_conjunction_lexemes, ctx.resources.conjunction_classes)
        if cls == "conditional":
            return [self.ev(ctx, "ADJU_COND", payload={"conj": lex, "class": cls})]
        if cls == "final":
            return [self.ev(ctx, "ADJU_FINAL", payload={"conj": lex, "class": cls})]
        if cls == "causal":
            return [self.ev(ctx, "ADJU_CAUSAL", payload={"conj": lex, "class": cls})]
        return []


class OpeningPrepositionClassFeature(BaseFeature):
    def extract(self, daughter: ClauseAtomView, mother: ClauseAtomView, ctx: BhsaContext) -> Sequence[Evidence]:
        if daughter.coordinating_conjunction:
            return []
        lex, cls = first_class(daughter.opening_preposition_lexemes, ctx.resources.preposition_classes)
        if cls == "temporal_700":
            return [self.ev(ctx, "ADJU_TEMP700", payload={"prep": lex, "class": cls})]
        if cls == "temporal_800":
            return [self.ev(ctx, "ADJU_TEMP800", payload={"prep": lex, "class": cls})]
        if cls == "causal_900":
            return [self.ev(ctx, "ADJU_CAUS900", payload={"prep": lex, "class": cls})]
        return []


class AttributeClauseFeature(BaseFeature):
    label = "ATTR"

    def extract(self, daughter: ClauseAtomView, mother: ClauseAtomView, ctx: BhsaContext) -> Sequence[Evidence]:
        if daughter.coordinating_conjunction:
            return []
        if daughter.relative_marker and has_np_like_phrase(mother):
            return [self.ev(ctx)]
        if daughter.first_phrase() and daughter.first_phrase().function == "Rela" and has_np_like_phrase(mother):
            return [self.ev(ctx, "ATTR_RELA")]
        return []


class SubjectClauseFeature(BaseFeature):
    label = "SUBJ"

    def extract(self, daughter: ClauseAtomView, mother: ClauseAtomView, ctx: BhsaContext) -> Sequence[Evidence]:
        mp = mother.predicate
        if daughter.coordinating_conjunction:
            return []
        if mp and mp.lex in ctx.resources.subject_clause_governors:
            return [self.ev(ctx)]
        if mother.typ in {"NmCl", "AjCl"} and not mother.explicit_subject and daughter.subordinating_conjunction:
            return [self.ev(ctx, "SUBJ_NM")]
        return []


class ResumptiveClauseFeature(BaseFeature):
    label = "RESU"

    def extract(self, daughter: ClauseAtomView, mother: ClauseAtomView, ctx: BhsaContext) -> Sequence[Evidence]:
        if is_rightward(daughter, mother, ctx):
            return []
        overlap = lexical_overlap(daughter, mother)
        fp = daughter.first_phrase()
        if daughter.has_fronting and fp and overlap & set(fp.lexemes):
            return [self.ev(ctx, payload={"fronted": fp.text})]
        return []


class ReferralVocativeFeature(BaseFeature):
    label = "REVO"

    def extract(self, daughter: ClauseAtomView, mother: ClauseAtomView, ctx: BhsaContext) -> Sequence[Evidence]:
        dist = abs(ctx.atom_distance(daughter.node, mother.node))
        if dist > 2:
            return []
        if mother.has_vocative and not daughter.has_vocative:
            return [self.ev(ctx)]
        if daughter.has_vocative and mother.explicit_subject:
            return [self.ev(ctx, "REVO_DAUGHTER")]
        return []


class RegensRectumFeature(BaseFeature):
    label = "RGRC"

    def extract(self, daughter: ClauseAtomView, mother: ClauseAtomView, ctx: BhsaContext) -> Sequence[Evidence]:
        if daughter.coordinating_conjunction or daughter.relative_marker:
            return []
        if mother.predicate is None and has_np_like_phrase(mother) and daughter.subordinating_conjunction:
            return [self.ev(ctx)]
        if mother.first_phrase() and mother.first_phrase().typ == "PP" and daughter.predicate is None:
            return [self.ev(ctx, "RGRC_PP")]
        return []


class DownwardFeature(BaseFeature):
    label = "DOWN"

    def extract(self, daughter: ClauseAtomView, mother: ClauseAtomView, ctx: BhsaContext) -> Sequence[Evidence]:
        if not is_rightward(daughter, mother, ctx):
            return []
        dist = abs(ctx.atom_distance(daughter.node, mother.node))
        if dist > 3:
            return []
        if daughter.pargr and mother.pargr and daughter.pargr != mother.pargr:
            return []
        if daughter.has_fronting or daughter.subordinating_conjunction or daughter.relative_marker:
            return [self.ev(ctx)]
        if dist == 1 and not daughter.coordinating_conjunction:
            return [self.ev(ctx, "DOWN_ADJ")]
        return []


class ExtraposedConstituentFeature(BaseFeature):
    label = "XPOS"

    def extract(self, daughter: ClauseAtomView, mother: ClauseAtomView, ctx: BhsaContext) -> Sequence[Evidence]:
        if not is_rightward(daughter, mother, ctx):
            return []
        if daughter.coordinating_conjunction:
            return []
        if len(daughter.preverbal_phrases) != 1 or daughter.predicate is None:
            return []
        stranded = daughter.preverbal_phrases[0]
        if stranded.function in {"Conj", "Rela"}:
            return []
        overlap = set(stranded.lexemes) & set(mother.lexical_signature())
        if overlap:
            return [self.ev(ctx, payload={"overlap": sorted(overlap)})]
        if abs(ctx.atom_distance(daughter.node, mother.node)) == 1:
            return [self.ev(ctx, "XPOS_WEAK")]
        return []


class AdjunctClauseFeature(BaseFeature):
    label = "ADJU"

    def extract(self, daughter: ClauseAtomView, mother: ClauseAtomView, ctx: BhsaContext) -> Sequence[Evidence]:
        if daughter.coordinating_conjunction:
            return []
        if daughter.opening_preposition_lexemes:
            return [self.ev(ctx, payload={"prep": daughter.opening_preposition_lexemes[:2]})]
        if daughter.subordinating_conjunction and not daughter.relative_marker:
            return [self.ev(ctx, "ADJU_CONJ")]
        return []


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------


class EtcBcStyleScorer:
    def __init__(self) -> None:
        self._phi = NormalDist().cdf

    def score(
        self,
        daughter: ClauseAtomView,
        mother: ClauseAtomView,
        evidences: Sequence[Evidence],
        ctx: BhsaContext,
    ) -> tuple[float, bool, bool]:
        if not evidences:
            return (0.0, False, False)

        observed_distance = abs(ctx.atom_distance(daughter.node, mother.node))
        value_raw = sum(ev.weight for ev in evidences)
        value_score = self._phi(value_raw)

        d_terms = [
            self._logprob(ev.mean_distance, observed_distance)
            for ev in evidences
            if ev.mean_distance is not None and ev.mean_distance >= 1
        ]
        distance_score = exp((85 / 834) * sum(d_terms) / len(d_terms)) if d_terms else 1.0

        if is_rightward(daughter, mother, ctx) and not has_label_prefix((ev.label for ev in evidences), *LICENSE_PREFIXES):
            return (0.0, False, False)

        final_score = value_score * distance_score
        parallel = any(ev.par > 0 for ev in evidences)
        quotation = any(ev.quo > 0 for ev in evidences)
        return (final_score, parallel, quotation)

    @staticmethod
    def _logprob(mu: float | None, observed_distance: int) -> float:
        if mu is None:
            return 0.0
        if mu == 1:
            return 0.0 if observed_distance == 1 else -100.0
        if mu <= 1:
            return 0.0
        return (1 - observed_distance) * log(mu / (mu - 1)) - log(mu)


# ---------------------------------------------------------------------------
# Generation facade
# ---------------------------------------------------------------------------


def infer_rela(evidences: Sequence[Evidence], parallel: bool, quotation: bool) -> str | None:
    labels = {ev.label for ev in evidences}
    if "COOR" in labels or "COOR_PAR" in labels or (parallel and not labels & {"OBJC", "ATTR", "SUBJ", "PREC"}):
        return "Coor"
    for lbl, rela in (
        ("ATTR", "Attr"),
        ("ATTR_RELA", "Attr"),
        ("OBJC", "Objc"),
        ("OBJC_ADJ", "Objc"),
        ("SUBJ", "Subj"),
        ("SUBJ_NM", "Subj"),
        ("PREC", "PreC"),
        ("PREC_SUBJ", "PreC"),
        ("ADJU", "Adju"),
        ("ADJU_CONJ", "Adju"),
        ("RESU", "Resu"),
        ("REVO", "ReVo"),
        ("REVO_DAUGHTER", "ReVo"),
        ("RGRC", "RgRc"),
        ("RGRC_PP", "RgRc"),
    ):
        if lbl in labels:
            return rela
    if quotation:
        return None
    return None


def infer_sub2(evidences: Sequence[Evidence], quotation: bool) -> str:
    labels = {ev.label for ev in evidences}
    if quotation:
        return "q"
    if "DOWN" in labels or "DOWN_ADJ" in labels or "XPOS" in labels or "XPOS_WEAK" in labels:
        return "\\"
    return "."


class MotherCandidateGenerator:
    def __init__(
        self,
        ctx: BhsaContext,
        extractor: ClauseAtomExtractor,
        pool_builder: CandidatePoolBuilder,
        features: Sequence[ArgumentFeature],
        scorer: EtcBcStyleScorer,
    ) -> None:
        self.ctx = ctx
        self.extractor = extractor
        self.pool_builder = pool_builder
        self.features = tuple(features)
        self.scorer = scorer

    def clone_with_features(self, features: Sequence[ArgumentFeature]) -> "MotherCandidateGenerator":
        return MotherCandidateGenerator(
            ctx=self.ctx,
            extractor=self.extractor,
            pool_builder=self.pool_builder,
            features=features,
            scorer=self.scorer,
        )

    def predict_for_atom(self, daughter_atom: int, top_k: int | None = 5) -> list[Candidate]:
        d_view = self.extractor.extract(daughter_atom)
        candidates: list[Candidate] = []

        for mother_atom in self.pool_builder.build(daughter_atom):
            m_view = self.extractor.extract(mother_atom)
            evidences = self._collect_evidence(d_view, m_view)
            score, parallel, quotation = self.scorer.score(d_view, m_view, evidences, self.ctx)
            if score <= 0:
                continue
            predicted_rela = infer_rela(evidences, parallel, quotation)
            candidates.append(
                Candidate(
                    daughter=daughter_atom,
                    mother=mother_atom,
                    score=score,
                    evidences=tuple(sorted(evidences, key=lambda e: (e.weight, e.label), reverse=True)),
                    predicted_sub1=".",
                    predicted_sub2=infer_sub2(evidences, quotation),
                    predicted_rela=predicted_rela,
                    predicted_typ=d_view.typ,
                    parallel=parallel,
                    quotation=quotation,
                )
            )

        candidates.sort(key=lambda c: c.score, reverse=True)
        return candidates if top_k is None else candidates[:top_k]

    def _collect_evidence(self, daughter: ClauseAtomView, mother: ClauseAtomView) -> list[Evidence]:
        out: list[Evidence] = []
        for feat in self.features:
            out.extend(feat.extract(daughter, mother, self.ctx))
        return out


# ---------------------------------------------------------------------------
# Training data and weight fitting
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PairwiseTrainingRow:
    daughter: int
    mother: int
    y: int
    distance: int
    labels: tuple[str, ...]
    section: Any
    gold_rela: str | None
    code: int | None


class TrainingBuilder:
    def __init__(self, ctx: BhsaContext, generator: MotherCandidateGenerator) -> None:
        self.ctx = ctx
        self.generator = generator

    def build_rows(self, books: Sequence[str] | None = None, limit: int | None = None) -> Iterable[PairwiseTrainingRow]:
        for daughter in self.ctx.iter_atoms(books=books, limit=limit):
            gold = self.ctx.mother_of(daughter)
            if gold is None:
                continue
            d_view = self.generator.extractor.extract(daughter)
            pool = self.generator.pool_builder.build(daughter)
            for mother in pool:
                m_view = self.generator.extractor.extract(mother)
                evidences = self.generator._collect_evidence(d_view, m_view)
                yield PairwiseTrainingRow(
                    daughter=daughter,
                    mother=mother,
                    y=int(gold == mother),
                    distance=abs(self.ctx.atom_distance(daughter, mother)),
                    labels=tuple(sorted({ev.label for ev in evidences})),
                    section=self.ctx.section_of(daughter),
                    gold_rela=self.ctx.rela_of_atom(daughter),
                    code=self.ctx.code_of_atom(daughter),
                )


def fit_arg_weights_log_odds(
    rows: Iterable[PairwiseTrainingRow],
    alpha: float = 0.5,
) -> dict[str, ArgWeight]:
    rows = list(rows)
    total_pos = sum(r.y for r in rows)
    total_neg = max(len(rows) - total_pos, 1)

    pos_count: Counter[str] = Counter()
    neg_count: Counter[str] = Counter()
    dist_sum: Counter[str] = Counter()
    dist_n: Counter[str] = Counter()
    par_sum: Counter[str] = Counter()
    quo_sum: Counter[str] = Counter()

    for row in rows:
        labels = set(row.labels)
        for lbl in labels:
            if row.y:
                pos_count[lbl] += 1
                dist_sum[lbl] += row.distance
                dist_n[lbl] += 1
                if row.code in {200, 201}:
                    par_sum[lbl] += 1
                if row.code == 999:
                    quo_sum[lbl] += 1
            else:
                neg_count[lbl] += 1

    base = log((total_pos + alpha) / (total_neg + alpha))
    out: dict[str, ArgWeight] = {}
    for lbl in sorted(set(pos_count) | set(neg_count)):
        p = pos_count[lbl]
        n = neg_count[lbl]
        weight = log((p + alpha) / (n + alpha)) - base
        out[lbl] = ArgWeight(
            label=lbl,
            weight=weight,
            mean_distance=(dist_sum[lbl] / dist_n[lbl]) if dist_n[lbl] else None,
            par=(par_sum[lbl] / dist_n[lbl]) if dist_n[lbl] else 0.0,
            quo=(quo_sum[lbl] / dist_n[lbl]) if dist_n[lbl] else 0.0,
            freq=p,
        )
    return out


def fit_resources_from_gold(
    generator: MotherCandidateGenerator,
    *,
    books: Sequence[str] | None = None,
    limit: int | None = None,
    alpha: float = 0.5,
) -> ResourceTables:
    trainer = TrainingBuilder(generator.ctx, generator)
    rows = list(trainer.build_rows(books=books, limit=limit))
    learned = fit_arg_weights_log_odds(rows, alpha=alpha)
    src = generator.ctx.resources
    return ResourceTables(
        arg_weights=learned,
        quote_verbs=src.quote_verbs,
        object_clause_governors=src.object_clause_governors,
        subject_clause_governors=src.subject_clause_governors,
        predicative_clause_governors=src.predicative_clause_governors,
        conjunction_classes=src.conjunction_classes,
        preposition_classes=src.preposition_classes,
        infinitive_preposition_classes=src.infinitive_preposition_classes,
        relative_lexemes=src.relative_lexemes,
    )


# ---------------------------------------------------------------------------
# Diagnostics
# ---------------------------------------------------------------------------


OPENING_CLASS_LABELS = {
    "ADJU_COND",
    "ADJU_FINAL",
    "ADJU_CAUSAL",
    "ADJU_TEMP700",
    "ADJU_TEMP800",
    "ADJU_CAUS900",
}


def _rank_of_gold(candidates: Sequence[Candidate], gold: int | None) -> int | None:
    if gold is None:
        return None
    for i, cand in enumerate(candidates, start=1):
        if cand.mother == gold:
            return i
    return None


def _counter_rows(
    counter: Counter[str],
    *,
    covered_predicate,
    class_mapping: Mapping[str, str] | None = None,
) -> tuple[dict[str, float | int], list[dict[str, Any]]]:
    rows: list[dict[str, Any]] = []
    covered_occ = 0
    covered_types = 0
    for lex, count in counter.items():
        covered = bool(covered_predicate(lex))
        if covered:
            covered_occ += count
            covered_types += 1
        row: dict[str, Any] = {
            "lex": lex,
            "count": count,
            "covered": covered,
        }
        if class_mapping is not None:
            row["class"] = class_mapping.get(lex)
        rows.append(row)
    rows.sort(key=lambda r: (-int(r["count"]), str(r["lex"])))
    total_occ = sum(counter.values())
    total_types = len(counter)
    return (
        {
            "occurrences": total_occ,
            "types": total_types,
            "covered_occurrences": covered_occ,
            "covered_types": covered_types,
            "occurrence_coverage": covered_occ / max(total_occ, 1),
            "type_coverage": covered_types / max(total_types, 1),
        },
        rows,
    )


def _governor_counter_rows(counter: Counter[str], covered_set: frozenset[str]) -> tuple[dict[str, float | int], list[dict[str, Any]]]:
    return _counter_rows(counter, covered_predicate=lambda lex: lex in covered_set)


def audit_resource_tables(
    generator: MotherCandidateGenerator,
    *,
    books: Sequence[str] | None = None,
    limit: int | None = None,
) -> dict[str, Any]:
    ctx = generator.ctx
    extractor = generator.extractor

    opening_conj = Counter()
    opening_prep = Counter()
    relative_markers = Counter()
    gold_object_governors = Counter()
    gold_subject_governors = Counter()
    gold_predicative_governors = Counter()
    quote_governor_candidates = Counter()

    totals = Counter()

    for daughter in ctx.iter_atoms(books=books, limit=limit):
        totals["atoms"] += 1
        d_view = extractor.extract(daughter)

        for lex in d_view.opening_conjunction_lexemes:
            opening_conj[lex] += 1
        for lex in d_view.opening_preposition_lexemes:
            opening_prep[lex] += 1

        rel_lexs: list[str] = []
        for phrase in d_view.phrases:
            if phrase.function == "Rela":
                rel_lexs.extend(lex for lex in phrase.lexemes if lex)
        if d_view.relative_marker:
            if not rel_lexs and d_view.opening_conjunction_lexemes:
                rel_lexs.extend(d_view.opening_conjunction_lexemes)
            if not rel_lexs:
                rel_lexs.append("<IMPLICIT>")
            for lex in rel_lexs:
                relative_markers[lex] += 1

        gold = ctx.mother_of(daughter)
        if gold is None:
            continue

        totals["with_gold"] += 1
        gold_rela = ctx.rela_of_atom(daughter) or "None"
        m_view = extractor.extract(gold)
        mlex = m_view.predicate.lex if m_view.predicate else None
        if not mlex:
            continue

        if gold_rela == "Objc":
            gold_object_governors[mlex] += 1
        elif gold_rela == "Subj":
            gold_subject_governors[mlex] += 1
        elif gold_rela == "PreC":
            gold_predicative_governors[mlex] += 1

        if d_view.txt == "Q":
            quote_governor_candidates[mlex] += 1

    conj_summary, conj_rows = _counter_rows(
        opening_conj,
        covered_predicate=lambda lex: lex in ctx.resources.conjunction_classes,
        class_mapping=ctx.resources.conjunction_classes,
    )
    prep_summary, prep_rows = _counter_rows(
        opening_prep,
        covered_predicate=lambda lex: lex in ctx.resources.preposition_classes,
        class_mapping=ctx.resources.preposition_classes,
    )
    rel_summary, rel_rows = _counter_rows(
        relative_markers,
        covered_predicate=lambda lex: lex == "<IMPLICIT>" or lex in ctx.resources.relative_lexemes,
    )
    obj_summary, obj_rows = _governor_counter_rows(gold_object_governors, ctx.resources.object_clause_governors)
    subj_summary, subj_rows = _governor_counter_rows(gold_subject_governors, ctx.resources.subject_clause_governors)
    prec_summary, prec_rows = _governor_counter_rows(gold_predicative_governors, ctx.resources.predicative_clause_governors)
    quote_summary, quote_rows = _governor_counter_rows(quote_governor_candidates, ctx.resources.quote_verbs)

    summary = {
        "atoms": totals["atoms"],
        "with_gold": totals["with_gold"],
        "opening_conjunction_occurrence_coverage": conj_summary["occurrence_coverage"],
        "opening_conjunction_type_coverage": conj_summary["type_coverage"],
        "opening_preposition_occurrence_coverage": prep_summary["occurrence_coverage"],
        "opening_preposition_type_coverage": prep_summary["type_coverage"],
        "relative_marker_occurrence_coverage": rel_summary["occurrence_coverage"],
        "relative_marker_type_coverage": rel_summary["type_coverage"],
        "gold_object_governor_coverage": obj_summary["occurrence_coverage"],
        "gold_subject_governor_coverage": subj_summary["occurrence_coverage"],
        "gold_predicative_governor_coverage": prec_summary["occurrence_coverage"],
        "quote_governor_candidate_coverage": quote_summary["occurrence_coverage"],
    }

    return {
        "summary": summary,
        "opening_conjunctions": {"summary": conj_summary, "rows": conj_rows},
        "opening_prepositions": {"summary": prep_summary, "rows": prep_rows},
        "relative_markers": {"summary": rel_summary, "rows": rel_rows},
        "gold_object_governors": {"summary": obj_summary, "rows": obj_rows},
        "gold_subject_governors": {"summary": subj_summary, "rows": subj_rows},
        "gold_predicative_governors": {"summary": prec_summary, "rows": prec_rows},
        "quote_governor_candidates": {"summary": quote_summary, "rows": quote_rows},
    }


def evaluate_by_gold_relation(
    generator: MotherCandidateGenerator,
    *,
    books: Sequence[str] | None = None,
    limit: int | None = None,
    top_k: int = 5,
) -> list[dict[str, Any]]:
    ctx = generator.ctx
    counts = defaultdict(Counter)
    rank_sum = defaultdict(float)
    rr_sum = defaultdict(float)

    for daughter in ctx.iter_atoms(books=books, limit=limit):
        gold = ctx.mother_of(daughter)
        if gold is None:
            continue
        rel = ctx.rela_of_atom(daughter) or "None"
        counts[rel]["with_gold"] += 1
        pool = generator.pool_builder.build(daughter)
        if gold in pool:
            counts[rel]["gold_in_pool"] += 1
        full_preds = generator.predict_for_atom(daughter, top_k=None)
        gold_rank = _rank_of_gold(full_preds, gold)
        if gold_rank is not None:
            counts[rel]["gold_scored"] += 1
            rank_sum[rel] += gold_rank
            rr_sum[rel] += 1.0 / gold_rank
            if gold_rank <= 1:
                counts[rel]["hit@1"] += 1
            if gold_rank <= 3:
                counts[rel]["hit@3"] += 1
            if top_k not in {1, 3} and gold_rank <= top_k:
                counts[rel][f"hit@{top_k}"] += 1

    rows: list[dict[str, Any]] = []
    for rel, cnt in counts.items():
        wg = max(cnt["with_gold"], 1)
        gs = max(cnt["gold_scored"], 1)
        dynamic_hits = cnt["hit@1"] if top_k == 1 else cnt["hit@3"] if top_k == 3 else cnt[f"hit@{top_k}"]
        rows.append(
            {
                "gold_rela": rel,
                "with_gold": cnt["with_gold"],
                "candidate_pool_coverage": cnt["gold_in_pool"] / wg,
                "scored_coverage": cnt["gold_scored"] / wg,
                "hit@1": cnt["hit@1"] / wg,
                "hit@3": cnt["hit@3"] / wg,
                f"hit@{top_k}": dynamic_hits / wg,
                "mrr": rr_sum[rel] / wg,
                "avg_gold_rank": rank_sum[rel] / gs,
            }
        )
    rows.sort(key=lambda r: (-int(r["with_gold"]), str(r["gold_rela"])))
    return rows


def gold_evidence_coverage(
    generator: MotherCandidateGenerator,
    *,
    books: Sequence[str] | None = None,
    limit: int | None = None,
) -> dict[str, Any]:
    ctx = generator.ctx
    label_counts = Counter()
    opening_class_counts = Counter()
    totals = Counter()

    for daughter in ctx.iter_atoms(books=books, limit=limit):
        gold = ctx.mother_of(daughter)
        if gold is None:
            continue
        totals["with_gold"] += 1
        full_preds = generator.predict_for_atom(daughter, top_k=None)
        cand = next((cand for cand in full_preds if cand.mother == gold), None)
        if cand is None:
            continue
        totals["gold_scored"] += 1
        labels = {ev.label for ev in cand.evidences}
        for lbl in labels:
            label_counts[lbl] += 1
        opening_hits = labels & OPENING_CLASS_LABELS
        if opening_hits:
            totals["gold_pairs_with_opening_class"] += 1
            for lbl in opening_hits:
                opening_class_counts[lbl] += 1

    rows = [
        {
            "label": lbl,
            "gold_pair_count": count,
            "gold_pair_coverage": count / max(totals["with_gold"], 1),
        }
        for lbl, count in label_counts.items()
    ]
    rows.sort(key=lambda r: (-int(r["gold_pair_count"]), str(r["label"])))

    opening_rows = [
        {
            "label": lbl,
            "gold_pair_count": count,
            "gold_pair_coverage": count / max(totals["with_gold"], 1),
        }
        for lbl, count in opening_class_counts.items()
    ]
    opening_rows.sort(key=lambda r: (-int(r["gold_pair_count"]), str(r["label"])))

    summary = {
        "with_gold": totals["with_gold"],
        "gold_scored": totals["gold_scored"],
        "gold_pairs_with_opening_class": totals["gold_pairs_with_opening_class"],
        "opening_class_gold_pair_coverage": totals["gold_pairs_with_opening_class"] / max(totals["with_gold"], 1),
    }
    return {
        "summary": summary,
        "rows": rows,
        "opening_class_rows": opening_rows,
    }


def diagnose_generator(
    generator: MotherCandidateGenerator,
    *,
    books: Sequence[str] | None = None,
    limit: int | None = None,
    top_k: int = 5,
) -> dict[str, Any]:
    baseline = evaluate_generator(generator, books=books, limit=limit, top_k=top_k, error_limit=0)
    resource_audit = audit_resource_tables(generator, books=books, limit=limit)
    relation_slices = evaluate_by_gold_relation(generator, books=books, limit=limit, top_k=top_k)
    evidence = gold_evidence_coverage(generator, books=books, limit=limit)
    return {
        "baseline_summary": baseline["summary"],
        "resource_audit": resource_audit,
        "per_relation": relation_slices,
        "gold_evidence_coverage": evidence,
    }


def render_diagnostic_markdown(report: Mapping[str, Any], *, top_k: int = 5, top_n: int = 25) -> str:
    base = report["baseline_summary"]
    audit = report["resource_audit"]
    ev = report["gold_evidence_coverage"]
    lines = [
        "# Mother candidate generator diagnostics",
        "",
        "## Baseline summary",
        "",
        f"- with_gold: {base['with_gold']}",
        f"- candidate_pool_coverage: {base['candidate_pool_coverage']:.4f}",
        f"- scored_coverage: {base['scored_coverage']:.4f}",
        f"- hit@1: {base['hit@1']:.4f}",
        f"- hit@3: {base['hit@3']:.4f}",
        f"- mrr: {base['mrr']:.4f}",
    ]
    if top_k not in {1, 3}:
        lines.append(f"- hit@{top_k}: {base[f'hit@{top_k}']:.4f}")

    lines.extend(
        [
            "",
            "## Resource-table coverage summary",
            "",
            f"- opening conjunction occurrence coverage: {audit['summary']['opening_conjunction_occurrence_coverage']:.4f}",
            f"- opening conjunction type coverage: {audit['summary']['opening_conjunction_type_coverage']:.4f}",
            f"- opening preposition occurrence coverage: {audit['summary']['opening_preposition_occurrence_coverage']:.4f}",
            f"- opening preposition type coverage: {audit['summary']['opening_preposition_type_coverage']:.4f}",
            f"- relative marker occurrence coverage: {audit['summary']['relative_marker_occurrence_coverage']:.4f}",
            f"- gold object-governor coverage: {audit['summary']['gold_object_governor_coverage']:.4f}",
            f"- gold subject-governor coverage: {audit['summary']['gold_subject_governor_coverage']:.4f}",
            f"- gold predicative-governor coverage: {audit['summary']['gold_predicative_governor_coverage']:.4f}",
            f"- heuristic quote-governor coverage: {audit['summary']['quote_governor_candidate_coverage']:.4f}",
            "",
            "## Gold-relation slices",
            "",
        ]
    )

    rel_header = ["gold_rela", "with_gold", "pool_cov", "scored_cov", "hit@1", "hit@3"]
    if top_k not in {1, 3}:
        rel_header.append(f"hit@{top_k}")
    rel_header.extend(["mrr", "avg_rank"])
    lines.append("| " + " | ".join(rel_header) + " |")
    lines.append("|" + "|".join(["---"] + ["---:" for _ in rel_header[1:]]) + "|")
    for row in report["per_relation"]:
        cells = [
            row["gold_rela"],
            str(row["with_gold"]),
            f"{row['candidate_pool_coverage']:.4f}",
            f"{row['scored_coverage']:.4f}",
            f"{row['hit@1']:.4f}",
            f"{row['hit@3']:.4f}",
        ]
        if top_k not in {1, 3}:
            cells.append(f"{row[f'hit@{top_k}']:.4f}")
        cells.extend([f"{row['mrr']:.4f}", f"{row['avg_gold_rank']:.4f}"])
        lines.append("| " + " | ".join(cells) + " |")

    lines.extend(
        [
            "",
            "## Gold-evidence coverage",
            "",
            f"- gold_scored: {ev['summary']['gold_scored']}",
            f"- gold_pairs_with_opening_class: {ev['summary']['gold_pairs_with_opening_class']}",
            f"- opening_class_gold_pair_coverage: {ev['summary']['opening_class_gold_pair_coverage']:.4f}",
            "",
            "| label | gold_pair_count | gold_pair_coverage |",
            "|---|---:|---:|",
        ]
    )
    for row in ev["rows"][:top_n]:
        lines.append(f"| {row['label']} | {row['gold_pair_count']} | {row['gold_pair_coverage']:.4f} |")

    lines.extend(
        [
            "",
            "## Opening-class evidence on gold pairs",
            "",
            "| label | gold_pair_count | gold_pair_coverage |",
            "|---|---:|---:|",
        ]
    )
    for row in ev["opening_class_rows"][:top_n]:
        lines.append(f"| {row['label']} | {row['gold_pair_count']} | {row['gold_pair_coverage']:.4f} |")

    section_specs = [
        ("Top uncovered opening conjunction lexemes", audit["opening_conjunctions"]["rows"]),
        ("Top uncovered opening preposition lexemes", audit["opening_prepositions"]["rows"]),
        ("Top uncovered relative-marker lexemes", audit["relative_markers"]["rows"]),
        ("Top uncovered object-clause governors on gold pairs", audit["gold_object_governors"]["rows"]),
        ("Top uncovered subject-clause governors on gold pairs", audit["gold_subject_governors"]["rows"]),
        ("Top uncovered predicative-clause governors on gold pairs", audit["gold_predicative_governors"]["rows"]),
        ("Top uncovered heuristic quote governors", audit["quote_governor_candidates"]["rows"]),
    ]
    for title, rows in section_specs:
        if rows and "class" in rows[0]:
            lines.extend(["", f"## {title}", "", "| lex | count | class |", "|---|---:|---|"])
            for row in [r for r in rows if not r["covered"]][:top_n]:
                lines.append(f"| {row['lex']} | {row['count']} | {row.get('class') or ''} |")
        else:
            lines.extend(["", f"## {title}", "", "| lex | count | covered |", "|---|---:|---:|"])
            for row in [r for r in rows if not r["covered"]][:top_n]:
                lines.append(f"| {row['lex']} | {row['count']} | {row['covered']} |")
    return "\n".join(lines)


def _counter_top(counter: Counter[str]) -> tuple[str | None, int, float]:
    total = sum(counter.values())
    if total <= 0:
        return (None, 0, 0.0)
    label, count = counter.most_common(1)[0]
    return (label, count, count / total)


def profile_opening_lexemes(
    generator: MotherCandidateGenerator,
    *,
    kind: str,
    books: Sequence[str] | None = None,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    if kind not in {"conjunction", "preposition"}:
        raise ValueError("kind must be 'conjunction' or 'preposition'")

    ctx = generator.ctx
    extractor = generator.extractor
    profiles: dict[str, dict[str, Any]] = {}

    for daughter in ctx.iter_atoms(books=books, limit=limit):
        d_view = extractor.extract(daughter)
        lexs = d_view.opening_conjunction_lexemes if kind == "conjunction" else d_view.opening_preposition_lexemes
        if not lexs:
            continue

        gold = ctx.mother_of(daughter)
        gold_rela = (ctx.rela_of_atom(daughter) or "None") if gold is not None else None
        book = ctx.book_of(daughter)
        txt = d_view.txt or "None"

        for lex in lexs:
            prof = profiles.setdefault(
                lex,
                {
                    "lex": lex,
                    "count": 0,
                    "with_gold": 0,
                    "gold_rela_counts": Counter(),
                    "txt_counts": Counter(),
                    "book_counts": Counter(),
                },
            )
            prof["count"] += 1
            prof["txt_counts"][txt] += 1
            prof["book_counts"][book] += 1
            if gold is not None:
                prof["with_gold"] += 1
                prof["gold_rela_counts"][gold_rela] += 1

    rows: list[dict[str, Any]] = []
    for lex, prof in profiles.items():
        top_rela, top_rela_count, top_rela_share = _counter_top(prof["gold_rela_counts"])
        top_txt, top_txt_count, top_txt_share = _counter_top(prof["txt_counts"])
        top_book, top_book_count, top_book_share = _counter_top(prof["book_counts"])
        rows.append(
            {
                "lex": lex,
                "count": prof["count"],
                "with_gold": prof["with_gold"],
                "top_gold_rela": top_rela,
                "top_gold_rela_count": top_rela_count,
                "top_gold_rela_share": top_rela_share,
                "top_txt": top_txt,
                "top_txt_count": top_txt_count,
                "top_txt_share": top_txt_share,
                "top_book": top_book,
                "top_book_count": top_book_count,
                "top_book_share": top_book_share,
                "gold_rela_counts": dict(prof["gold_rela_counts"]),
                "txt_counts": dict(prof["txt_counts"]),
                "book_counts": dict(prof["book_counts"]),
            }
        )

    rows.sort(key=lambda r: (-int(r["count"]), str(r["lex"])))
    return rows


def _manual_opening_hint(row: Mapping[str, Any], *, kind: str) -> str:
    top_rela = row.get("top_gold_rela")
    top_rela_share = float(row.get("top_gold_rela_share") or 0.0)
    top_txt = row.get("top_txt")
    top_txt_share = float(row.get("top_txt_share") or 0.0)

    if kind == "conjunction":
        if top_rela == "Coor" and top_rela_share >= 0.60:
            return "likely_coordinate_opener"
        if top_rela == "Adju" and top_rela_share >= 0.60:
            return "likely_adverbial_opener"
        if top_rela == "Attr" and top_rela_share >= 0.60:
            return "likely_relative_or_attributive_opener"
        if top_rela == "Objc" and top_rela_share >= 0.60:
            return "possible_complementizer"
        if top_txt == "Q" and top_txt_share >= 0.50:
            return "possible_speech_introducer"
        return "manual_review"

    if top_rela == "Adju" and top_rela_share >= 0.60:
        return "likely_adverbial_preposition"
    if top_rela == "Attr" and top_rela_share >= 0.60:
        return "possible_relative_preposition"
    if top_txt == "Q" and top_txt_share >= 0.50:
        return "possible_speech_preposition"
    return "manual_review"


def _mine_set_additions(
    rows: Sequence[Mapping[str, Any]],
    *,
    min_count: int,
    exclude: frozenset[str] | None = None,
    note: str,
) -> list[dict[str, Any]]:
    exclude = exclude or frozenset()
    out: list[dict[str, Any]] = []
    for row in rows:
        lex = str(row["lex"])
        if bool(row.get("covered")):
            continue
        if lex in exclude:
            continue
        count = int(row.get("count", 0))
        if count < min_count:
            continue
        out.append(
            {
                "lex": lex,
                "count": count,
                "source": note,
            }
        )
    out.sort(key=lambda r: (-int(r["count"]), str(r["lex"])))
    return out


def mine_resource_suggestions(
    generator: MotherCandidateGenerator,
    *,
    books: Sequence[str] | None = None,
    limit: int | None = None,
    min_count: int = 2,
) -> dict[str, Any]:
    audit = audit_resource_tables(generator, books=books, limit=limit)
    conj_profiles = {
        row["lex"]: row
        for row in profile_opening_lexemes(generator, kind="conjunction", books=books, limit=limit)
    }
    prep_profiles = {
        row["lex"]: row
        for row in profile_opening_lexemes(generator, kind="preposition", books=books, limit=limit)
    }

    safe_additions = {
        "relative_lexemes": {
            "rows": _mine_set_additions(
                audit["relative_markers"]["rows"],
                min_count=min_count,
                exclude=frozenset({"<IMPLICIT>"}),
                note="uncovered_relative_marker",
            )
        },
        "object_clause_governors": {
            "rows": _mine_set_additions(
                audit["gold_object_governors"]["rows"],
                min_count=min_count,
                note="uncovered_gold_object_governor",
            )
        },
        "subject_clause_governors": {
            "rows": _mine_set_additions(
                audit["gold_subject_governors"]["rows"],
                min_count=min_count,
                note="uncovered_gold_subject_governor",
            )
        },
        "predicative_clause_governors": {
            "rows": _mine_set_additions(
                audit["gold_predicative_governors"]["rows"],
                min_count=min_count,
                note="uncovered_gold_predicative_governor",
            )
        },
        "quote_verbs": {
            "rows": _mine_set_additions(
                audit["quote_governor_candidates"]["rows"],
                min_count=min_count,
                note="uncovered_quote_governor_candidate",
            )
        },
    }

    relative_skip = set(generator.ctx.resources.relative_lexemes) | {
        str(row["lex"]) for row in safe_additions["relative_lexemes"]["rows"]
    }

    manual_conj_rows: list[dict[str, Any]] = []
    for row in audit["opening_conjunctions"]["rows"]:
        if bool(row.get("covered")) or int(row.get("count", 0)) < min_count:
            continue
        if str(row.get("lex")) in relative_skip:
            continue
        profile = conj_profiles.get(str(row["lex"]), {})
        manual_conj_rows.append(
            {
                "lex": row["lex"],
                "count": row["count"],
                "hint": _manual_opening_hint(profile, kind="conjunction"),
                "top_gold_rela": profile.get("top_gold_rela"),
                "top_gold_rela_share": profile.get("top_gold_rela_share", 0.0),
                "top_txt": profile.get("top_txt"),
                "top_txt_share": profile.get("top_txt_share", 0.0),
                "top_book": profile.get("top_book"),
                "gold_rela_counts": profile.get("gold_rela_counts", {}),
            }
        )
    manual_conj_rows.sort(key=lambda r: (-int(r["count"]), str(r["lex"])))

    manual_prep_rows: list[dict[str, Any]] = []
    for row in audit["opening_prepositions"]["rows"]:
        if bool(row.get("covered")) or int(row.get("count", 0)) < min_count:
            continue
        if str(row.get("lex")) in relative_skip:
            continue
        profile = prep_profiles.get(str(row["lex"]), {})
        manual_prep_rows.append(
            {
                "lex": row["lex"],
                "count": row["count"],
                "hint": _manual_opening_hint(profile, kind="preposition"),
                "top_gold_rela": profile.get("top_gold_rela"),
                "top_gold_rela_share": profile.get("top_gold_rela_share", 0.0),
                "top_txt": profile.get("top_txt"),
                "top_txt_share": profile.get("top_txt_share", 0.0),
                "top_book": profile.get("top_book"),
                "gold_rela_counts": profile.get("gold_rela_counts", {}),
            }
        )
    manual_prep_rows.sort(key=lambda r: (-int(r["count"]), str(r["lex"])))

    summary = {
        "min_count": min_count,
        "safe_relative_lexemes": len(safe_additions["relative_lexemes"]["rows"]),
        "safe_object_clause_governors": len(safe_additions["object_clause_governors"]["rows"]),
        "safe_subject_clause_governors": len(safe_additions["subject_clause_governors"]["rows"]),
        "safe_predicative_clause_governors": len(safe_additions["predicative_clause_governors"]["rows"]),
        "safe_quote_verbs": len(safe_additions["quote_verbs"]["rows"]),
        "manual_opening_conjunctions": len(manual_conj_rows),
        "manual_opening_prepositions": len(manual_prep_rows),
    }

    return {
        "summary": summary,
        "resource_audit_summary": audit["summary"],
        "safe_additions": safe_additions,
        "manual_review": {
            "opening_conjunctions": {"rows": manual_conj_rows},
            "opening_prepositions": {"rows": manual_prep_rows},
        },
    }


def patch_resources_with_suggestions(
    resources: ResourceTables,
    report: Mapping[str, Any],
    *,
    include_quote_verbs: bool = False,
) -> ResourceTables:
    data = resources.to_json_dict()

    def merge_set(field_name: str) -> None:
        current = set(data.get(field_name, []))
        current.update(str(row["lex"]) for row in report["safe_additions"][field_name]["rows"])
        data[field_name] = sorted(current)

    merge_set("relative_lexemes")
    merge_set("object_clause_governors")
    merge_set("subject_clause_governors")
    merge_set("predicative_clause_governors")
    if include_quote_verbs:
        merge_set("quote_verbs")

    return ResourceTables.from_json_dict(data)


def render_mining_markdown(report: Mapping[str, Any], *, top_n: int = 25, include_quote_verbs: bool = False) -> str:
    summary = report["summary"]
    lines = [
        "# Resource suggestion miner",
        "",
        "## Summary",
        "",
        f"- min_count: {summary['min_count']}",
        f"- safe relative_lexemes: {summary['safe_relative_lexemes']}",
        f"- safe object_clause_governors: {summary['safe_object_clause_governors']}",
        f"- safe subject_clause_governors: {summary['safe_subject_clause_governors']}",
        f"- safe predicative_clause_governors: {summary['safe_predicative_clause_governors']}",
        f"- safe quote_verbs: {summary['safe_quote_verbs']}",
        f"- manual opening conjunctions: {summary['manual_opening_conjunctions']}",
        f"- manual opening prepositions: {summary['manual_opening_prepositions']}",
        "",
        "Quote verbs stay out of the merged patch unless `--apply-quote-verbs` is given.",
    ]

    safe_sections = [
        ("relative_lexemes", report["safe_additions"]["relative_lexemes"]["rows"]),
        ("object_clause_governors", report["safe_additions"]["object_clause_governors"]["rows"]),
        ("subject_clause_governors", report["safe_additions"]["subject_clause_governors"]["rows"]),
        ("predicative_clause_governors", report["safe_additions"]["predicative_clause_governors"]["rows"]),
    ]
    if include_quote_verbs or report["safe_additions"]["quote_verbs"]["rows"]:
        safe_sections.append(("quote_verbs", report["safe_additions"]["quote_verbs"]["rows"]))

    for title, rows in safe_sections:
        lines.extend(["", f"## Safe additions: {title}", "", "| lex | count | source |", "|---|---:|---|"])
        for row in rows[:top_n]:
            lines.append(f"| {row['lex']} | {row['count']} | {row['source']} |")
        if not rows:
            lines.append("| *(none)* | 0 |  |")

    lines.extend(["", "## Manual review: opening conjunctions", "", "| lex | count | hint | top_gold_rela | top_gold_rela_share | top_txt | top_book |", "|---|---:|---|---|---:|---|---|"])
    for row in report["manual_review"]["opening_conjunctions"]["rows"][:top_n]:
        lines.append(
            f"| {row['lex']} | {row['count']} | {row['hint']} | {row.get('top_gold_rela') or ''} | {float(row.get('top_gold_rela_share') or 0.0):.4f} | {row.get('top_txt') or ''} | {row.get('top_book') or ''} |"
        )
    if not report["manual_review"]["opening_conjunctions"]["rows"]:
        lines.append("| *(none)* | 0 |  |  | 0.0000 |  |  |")

    lines.extend(["", "## Manual review: opening prepositions", "", "| lex | count | hint | top_gold_rela | top_gold_rela_share | top_txt | top_book |", "|---|---:|---|---|---:|---|---|"])
    for row in report["manual_review"]["opening_prepositions"]["rows"][:top_n]:
        lines.append(
            f"| {row['lex']} | {row['count']} | {row['hint']} | {row.get('top_gold_rela') or ''} | {float(row.get('top_gold_rela_share') or 0.0):.4f} | {row.get('top_txt') or ''} | {row.get('top_book') or ''} |"
        )
    if not report["manual_review"]["opening_prepositions"]["rows"]:
        lines.append("| *(none)* | 0 |  |  | 0.0000 |  |  |")

    return "\n".join(lines)


def candidate_to_dict(cand: Candidate, ctx: BhsaContext) -> dict[str, Any]:
    return {
        "daughter": cand.daughter,
        "mother": cand.mother,
        "score": cand.score,
        "predicted_sub1": cand.predicted_sub1,
        "predicted_sub2": cand.predicted_sub2,
        "predicted_rela": cand.predicted_rela,
        "predicted_typ": cand.predicted_typ,
        "parallel": cand.parallel,
        "quotation": cand.quotation,
        "daughter_section": ctx.section_of(cand.daughter),
        "mother_section": ctx.section_of(cand.mother),
        "daughter_text": ctx.text_of(cand.daughter),
        "mother_text": ctx.text_of(cand.mother),
        "evidences": [asdict(ev) for ev in cand.evidences],
    }


def evaluate_generator(
    generator: MotherCandidateGenerator,
    *,
    books: Sequence[str] | None = None,
    limit: int | None = None,
    top_k: int = 5,
    error_limit: int = 25,
) -> dict[str, Any]:
    ctx = generator.ctx
    totals = Counter()
    hit_counts = Counter()
    gold_rank_sum = 0.0
    reciprocal_rank_sum = 0.0
    pool_sizes: list[int] = []
    scored_sizes: list[int] = []
    per_book = defaultdict(Counter)
    feature_pair_counts: Counter[str] = Counter()
    feature_pair_pos: Counter[str] = Counter()
    feature_top1_counts: Counter[str] = Counter()
    feature_top1_correct: Counter[str] = Counter()
    relation_confusion: Counter[tuple[str, str]] = Counter()
    top1_errors: list[dict[str, Any]] = []

    for daughter in ctx.iter_atoms(books=books, limit=limit):
        gold = ctx.mother_of(daughter)
        book = ctx.book_of(daughter)
        section = ctx.section_of(daughter)
        totals["atoms"] += 1
        per_book[book]["atoms"] += 1

        if gold is None:
            totals["roots"] += 1
            preds = generator.predict_for_atom(daughter, top_k=1)
            if not preds:
                totals["root_empty"] += 1
                per_book[book]["root_empty"] += 1
            continue

        totals["with_gold"] += 1
        per_book[book]["with_gold"] += 1

        pool = generator.pool_builder.build(daughter)
        pool_sizes.append(len(pool))
        if gold in pool:
            totals["gold_in_pool"] += 1
            per_book[book]["gold_in_pool"] += 1

        full_preds = generator.predict_for_atom(daughter, top_k=None)
        scored_sizes.append(len(full_preds))
        cand_map = {cand.mother: cand for cand in full_preds}

        for cand in full_preds:
            positive = int(cand.mother == gold)
            labels = {ev.label for ev in cand.evidences}
            for lbl in labels:
                feature_pair_counts[lbl] += 1
                feature_pair_pos[lbl] += positive

        gold_rank: int | None = None
        for i, cand in enumerate(full_preds, start=1):
            if cand.mother == gold:
                gold_rank = i
                break

        if gold_rank is not None:
            totals["gold_scored"] += 1
            per_book[book]["gold_scored"] += 1
            gold_rank_sum += gold_rank
            reciprocal_rank_sum += 1.0 / gold_rank
            if gold_rank <= 1:
                hit_counts["hit@1"] += 1
                per_book[book]["hit@1"] += 1
            if gold_rank <= 3:
                hit_counts["hit@3"] += 1
                per_book[book]["hit@3"] += 1
            if top_k not in {1, 3} and gold_rank <= top_k:
                hit_counts[f"hit@{top_k}"] += 1
                per_book[book][f"hit@{top_k}"] += 1
        else:
            totals["gold_not_scored"] += 1
            per_book[book]["gold_not_scored"] += 1

        top1 = full_preds[0] if full_preds else None
        if top1:
            for ev in {ev.label for ev in top1.evidences}:
                feature_top1_counts[ev] += 1
                if top1.mother == gold:
                    feature_top1_correct[ev] += 1

            gold_rela = ctx.rela_of_atom(daughter) or "None"
            pred_rela = top1.predicted_rela or "None"
            relation_confusion[(gold_rela, pred_rela)] += 1

            if top1.mother == gold:
                totals["top1_correct"] += 1
                per_book[book]["top1_correct"] += 1
                if gold_rela == pred_rela:
                    totals["top1_rela_correct"] += 1
                    per_book[book]["top1_rela_correct"] += 1
            elif len(top1_errors) < error_limit:
                top1_errors.append(
                    {
                        "daughter": daughter,
                        "section": section,
                        "daughter_text": ctx.text_of(daughter),
                        "gold_mother": gold,
                        "gold_mother_text": ctx.text_of(gold),
                        "predicted_mother": top1.mother,
                        "predicted_mother_text": ctx.text_of(top1.mother),
                        "predicted_score": top1.score,
                        "predicted_rela": top1.predicted_rela,
                        "gold_rela": ctx.rela_of_atom(daughter),
                        "gold_rank": gold_rank,
                        "evidences": [ev.label for ev in top1.evidences[:8]],
                    }
                )
        else:
            if len(top1_errors) < error_limit:
                top1_errors.append(
                    {
                        "daughter": daughter,
                        "section": section,
                        "daughter_text": ctx.text_of(daughter),
                        "gold_mother": gold,
                        "gold_mother_text": ctx.text_of(gold),
                        "predicted_mother": None,
                        "predicted_mother_text": None,
                        "predicted_score": None,
                        "predicted_rela": None,
                        "gold_rela": ctx.rela_of_atom(daughter),
                        "gold_rank": None,
                        "evidences": [],
                    }
                )

    with_gold = max(totals["with_gold"], 1)
    dynamic_hits = hit_counts["hit@1"] if top_k == 1 else hit_counts["hit@3"] if top_k == 3 else hit_counts[f"hit@{top_k}"]
    summary = {
        "atoms": totals["atoms"],
        "with_gold": totals["with_gold"],
        "roots": totals["roots"],
        "root_empty_rate": totals["root_empty"] / max(totals["roots"], 1),
        "candidate_pool_coverage": totals["gold_in_pool"] / with_gold,
        "scored_coverage": totals["gold_scored"] / with_gold,
        "hit@1": hit_counts["hit@1"] / with_gold,
        "hit@3": hit_counts["hit@3"] / with_gold,
        f"hit@{top_k}": dynamic_hits / with_gold,
        "mrr": reciprocal_rank_sum / with_gold,
        "avg_gold_rank": gold_rank_sum / max(totals["gold_scored"], 1),
        "top1_rela_accuracy_on_top1_correct": totals["top1_rela_correct"] / max(totals["top1_correct"], 1),
        "avg_pool_size": (sum(pool_sizes) / len(pool_sizes)) if pool_sizes else 0.0,
        "avg_scored_size": (sum(scored_sizes) / len(scored_sizes)) if scored_sizes else 0.0,
    }

    book_summary = {}
    for book, cnt in per_book.items():
        wg = max(cnt["with_gold"], 1)
        tc = max(cnt["top1_correct"], 1)
        dynamic_book_hits = cnt["hit@1"] if top_k == 1 else cnt["hit@3"] if top_k == 3 else cnt[f"hit@{top_k}"]
        book_summary[book] = {
            "atoms": cnt["atoms"],
            "with_gold": cnt["with_gold"],
            "candidate_pool_coverage": cnt["gold_in_pool"] / wg,
            "scored_coverage": cnt["gold_scored"] / wg,
            "hit@1": cnt["hit@1"] / wg,
            "hit@3": cnt["hit@3"] / wg,
            f"hit@{top_k}": dynamic_book_hits / wg,
            "top1_rela_accuracy_on_top1_correct": cnt["top1_rela_correct"] / tc,
        }

    feature_pair_precision = []
    for lbl in sorted(feature_pair_counts):
        feature_pair_precision.append(
            {
                "label": lbl,
                "pair_count": feature_pair_counts[lbl],
                "positive_pair_count": feature_pair_pos[lbl],
                "pair_precision": feature_pair_pos[lbl] / feature_pair_counts[lbl],
                "top1_count": feature_top1_counts[lbl],
                "top1_correct_count": feature_top1_correct[lbl],
                "top1_precision": feature_top1_correct[lbl] / max(feature_top1_counts[lbl], 1),
            }
        )
    feature_pair_precision.sort(key=lambda row: (-row["pair_precision"], -row["pair_count"], row["label"]))

    relation_rows = [
        {"gold_rela": gold, "predicted_rela": pred, "count": count}
        for ((gold, pred), count) in relation_confusion.most_common()
    ]

    return {
        "summary": summary,
        "per_book": book_summary,
        "feature_pair_precision": feature_pair_precision,
        "relation_confusion": relation_rows,
        "top1_errors": top1_errors,
    }


def render_eval_markdown(report: Mapping[str, Any], top_k: int = 5) -> str:
    summary = report["summary"]
    lines = [
        "# Mother candidate generator evaluation",
        "",
        "## Summary",
        "",
        f"- atoms: {summary['atoms']}",
        f"- with_gold: {summary['with_gold']}",
        f"- roots: {summary['roots']}",
        f"- root_empty_rate: {summary['root_empty_rate']:.4f}",
        f"- candidate_pool_coverage: {summary['candidate_pool_coverage']:.4f}",
        f"- scored_coverage: {summary['scored_coverage']:.4f}",
        f"- hit@1: {summary['hit@1']:.4f}",
        f"- hit@3: {summary['hit@3']:.4f}",
        f"- mrr: {summary['mrr']:.4f}",
        f"- avg_gold_rank: {summary['avg_gold_rank']:.4f}",
        f"- top1_rela_accuracy_on_top1_correct: {summary['top1_rela_accuracy_on_top1_correct']:.4f}",
        f"- avg_pool_size: {summary['avg_pool_size']:.2f}",
        f"- avg_scored_size: {summary['avg_scored_size']:.2f}",
    ]
    if top_k not in {1, 3}:
        lines.append(f"- hit@{top_k}: {summary[f'hit@{top_k}']:.4f}")
    lines.extend(["", "## Per-book", ""])

    header = ["Book", "with_gold", "pool_cov", "scored_cov", "hit@1", "hit@3"]
    if top_k not in {1, 3}:
        header.append(f"hit@{top_k}")
    header.append("top1_rela_acc")
    lines.append("| " + " | ".join(header) + " |")
    lines.append("|" + "|".join(["---"] + ["---:" for _ in header[1:]]) + "|")
    for book, row in sorted(report["per_book"].items()):
        cells = [
            book,
            str(row["with_gold"]),
            f"{row['candidate_pool_coverage']:.4f}",
            f"{row['scored_coverage']:.4f}",
            f"{row['hit@1']:.4f}",
            f"{row['hit@3']:.4f}",
        ]
        if top_k not in {1, 3}:
            cells.append(f"{row[f'hit@{top_k}']:.4f}")
        cells.append(f"{row['top1_rela_accuracy_on_top1_correct']:.4f}")
        lines.append("| " + " | ".join(cells) + " |")

    lines.extend(
        [
            "",
            "## Feature pair precision",
            "",
            "| label | pair_count | pair_precision | top1_count | top1_precision |",
            "|---|---:|---:|---:|---:|",
        ]
    )
    for row in report["feature_pair_precision"][:40]:
        lines.append(
            f"| {row['label']} | {row['pair_count']} | {row['pair_precision']:.4f} | {row['top1_count']} | {row['top1_precision']:.4f} |"
        )

    lines.extend(["", "## Top-1 errors", ""])
    for err in report["top1_errors"][:20]:
        lines.extend(
            [
                f"### {err['section']}",
                "",
                f"- daughter `{err['daughter']}`: {err['daughter_text']}",
                f"- gold mother `{err['gold_mother']}`: {err['gold_mother_text']}",
                f"- predicted mother `{err['predicted_mother']}`: {err['predicted_mother_text']}",
                f"- gold relation: {err['gold_rela']}",
                f"- predicted relation: {err['predicted_rela']}",
                f"- gold rank: {err['gold_rank']}",
                f"- evidences: {', '.join(err['evidences'])}",
                "",
            ]
        )
    return "\n".join(lines)
def ablate_features(
    generator: MotherCandidateGenerator,
    *,
    books: Sequence[str] | None = None,
    limit: int | None = None,
    top_k: int = 5,
) -> dict[str, Any]:
    baseline = evaluate_generator(generator, books=books, limit=limit, top_k=top_k)
    rows = []
    base_hit1 = baseline["summary"]["hit@1"]
    base_mrr = baseline["summary"]["mrr"]
    base_scored = baseline["summary"]["scored_coverage"]

    for i, feat in enumerate(generator.features):
        reduced = generator.clone_with_features(generator.features[:i] + generator.features[i + 1 :])
        rep = evaluate_generator(reduced, books=books, limit=limit, top_k=top_k, error_limit=0)
        rows.append(
            {
                "feature": feat.__class__.__name__,
                "hit@1": rep["summary"]["hit@1"],
                "mrr": rep["summary"]["mrr"],
                "scored_coverage": rep["summary"]["scored_coverage"],
                "delta_hit@1": rep["summary"]["hit@1"] - base_hit1,
                "delta_mrr": rep["summary"]["mrr"] - base_mrr,
                "delta_scored_coverage": rep["summary"]["scored_coverage"] - base_scored,
            }
        )
    rows.sort(key=lambda r: (r["delta_hit@1"], r["delta_mrr"]))
    return {"baseline": baseline["summary"], "ablations": rows}


def render_ablation_markdown(report: Mapping[str, Any]) -> str:
    baseline = report["baseline"]
    lines = [
        "# Feature ablation",
        "",
        f"- baseline hit@1: {baseline['hit@1']:.4f}",
        f"- baseline mrr: {baseline['mrr']:.4f}",
        f"- baseline scored_coverage: {baseline['scored_coverage']:.4f}",
        "",
        "| feature | hit@1 | delta_hit@1 | mrr | delta_mrr | scored_cov | delta_scored_cov |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in report["ablations"]:
        lines.append(
            f"| {row['feature']} | {row['hit@1']:.4f} | {row['delta_hit@1']:.4f} | "
            f"{row['mrr']:.4f} | {row['delta_mrr']:.4f} | "
            f"{row['scored_coverage']:.4f} | {row['delta_scored_coverage']:.4f} |"
        )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------


def export_predictions(
    generator: MotherCandidateGenerator,
    path: str | Path,
    *,
    books: Sequence[str] | None = None,
    limit: int | None = None,
    top_k: int = 5,
    fmt: str = "jsonl",
) -> None:
    ctx = generator.ctx
    out_path = Path(path)
    fmt = fmt.lower()

    rows: list[dict[str, Any]] = []
    for daughter in ctx.iter_atoms(books=books, limit=limit):
        preds = generator.predict_for_atom(daughter, top_k=top_k)
        rows.append(
            {
                "daughter": daughter,
                "section": ctx.section_of(daughter),
                "text": ctx.text_of(daughter),
                "gold_mother": ctx.mother_of(daughter),
                "predictions": [candidate_to_dict(cand, ctx) for cand in preds],
            }
        )

    if fmt == "json":
        out_path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
        return

    if fmt == "jsonl":
        with out_path.open("w", encoding="utf-8") as f:
            for row in rows:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
        return

    if fmt == "csv":
        with out_path.open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=[
                    "daughter",
                    "section",
                    "text",
                    "gold_mother",
                    "rank",
                    "mother",
                    "score",
                    "predicted_rela",
                    "predicted_sub2",
                    "parallel",
                    "quotation",
                    "evidences",
                ],
            )
            writer.writeheader()
            for row in rows:
                for rank, cand in enumerate(row["predictions"], start=1):
                    writer.writerow(
                        {
                            "daughter": row["daughter"],
                            "section": row["section"],
                            "text": row["text"],
                            "gold_mother": row["gold_mother"],
                            "rank": rank,
                            "mother": cand["mother"],
                            "score": cand["score"],
                            "predicted_rela": cand["predicted_rela"],
                            "predicted_sub2": cand["predicted_sub2"],
                            "parallel": cand["parallel"],
                            "quotation": cand["quotation"],
                            "evidences": ",".join(ev["label"] for ev in cand["evidences"]),
                        }
                    )
        return

    raise ValueError(f"Unsupported export format: {fmt}")


# ---------------------------------------------------------------------------
# Recommended registry and bootstrap
# ---------------------------------------------------------------------------


def official_etcbc_seed_resources() -> ResourceTables:
    """Starter tables grounded in published ETCBC/BHSA documentation.

    The conjunction/preposition class mappings come directly from the BHSA `code`
    documentation and CARC manual. Quote/object-clause lexeme lists are cautious
    starter heuristics based on the `syn04types` manual's list of lexemes that are
    internal to the program.
    """
    return ResourceTables(
        quote_verbs=frozenset({">MR[", "DBR[", "NGD["}),
        object_clause_governors=frozenset({">MR[", "DBR[", "NGD[", "JD<[", "R>H[", "CM<["}),
        subject_clause_governors=frozenset(),
        predicative_clause_governors=frozenset(),
        conjunction_classes={
            ">W": "coord",
            "W": "coord",
            ">CR": "postulational",
            "DJ": "postulational",
            "H": "postulational",
            "ZW": "postulational",
            "KJ": "postulational",
            "C": "postulational",
            ">LW": "conditional",
            ">M": "conditional",
            "HN": "conditional",
            "LHN=": "conditional",
            "LW": "conditional",
            "LWL>": "conditional",
            "PN": "final",
        },
        preposition_classes={
            ">XR/": "temporal_700",
            ">L": "temporal_700",
            "B": "temporal_700",
            "BMW": "temporal_700",
            "VRM/": "temporal_700",
            "K": "temporal_700",
            "KMW": "temporal_700",
            "L": "temporal_700",
            "LMW": "temporal_700",
            "<D": "temporal_700",
            "BLT/": "temporal_800",
            "BLTJ/": "temporal_800",
            "ZWLH/": "temporal_800",
            "LM<N": "temporal_800",
            "MN": "temporal_800",
            "J<N/": "causal_900",
            "<L": "causal_900",
            "<QB/": "causal_900",
        },
        infinitive_preposition_classes={
            ">XR/": 1,
            ">L": 2,
            ">YL/": 3,
            ">T": 4,
            "B": 5,
            "BMW": 5,
            "BJN/": 6,
            "BL<DJ": 7,
            "B<D/": 9,
            "ZWLH/": 10,
            "J<N/": 11,
            "K": 12,
            "KMW": 12,
            "L": 14,
            "LMW": 14,
            "LM<N": 15,
            "MN": 17,
            "<D": 20,
            "<L": 21,
            "<M": 22,
            "TXT/": 24,
        },
        relative_lexemes=frozenset({">CR"}),
    )


def render_official_seed_notes() -> str:
    lines = [
        "# ETCBC/BHSA official seed notes",
        "",
        "## Directly grounded in published docs",
        "",
        "- `conjunction_classes`: seeded from the BHSA `code` page examples for coordinate, postulational, conditional, and final opening conjunction classes.",
        "- `preposition_classes`: seeded from the BHSA `code` page examples for temporal/causal opening-preposition classes.",
        "- `infinitive_preposition_classes`: seeded from the BHSA `code` page table for infinitive-construct preposition classes.",
        "- `relative_lexemes`: seeded with `>CR` because the `syn04types` manual lists it among internal lexemes and the BHSA docs tie relative openings to `Rela`/relative clauses.",
        "",
        "## Cautious starter inferences",
        "",
        "- `quote_verbs`: `>MR[`, `DBR[`, `NGD[` are used as verbum-dicendi starter verbs.",
        "- `object_clause_governors`: the starter set adds `JD<[`, `R>H[`, `CM<[` to the speech verbs because these knowledge/perception verbs are listed as program-internal in `syn04types`. This is heuristic, not a recovered ETCBC gold list.",
        "- `subject_clause_governors` and `predicative_clause_governors` are left empty on purpose because the published manuals do not give stable lexeme tables for them.",
        "",
        "## Not seeded",
        "",
        "- No explicit causal conjunction lexemes for class 900, because the published BHSA page shows the class range but does not publish example lexemes for that class.",
        "- No conjunctive-adverb lexeme table for code class 300, because the published docs describe the class but do not expose a canonical lexeme list.",
        "",
    ]
    return "\n".join(lines) + "\n"


def cmd_seed_resources(args: argparse.Namespace) -> None:
    resources = official_etcbc_seed_resources()
    resources.save_json(args.output)
    print(f"saved official ETCBC-style seed to {args.output}")
    if args.md_out:
        Path(args.md_out).write_text(render_official_seed_notes(), encoding="utf-8")
        print(f"saved seed notes to {args.md_out}")


def default_feature_registry() -> tuple[ArgumentFeature, ...]:
    return (
        VSeqFeature(),
        VLexFeature(),
        ParallelOpeningFeature(),
        LexicalParallelFeature(),
        PngAgreementFeature(),
        AsyndeticQuoteFeature(),
        CoordinationFeature(),
        OpeningConjunctionClassFeature(),
        OpeningPrepositionClassFeature(),
        AttributeClauseFeature(),
        ObjectClauseFeature(),
        SubjectClauseFeature(),
        PredicativeClauseFeature(),
        ResumptiveClauseFeature(),
        ReferralVocativeFeature(),
        RegensRectumFeature(),
        DownwardFeature(),
        ExtraposedConstituentFeature(),
        AdjunctClauseFeature(),
    )


def build_generator(
    api: Any,
    resources: ResourceTables | None = None,
    *,
    pool_mode: str = "instruction",
) -> MotherCandidateGenerator:
    ctx = BhsaContext(api, resources=resources)
    extractor = ClauseAtomExtractor(ctx)
    pool_builder = CandidatePoolBuilder(ctx, extractor, mode=pool_mode)
    scorer = EtcBcStyleScorer()
    return MotherCandidateGenerator(
        ctx=ctx,
        extractor=extractor,
        pool_builder=pool_builder,
        features=default_feature_registry(),
        scorer=scorer,
    )


# ---------------------------------------------------------------------------
# CLI helpers
# ---------------------------------------------------------------------------


def parse_books(values: Sequence[str] | None) -> list[str] | None:
    if not values:
        return None
    out: list[str] = []
    for v in values:
        out.extend(part.strip() for part in v.split(",") if part.strip())
    return out or None


def load_resources(path: str | None) -> ResourceTables:
    if path == ":official_seed":
        return official_etcbc_seed_resources()
    if path:
        return ResourceTables.load_json(path)
    return ResourceTables()


def add_common_filter_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--books", nargs="*", help="Limit to one or more book names")
    parser.add_argument("--limit", type=int, help="Maximum number of clause atoms to inspect")
    parser.add_argument("--app", default="ETCBC/bhsa", help="Text-Fabric app name")
    parser.add_argument(
        "--resources",
        help='JSON file with ResourceTables, or :official_seed for the built-in ETCBC-style seed',
    )
    parser.add_argument(
        "--pool-mode",
        default="instruction",
        choices=("instruction", "tab_only"),
        help="Candidate-pool pruning mode",
    )


def cmd_demo(args: argparse.Namespace) -> None:
    api = load_bhsa(args.app)
    resources = load_resources(args.resources)
    generator = build_generator(api, resources=resources, pool_mode=args.pool_mode)
    preds = generator.predict_for_atom(args.atom, top_k=args.top_k)
    if not preds:
        print("No scored candidates")
        return
    print("=" * 80)
    print("daughter", args.atom, generator.ctx.section_of(args.atom), generator.ctx.text_of(args.atom))
    gold = generator.ctx.mother_of(args.atom)
    print("gold mother:", gold)
    for rank, cand in enumerate(preds, start=1):
        labels = ", ".join(ev.label for ev in cand.evidences)
        print(
            f"{rank:>2}. mother={cand.mother:<6} score={cand.score:0.4f} "
            f"rela={cand.predicted_rela or '-':<4} sub2={cand.predicted_sub2} labels=[{labels}]"
        )


def cmd_fit(args: argparse.Namespace) -> None:
    api = load_bhsa(args.app)
    resources = load_resources(args.resources)
    generator = build_generator(api, resources=resources, pool_mode=args.pool_mode)
    learned = fit_resources_from_gold(
        generator,
        books=parse_books(args.books),
        limit=args.limit,
        alpha=args.alpha,
    )
    learned.save_json(args.output)
    print(f"saved weights to {args.output}")


def cmd_eval(args: argparse.Namespace) -> None:
    api = load_bhsa(args.app)
    resources = load_resources(args.resources)
    generator = build_generator(api, resources=resources, pool_mode=args.pool_mode)
    report = evaluate_generator(
        generator,
        books=parse_books(args.books),
        limit=args.limit,
        top_k=args.top_k,
        error_limit=args.error_limit,
    )
    text = json.dumps(report, ensure_ascii=False, indent=2)
    if args.json_out:
        Path(args.json_out).write_text(text, encoding="utf-8")
    else:
        print(text)
    if args.md_out:
        Path(args.md_out).write_text(render_eval_markdown(report, top_k=args.top_k), encoding="utf-8")


def cmd_ablate(args: argparse.Namespace) -> None:
    api = load_bhsa(args.app)
    resources = load_resources(args.resources)
    generator = build_generator(api, resources=resources, pool_mode=args.pool_mode)
    report = ablate_features(
        generator,
        books=parse_books(args.books),
        limit=args.limit,
        top_k=args.top_k,
    )
    text = json.dumps(report, ensure_ascii=False, indent=2)
    if args.json_out:
        Path(args.json_out).write_text(text, encoding="utf-8")
    else:
        print(text)
    if args.md_out:
        Path(args.md_out).write_text(render_ablation_markdown(report), encoding="utf-8")


def cmd_diagnose(args: argparse.Namespace) -> None:
    api = load_bhsa(args.app)
    resources = load_resources(args.resources)
    generator = build_generator(api, resources=resources, pool_mode=args.pool_mode)
    report = diagnose_generator(
        generator,
        books=parse_books(args.books),
        limit=args.limit,
        top_k=args.top_k,
    )
    text = json.dumps(report, ensure_ascii=False, indent=2)
    if args.json_out:
        Path(args.json_out).write_text(text, encoding="utf-8")
    else:
        print(text)
    if args.md_out:
        Path(args.md_out).write_text(render_diagnostic_markdown(report, top_k=args.top_k, top_n=args.top_n), encoding="utf-8")



def cmd_mine(args: argparse.Namespace) -> None:
    api = load_bhsa(args.app)
    resources = load_resources(args.resources)
    generator = build_generator(api, resources=resources, pool_mode=args.pool_mode)
    report = mine_resource_suggestions(
        generator,
        books=parse_books(args.books),
        limit=args.limit,
        min_count=args.min_count,
    )
    text = json.dumps(report, ensure_ascii=False, indent=2)
    if args.json_out:
        Path(args.json_out).write_text(text, encoding="utf-8")
    else:
        print(text)
    if args.md_out:
        Path(args.md_out).write_text(
            render_mining_markdown(report, top_n=args.top_n, include_quote_verbs=args.apply_quote_verbs),
            encoding="utf-8",
        )
    if args.patch_out:
        patched = patch_resources_with_suggestions(resources, report, include_quote_verbs=args.apply_quote_verbs)
        patched.save_json(args.patch_out)


def cmd_export(args: argparse.Namespace) -> None:
    api = load_bhsa(args.app)
    resources = load_resources(args.resources)
    generator = build_generator(api, resources=resources, pool_mode=args.pool_mode)
    export_predictions(
        generator,
        args.output,
        books=parse_books(args.books),
        limit=args.limit,
        top_k=args.top_k,
        fmt=args.format,
    )
    print(f"saved predictions to {args.output}")


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="ETCBC-style BHSA mother-candidate prototype")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_demo = sub.add_parser("demo", help="Show candidate list for one clause_atom")
    add_common_filter_args(p_demo)
    p_demo.add_argument("atom", type=int)
    p_demo.add_argument("--top-k", type=int, default=5)
    p_demo.set_defaults(func=cmd_demo)

    p_fit = sub.add_parser("fit", help="Fit argument weights from gold BHSA mother edges")
    add_common_filter_args(p_fit)
    p_fit.add_argument("output")
    p_fit.add_argument("--alpha", type=float, default=0.5)
    p_fit.set_defaults(func=cmd_fit)

    p_eval = sub.add_parser("eval", help="Evaluate candidate ranking against gold BHSA mother edges")
    add_common_filter_args(p_eval)
    p_eval.add_argument("--top-k", type=int, default=5)
    p_eval.add_argument("--error-limit", type=int, default=25)
    p_eval.add_argument("--json-out")
    p_eval.add_argument("--md-out")
    p_eval.set_defaults(func=cmd_eval)

    p_ablate = sub.add_parser("ablate", help="Run leave-one-feature-out ablation")
    add_common_filter_args(p_ablate)
    p_ablate.add_argument("--top-k", type=int, default=5)
    p_ablate.add_argument("--json-out")
    p_ablate.add_argument("--md-out")
    p_ablate.set_defaults(func=cmd_ablate)

    p_diag = sub.add_parser("diagnose", help="Audit resource coverage and gold-evidence activation")
    add_common_filter_args(p_diag)
    p_diag.add_argument("--top-k", type=int, default=5)
    p_diag.add_argument("--top-n", type=int, default=25)
    p_diag.add_argument("--json-out")
    p_diag.add_argument("--md-out")
    p_diag.set_defaults(func=cmd_diagnose)


    p_mine = sub.add_parser("mine", help="Suggest resource-table additions from uncovered lexemes")
    add_common_filter_args(p_mine)
    p_mine.add_argument("--min-count", type=int, default=2)
    p_mine.add_argument("--top-n", type=int, default=25)
    p_mine.add_argument("--json-out")
    p_mine.add_argument("--md-out")
    p_mine.add_argument("--patch-out")
    p_mine.add_argument(
        "--apply-quote-verbs",
        action="store_true",
        help="Also merge mined quote verbs into patch-out (off by default)",
    )
    p_mine.set_defaults(func=cmd_mine)

    p_export = sub.add_parser("export", help="Export top-k predictions")
    add_common_filter_args(p_export)
    p_export.add_argument("output")
    p_export.add_argument("--top-k", type=int, default=5)
    p_export.add_argument("--format", choices=("json", "jsonl", "csv"), default="jsonl")
    p_export.set_defaults(func=cmd_export)

    p_seed = sub.add_parser("seed-resources", help="Write ETCBC/BHSA starter resource tables")
    p_seed.add_argument("output")
    p_seed.add_argument("--md-out")
    p_seed.set_defaults(func=cmd_seed_resources)

    return parser


def main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
