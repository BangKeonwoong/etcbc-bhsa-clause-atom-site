from __future__ import annotations

import argparse
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


def load_bhsa(app_name: str = "ETCBC/bhsa") -> Any:
    """Return a Text-Fabric API object for BHSA.

    Example
    -------
    >>> api = load_bhsa()
    >>> F, E, L, T = api.F, api.E, api.L, api.T
    """
    from tf.app import use

    A = use(app_name)
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
        seen: list[str] = []
        for p in self.phrases:
            seen.extend(p.lexemes)
        return tuple(seen)

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
    """External knowledge replacing ETCBC library tables.

    Populate these from JSON/TSV assets that you maintain separately.
    """

    arg_weights: Mapping[str, ArgWeight] = field(default_factory=dict)
    quote_verbs: frozenset[str] = field(default_factory=frozenset)
    object_clause_governors: frozenset[str] = field(default_factory=frozenset)
    subject_clause_governors: frozenset[str] = field(default_factory=frozenset)
    predicative_clause_governors: frozenset[str] = field(default_factory=frozenset)
    conjunction_classes: Mapping[str, str] = field(default_factory=dict)
    preposition_classes: Mapping[str, str] = field(default_factory=dict)
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
            "relative_lexemes": sorted(self.relative_lexemes),
        }

    def save_json(self, path: str | Path) -> None:
        Path(path).write_text(json.dumps(self.to_json_dict(), ensure_ascii=False, indent=2), encoding="utf-8")

    @classmethod
    def from_json_dict(cls, data: Mapping[str, Any]) -> "ResourceTables":
        arg_weights = {
            k: ArgWeight(**v) if not isinstance(v, ArgWeight) else v
            for (k, v) in dict(data.get("arg_weights", {})).items()
        }
        return cls(
            arg_weights=arg_weights,
            quote_verbs=frozenset(data.get("quote_verbs", [])),
            object_clause_governors=frozenset(data.get("object_clause_governors", [])),
            subject_clause_governors=frozenset(data.get("subject_clause_governors", [])),
            predicative_clause_governors=frozenset(data.get("predicative_clause_governors", [])),
            conjunction_classes=dict(data.get("conjunction_classes", {})),
            preposition_classes=dict(data.get("preposition_classes", {})),
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
        self._atom_index = {n: i for i, n in enumerate(self._clause_atoms)}

    @property
    def clause_atoms(self) -> tuple[int, ...]:
        return self._clause_atoms

    def atom_pos(self, clause_atom: int) -> int:
        return self._atom_index[clause_atom]

    def atom_distance(self, a: int, b: int) -> int:
        return self.atom_pos(a) - self.atom_pos(b)

    def first_slot(self, node: int) -> int:
        return min(self.E.oslots.s(node))

    def last_slot(self, node: int) -> int:
        return max(self.E.oslots.s(node))

    def words_of(self, node: int) -> tuple[int, ...]:
        return tuple(self.E.oslots.s(node))

    def text_of(self, node: int) -> str:
        return self.T.text(node)

    def section_of(self, node: int) -> Any:
        return self.T.sectionFromNode(node)

    def clause_of_atom(self, clause_atom: int) -> int | None:
        up = tuple(self.L.u(clause_atom, otype="clause"))
        return up[0] if up else None

    def mother_of(self, node: int) -> int | None:
        moms = tuple(self.E.mother.f(node) or ())
        return moms[0] if moms else None

    def prev_atom(self, node: int) -> int | None:
        i = self._atom_index[node]
        return self._clause_atoms[i - 1] if i > 0 else None

    def next_atom(self, node: int) -> int | None:
        i = self._atom_index[node]
        return self._clause_atoms[i + 1] if i + 1 < len(self._clause_atoms) else None

    def atoms_between(self, left: int, right: int) -> tuple[int, ...]:
        i = self._atom_index[left]
        j = self._atom_index[right]
        if i <= j:
            return self._clause_atoms[i : j + 1]
        return self._clause_atoms[j : i + 1]


# ---------------------------------------------------------------------------
# Clause-atom view extraction
# ---------------------------------------------------------------------------


PREDICATE_FUNCTIONS = {"Pred", "PreS", "PreO", "PtcO", "PrcS", "PreC", "PrAd"}
SUBJECT_FUNCTIONS = {"Subj"}
QUESTION_FUNCTIONS = {"Ques"}
NEGATION_FUNCTIONS = {"Nega"}
VOCATIVE_FUNCTIONS = {"Voct"}
FRONTING_FUNCTIONS = {"Frnt"}
OPENING_FUNCTIONS = {"Conj", "Ques", "Nega", "Intj", "Frnt", "Rela"}
NP_LIKE_TYPES = {"NP", "PrNP", "PPrP", "DPrP", "IPrP"}
COORD_CONJ_LEXEMES = {"W", "W[", ">W", ">W["}
FINITE_VT = {"impf", "perf", "impv", "wayq", "weyq"}
NONFINITE_VT = {"infc", "infa", "ptcp", "ptca"}
XLIKE_CTYPES = {
    "XImp",
    "XYqt",
    "XQtl",
    "XPos",
    "InfC",
    "InfA",
    "Ptcp",
    "WXQt",
    "WXYq",
    "WayX",
}


class ClauseAtomExtractor:
    def __init__(self, ctx: BhsaContext) -> None:
        self.ctx = ctx

    @lru_cache(maxsize=32768)
    def extract(self, clause_atom: int) -> ClauseAtomView:
        ctx = self.ctx
        F = ctx.F

        first_slot = ctx.first_slot(clause_atom)
        last_slot = ctx.last_slot(clause_atom)
        clause = ctx.clause_of_atom(clause_atom)
        txt = F.txt.v(clause) if clause else None
        instruction = (F.instruction.v(clause_atom) or "..")[:2].ljust(2, ".")
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
            opening = self._opening_prefix(phrases, predicate_idx)
            preverbal = tuple(phrases[:predicate_idx])
            predicate_phrase = phrases[predicate_idx]
            postverbal = tuple(phrases[predicate_idx + 1 :])

        predicate = self._predicate_info(predicate_phrase)
        opening_lexs = self._opening_conjunction_lexemes(opening)
        opening_preps = self._opening_preposition_lexemes(opening)
        explicit_subject = any((p.function in SUBJECT_FUNCTIONS) for p in phrases)
        has_fronting = any((p.function in FRONTING_FUNCTIONS) for p in phrases)
        has_vocative = any((p.function in VOCATIVE_FUNCTIONS) for p in phrases)
        relative_marker = self._has_relative_marker(opening)
        quote_verb = bool(predicate and predicate.lex in ctx.resources.quote_verbs)
        question_marked = any((p.function in QUESTION_FUNCTIONS) for p in phrases)
        coord = self._coordinating_conjunction(opening_lexs)
        subord = any((p.function == "Conj") for p in opening)

        return ClauseAtomView(
            node=clause_atom,
            clause=clause,
            first_slot=first_slot,
            last_slot=last_slot,
            tab=int(F.tab.v(clause_atom) or 0),
            pargr=F.pargr.v(clause_atom),
            instruction=instruction,
            sub1=sub1,
            sub2=sub2,
            typ=F.typ.v(clause_atom),
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
            coordinating_conjunction=coord,
            subordinating_conjunction=subord,
        )

    def _phrase_nodes_of_atom(self, clause_atom: int) -> tuple[int, ...]:
        ctx = self.ctx
        first_slot = ctx.first_slot(clause_atom)
        last_slot = ctx.last_slot(clause_atom)
        candidates = tuple(ctx.L.d(clause_atom, otype="phrase"))
        selected = []
        for p in candidates:
            pf = ctx.first_slot(p)
            pl = ctx.last_slot(p)
            if pf >= first_slot and pl <= last_slot:
                selected.append(p)
        selected.sort(key=ctx.first_slot)
        return tuple(selected)

    def _phrase_info(self, phrase: int) -> PhraseInfo:
        ctx = self.ctx
        F = ctx.F
        words = ctx.words_of(phrase)
        lexemes = tuple(F.lex.v(w) for w in words if F.lex.v(w))
        return PhraseInfo(
            node=phrase,
            first_slot=ctx.first_slot(phrase),
            last_slot=ctx.last_slot(phrase),
            function=F.function.v(phrase),
            typ=F.typ.v(phrase),
            text=ctx.text_of(phrase),
            lexemes=lexemes,
        )

    def _predicate_index(self, phrases: Sequence[PhraseInfo]) -> int | None:
        for i, p in enumerate(phrases):
            if p.function in PREDICATE_FUNCTIONS or p.typ == "VP":
                return i
        return None

    def _opening_prefix(self, phrases: Sequence[PhraseInfo], predicate_idx: int) -> tuple[PhraseInfo, ...]:
        prefix: list[PhraseInfo] = []
        for p in phrases[:predicate_idx]:
            prefix.append(p)
        return tuple(prefix)

    def _predicate_info(self, predicate_phrase: PhraseInfo | None) -> PredicateInfo | None:
        if predicate_phrase is None:
            return None
        ctx = self.ctx
        F = ctx.F
        for w in ctx.words_of(predicate_phrase.node):
            if F.vt.v(w) not in (None, "NA") or F.vs.v(w) not in (None, "NA"):
                return PredicateInfo(
                    lex=F.lex.v(w),
                    vt=F.vt.v(w),
                    vs=F.vs.v(w),
                    ps=F.ps.v(w),
                    nu=F.nu.v(w),
                    gn=F.gn.v(w),
                    prs=F.prs.v(w),
                    prs_ps=F.prs_ps.v(w),
                    prs_nu=F.prs_nu.v(w),
                    prs_gn=F.prs_gn.v(w),
                )
        # fallback: first word in predicate phrase
        w = ctx.words_of(predicate_phrase.node)[0]
        return PredicateInfo(
            lex=F.lex.v(w),
            vt=F.vt.v(w),
            vs=F.vs.v(w),
            ps=F.ps.v(w),
            nu=F.nu.v(w),
            gn=F.gn.v(w),
            prs=F.prs.v(w),
            prs_ps=F.prs_ps.v(w),
            prs_nu=F.prs_nu.v(w),
            prs_gn=F.prs_gn.v(w),
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
            if p.typ == "PP":
                lexs.extend(p.lexemes[:1])
        return tuple(lexs)

    def _has_relative_marker(self, opening: Sequence[PhraseInfo]) -> bool:
        resource_relatives = self.ctx.resources.relative_lexemes
        for p in opening:
            if p.function == "Rela":
                return True
            if resource_relatives and any(lex in resource_relatives for lex in p.lexemes):
                return True
        return False

    def _coordinating_conjunction(self, lexs: Sequence[str]) -> bool:
        if any(lex in COORD_CONJ_LEXEMES for lex in lexs):
            return True
        classes = self.ctx.resources.conjunction_classes
        if classes:
            return any(classes.get(lex) == "Coor" for lex in lexs)
        return False


# ---------------------------------------------------------------------------
# Candidate pool (ETCBC-compatible reconstruction)
# ---------------------------------------------------------------------------


class CandidatePoolBuilder:
    def __init__(self, ctx: BhsaContext, extractor: ClauseAtomExtractor) -> None:
        self.ctx = ctx
        self.extractor = extractor

    def build(self, daughter: int) -> tuple[int, ...]:
        atoms = self.ctx.clause_atoms
        pos = self.ctx.atom_pos(daughter)
        pool: list[int] = []

        # left scan
        t = 10_000
        for i in range(pos - 1, -1, -1):
            m = atoms[i]
            m_view = self.extractor.extract(m)
            if m_view.tab <= t and m_view.sub2 != "e":
                pool.append(m)
                t = m_view.tab - 1
                if t < 0 or m_view.sub2 == "\\":
                    break

        # right scan
        t = 10_000
        for i in range(pos + 1, len(atoms)):
            m = atoms[i]
            m_view = self.extractor.extract(m)
            if m_view.tab <= t and m_view.sub2 != "e":
                pool.append(m)
                t = m_view.tab - 1
                if t < 0 or m_view.sub2 != "\\":
                    break

        return tuple(pool)


# ---------------------------------------------------------------------------
# Argument features
# ---------------------------------------------------------------------------


class ArgumentFeature(Protocol):
    def extract(
        self,
        daughter: ClauseAtomView,
        mother: ClauseAtomView,
        ctx: BhsaContext,
    ) -> Sequence[Evidence]:
        ...


def evidence_from_label(
    ctx: BhsaContext,
    label: str,
    *,
    default_weight: float = 0.0,
    default_mean_distance: float | None = None,
    default_par: float = 0.0,
    default_quo: float = 0.0,
    payload: Mapping[str, Any] | None = None,
) -> Evidence:
    aw = ctx.resources.arg_weights.get(label)
    if aw is None:
        return Evidence(
            label=label,
            weight=default_weight,
            mean_distance=default_mean_distance,
            par=default_par,
            quo=default_quo,
            payload=payload or {},
        )
    return Evidence(
        label=label,
        weight=aw.weight,
        mean_distance=aw.mean_distance,
        par=max(default_par, aw.par),
        quo=max(default_quo, aw.quo),
        freq=aw.freq,
        payload=payload or {},
    )


class VSeqFeature:
    def extract(self, daughter: ClauseAtomView, mother: ClauseAtomView, ctx: BhsaContext) -> Sequence[Evidence]:
        dvt = daughter.predicate.vt if daughter.predicate else None
        mvt = mother.predicate.vt if mother.predicate else None
        if dvt and mvt and dvt == mvt:
            return [evidence_from_label(ctx, "VBT")]
        if daughter.typ and mother.typ:
            label = f"{daughter.typ}<<{mother.typ}"
            return [evidence_from_label(ctx, label)]
        return []


class VLexFeature:
    def extract(self, daughter: ClauseAtomView, mother: ClauseAtomView, ctx: BhsaContext) -> Sequence[Evidence]:
        dlex = daughter.predicate.lex if daughter.predicate else None
        mlex = mother.predicate.lex if mother.predicate else None
        if dlex and mlex and dlex == mlex:
            return [evidence_from_label(ctx, "VLEX")]
        return []


class ParallelOpeningFeature:
    """ETCBC-style parallel opening approximation.

    Official code rules require subject-presence agreement and equivalent
    phrases up to the predicate, with same `typ` if a predicate is absent.
    """

    def extract(self, daughter: ClauseAtomView, mother: ClauseAtomView, ctx: BhsaContext) -> Sequence[Evidence]:
        if daughter.explicit_subject != mother.explicit_subject:
            return []

        if daughter.predicate is None or mother.predicate is None:
            if daughter.typ == mother.typ:
                return [evidence_from_label(ctx, "PAR_TYP", default_par=1.0)]
            return []

        d_sig = daughter.opening_signature(False)
        m_sig = mother.opening_signature(False)
        if d_sig == m_sig:
            return [evidence_from_label(ctx, "PAR_OPEN", default_par=1.0)]
        if daughter.opening_signature(True) == mother.opening_signature(True):
            return [evidence_from_label(ctx, "PAR_OPEN_NOCOOR", default_par=1.0)]
        if self._prefix_of(d_sig, m_sig) or self._prefix_of(m_sig, d_sig):
            return [evidence_from_label(ctx, "PAR_OPEN_PREFIX", default_par=1.0)]
        return []

    @staticmethod
    def _prefix_of(left: Sequence[Any], right: Sequence[Any]) -> bool:
        if len(left) > len(right):
            return False
        return tuple(left) == tuple(right[: len(left)])


class AsyndeticQuoteFeature:
    def extract(self, daughter: ClauseAtomView, mother: ClauseAtomView, ctx: BhsaContext) -> Sequence[Evidence]:
        if ctx.next_atom(mother.node) != daughter.node:
            return []
        if mother.quote_verb and not daughter.subordinating_conjunction:
            return [evidence_from_label(ctx, "ASYNQ", default_quo=1.0)]
        return []


class PngAgreementFeature:
    def extract(self, daughter: ClauseAtomView, mother: ClauseAtomView, ctx: BhsaContext) -> Sequence[Evidence]:
        out: list[Evidence] = []
        dp = daughter.predicate
        mp = mother.predicate
        if not dp or not mp:
            return out

        if self._clean_png(dp.png) == self._clean_png(mp.png):
            out.append(evidence_from_label(ctx, "PNG<<PNG"))
        if self._clean_png(dp.suffix_png) == self._clean_png(mp.png):
            out.append(evidence_from_label(ctx, "SFX<<PNG"))
        if self._clean_png(dp.png) == self._clean_png(mp.suffix_png):
            out.append(evidence_from_label(ctx, "PNG<<SFX"))
        return out

    @staticmethod
    def _clean_png(png: tuple[str | None, str | None, str | None]) -> tuple[str | None, str | None, str | None] | None:
        if all(x in (None, "NA", "unknown") for x in png):
            return None
        return png


class ObjectClauseFeature:
    """Governor-based approximation of ETCBC Objc argument."""

    def extract(self, daughter: ClauseAtomView, mother: ClauseAtomView, ctx: BhsaContext) -> Sequence[Evidence]:
        mp = mother.predicate
        if not mp or mp.lex not in ctx.resources.object_clause_governors:
            return []
        if ctx.atom_distance(daughter.node, mother.node) <= 0:
            return []
        if daughter.subordinating_conjunction or daughter.question_marked or daughter.predicate is not None:
            return [evidence_from_label(ctx, "OBJC")]
        return []


class PredicativeClauseFeature:
    def extract(self, daughter: ClauseAtomView, mother: ClauseAtomView, ctx: BhsaContext) -> Sequence[Evidence]:
        if ctx.next_atom(mother.node) != daughter.node:
            return []
        if daughter.subordinating_conjunction:
            return []
        mp = mother.predicate
        if mp and mp.lex in ctx.resources.predicative_clause_governors:
            return [evidence_from_label(ctx, "PREC")]
        m_funcs = {p.function for p in mother.phrases}
        if "Subj" in m_funcs and not m_funcs.intersection(PREDICATE_FUNCTIONS):
            return [evidence_from_label(ctx, "PREC")]
        return []


class AttributiveClauseFeature:
    def extract(self, daughter: ClauseAtomView, mother: ClauseAtomView, ctx: BhsaContext) -> Sequence[Evidence]:
        if ctx.atom_distance(daughter.node, mother.node) <= 0:
            return []
        if not daughter.relative_marker:
            return []
        nominal_anchor = any((p.typ in NP_LIKE_TYPES) for p in mother.phrases) or mother.explicit_subject
        if not nominal_anchor:
            return []
        if ctx.next_atom(mother.node) == daughter.node or daughter.subordinating_conjunction:
            return [evidence_from_label(ctx, "ATTR")]
        return []


class SubjectClauseFeature:
    def extract(self, daughter: ClauseAtomView, mother: ClauseAtomView, ctx: BhsaContext) -> Sequence[Evidence]:
        if ctx.atom_distance(daughter.node, mother.node) <= 0:
            return []
        mp = mother.predicate
        if mp and mp.lex in ctx.resources.subject_clause_governors and daughter.subordinating_conjunction:
            return [evidence_from_label(ctx, "SUBJ")]
        if not mother.explicit_subject and daughter.subordinating_conjunction and daughter.typ in {"NmCl", "InfC", "Ptcp"}:
            return [evidence_from_label(ctx, "SUBJ")]
        return []


class ResumptiveClauseFeature:
    def extract(self, daughter: ClauseAtomView, mother: ClauseAtomView, ctx: BhsaContext) -> Sequence[Evidence]:
        if ctx.atom_distance(daughter.node, mother.node) <= 0:
            return []
        if not (mother.has_fronting or mother.sub1 == "c"):
            return []
        daughter_pron = any((p.typ in {"PPrP", "DPrP"}) for p in daughter.preverbal_phrases)
        daughter_suffix = bool(daughter.predicate and any(x not in (None, "NA") for x in daughter.predicate.suffix_png))
        if daughter_pron or daughter_suffix:
            return [evidence_from_label(ctx, "RESU")]
        return []


class ReferralToVocativeFeature:
    def extract(self, daughter: ClauseAtomView, mother: ClauseAtomView, ctx: BhsaContext) -> Sequence[Evidence]:
        if ctx.atom_distance(daughter.node, mother.node) <= 0:
            return []
        if not (mother.has_vocative or mother.sub1 == "v"):
            return []
        dp = daughter.predicate
        second_person = bool(dp and dp.ps in {"p2", "2", "2p", "2s"})
        if second_person or any((p.typ == "PPrP") for p in daughter.preverbal_phrases):
            return [evidence_from_label(ctx, "REVO")]
        return []


class RegensRectumFeature:
    def extract(self, daughter: ClauseAtomView, mother: ClauseAtomView, ctx: BhsaContext) -> Sequence[Evidence]:
        if ctx.atom_distance(daughter.node, mother.node) <= 0:
            return []
        dvt = (daughter.predicate.vt or "").lower() if daughter.predicate else ""
        if daughter.typ in {"InfC", "InfA"} or dvt in {"infc", "infa"}:
            if daughter.opening_preposition_lexemes or daughter.subordinating_conjunction:
                return [evidence_from_label(ctx, "RGRC")]
        return []


class DownwardFeature:
    """Approximate ETCBC `DOWN`.

    Source comments say downward daughters do not have a coordinating
    conjunction and typically show x-clause or infinitive/participle types.
    """

    def extract(self, daughter: ClauseAtomView, mother: ClauseAtomView, ctx: BhsaContext) -> Sequence[Evidence]:
        if ctx.atom_distance(daughter.node, mother.node) >= 0:
            return []
        if daughter.coordinating_conjunction:
            return []
        dvt = (daughter.predicate.vt or "").lower() if daughter.predicate else ""
        dtype = daughter.typ or ""
        xlike = dtype in XLIKE_CTYPES or dtype.startswith("X") or dtype.startswith("x")
        if xlike or dvt in NONFINITE_VT or daughter.predicate is None:
            return [evidence_from_label(ctx, "DOWN")]
        return []


class ExtraposedConstituentFeature:
    """Approximate ETCBC `XPOS`.

    Roughly follows the source condition: a single non-predicative constituent
    preceding the mother and lacking a corresponding constituent in the mother.
    """

    def extract(self, daughter: ClauseAtomView, mother: ClauseAtomView, ctx: BhsaContext) -> Sequence[Evidence]:
        if ctx.atom_distance(daughter.node, mother.node) >= 0:
            return []
        if len(daughter.phrases) != 1:
            return []
        if daughter.predicate is not None:
            return []
        p = daughter.phrases[0]
        if p.function in PREDICATE_FUNCTIONS or p.function == "PreC":
            return []
        if p.typ not in NP_LIKE_TYPES | {"PP", "AdvP", "AdjP"}:
            return []
        if mother.subordinating_conjunction or mother.predicate is None:
            return []
        if any((mp.function == p.function) for mp in mother.phrases):
            return []
        return [evidence_from_label(ctx, "XPOS")]


class AdjunctClauseFeature:
    def extract(self, daughter: ClauseAtomView, mother: ClauseAtomView, ctx: BhsaContext) -> Sequence[Evidence]:
        if ctx.atom_distance(daughter.node, mother.node) <= 0:
            return []
        if daughter.opening_preposition_lexemes:
            return [evidence_from_label(ctx, "ADJU")]
        first = daughter.first_phrase()
        if first and first.function in {"Adju", "PrAd", "Loca"}:
            return [evidence_from_label(ctx, "ADJU")]
        return []


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------


class EtcBcStyleScorer:
    def __init__(self, ctx: BhsaContext) -> None:
        self.ctx = ctx
        self._phi = NormalDist().cdf

    def score(
        self,
        daughter: ClauseAtomView,
        mother: ClauseAtomView,
        evidences: Sequence[Evidence],
    ) -> tuple[float, bool, bool]:
        if not evidences:
            return (0.0, False, False)

        distance = abs(self.ctx.atom_distance(daughter.node, mother.node))
        value_raw = sum(ev.weight for ev in evidences)
        value_score = self._phi(value_raw)

        d_terms = [self._logprob(ev.mean_distance, distance) for ev in evidences if ev.mean_distance and ev.mean_distance >= 1]
        if d_terms:
            distance_score = exp((85 / 834) * sum(d_terms) / len(d_terms))
        else:
            distance_score = 1.0

        # ETCBC-compatible directional shunt: a rightward mother requires
        # constituent-clause or downward / extraposed evidence.
        rightward = self.ctx.atom_distance(daughter.node, mother.node) < 0
        if rightward and not any(ev.label in {"DOWN", "XPOS", "OBJC", "PREC", "SUBJ", "RGRC"} for ev in evidences):
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


CCR_LABELS = {
    "ADJU": "Adju",
    "ATTR": "Attr",
    "OBJC": "Objc",
    "PREC": "PreC",
    "SUBJ": "Subj",
    "RESU": "Resu",
    "REVO": "ReVo",
    "RGRC": "RgRc",
}


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

    def predict_for_atom(self, daughter_atom: int, top_k: int = 5) -> list[Candidate]:
        d_view = self.extractor.extract(daughter_atom)
        candidates: list[Candidate] = []

        for mother_atom in self.pool_builder.build(daughter_atom):
            m_view = self.extractor.extract(mother_atom)
            evidences = self._collect_evidence(d_view, m_view)
            score, parallel, quotation = self.scorer.score(d_view, m_view, evidences)
            if score <= 0:
                continue
            candidates.append(
                Candidate(
                    daughter=daughter_atom,
                    mother=mother_atom,
                    score=score,
                    evidences=tuple(sorted(evidences, key=lambda e: e.weight, reverse=True)),
                    predicted_sub1=self._predict_sub1(d_view, evidences),
                    predicted_sub2=self._predict_sub2(d_view, m_view, evidences, quotation),
                    predicted_rela=self._predict_rela(evidences, parallel),
                    predicted_typ=self._predict_typ(d_view, evidences),
                    parallel=parallel,
                    quotation=quotation,
                )
            )

        candidates.sort(key=lambda c: c.score, reverse=True)
        return candidates[:top_k]

    def _collect_evidence(self, daughter: ClauseAtomView, mother: ClauseAtomView) -> list[Evidence]:
        out: list[Evidence] = []
        for feat in self.features:
            out.extend(feat.extract(daughter, mother, self.ctx))
        return out

    def _predict_sub1(self, daughter: ClauseAtomView, evidences: Sequence[Evidence]) -> str:
        labels = {ev.label for ev in evidences}
        if daughter.has_vocative:
            return "v"
        if "XPOS" in labels:
            return "x"
        if daughter.has_fronting:
            return "c"
        if daughter.predicate is None and not daughter.explicit_subject:
            return "d"
        return daughter.sub1

    def _predict_sub2(
        self,
        daughter: ClauseAtomView,
        mother: ClauseAtomView,
        evidences: Sequence[Evidence],
        quotation: bool,
    ) -> str:
        labels = {ev.label for ev in evidences}
        if quotation:
            return "q"
        if self.ctx.atom_distance(daughter.node, mother.node) < 0 and ("DOWN" in labels or "XPOS" in labels):
            return "\\"
        return daughter.sub2

    def _predict_rela(self, evidences: Sequence[Evidence], parallel: bool) -> str | None:
        best: tuple[float, str] | None = None
        for ev in evidences:
            ccr = CCR_LABELS.get(ev.label)
            if ccr is None:
                continue
            score = abs(ev.weight) if ev.weight else 0.001
            if best is None or score > best[0]:
                best = (score, ccr)
        if best:
            return best[1]
        if parallel:
            return "Coor"
        return None

    def _predict_typ(self, daughter: ClauseAtomView, evidences: Sequence[Evidence]) -> str | None:
        labels = {ev.label for ev in evidences}
        if "XPOS" in labels:
            return "XPos"
        if daughter.predicate is None and daughter.explicit_subject:
            return daughter.typ or "NmCl"
        return daughter.typ


# ---------------------------------------------------------------------------
# Training data
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PairwiseTrainingRow:
    daughter: int
    mother: int
    y: int
    distance: int
    labels: tuple[str, ...]
    section: Any


class TrainingBuilder:
    def __init__(self, ctx: BhsaContext, generator: MotherCandidateGenerator) -> None:
        self.ctx = ctx
        self.generator = generator

    def build_rows(
        self,
        *,
        skip_without_gold: bool = True,
        limit: int | None = None,
    ) -> Iterator[PairwiseTrainingRow]:
        seen = 0
        for daughter in self.ctx.clause_atoms:
            gold = self.ctx.mother_of(daughter)
            if skip_without_gold and gold is None:
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
                    labels=tuple(ev.label for ev in evidences),
                    section=self.ctx.section_of(daughter),
                )
            seen += 1
            if limit is not None and seen >= limit:
                return


# ---------------------------------------------------------------------------
# Weight fitting
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class WeightFitSummary:
    total_positive: int
    total_negative: int
    labels_considered: int
    method: str


class LogOddsWeightEstimator:
    def fit(
        self,
        rows: Iterable[PairwiseTrainingRow],
        *,
        alpha: float = 0.5,
        min_freq: int = 2,
    ) -> tuple[dict[str, ArgWeight], WeightFitSummary]:
        pos_total = 0
        neg_total = 0
        pos_with: Counter[str] = Counter()
        neg_with: Counter[str] = Counter()
        dist_sum: Counter[str] = Counter()

        for row in rows:
            labels = set(row.labels)
            if row.y:
                pos_total += 1
                for label in labels:
                    pos_with[label] += 1
                    dist_sum[label] += row.distance
            else:
                neg_total += 1
                for label in labels:
                    neg_with[label] += 1

        labels_seen = set(pos_with) | set(neg_with)
        fitted: dict[str, ArgWeight] = {}
        for label in sorted(labels_seen):
            freq = pos_with[label]
            if freq < min_freq:
                continue
            a = pos_with[label] + alpha
            b = max(pos_total - pos_with[label], 0) + alpha
            c = neg_with[label] + alpha
            d = max(neg_total - neg_with[label], 0) + alpha
            weight = log(a / b) - log(c / d)
            mean_distance = (dist_sum[label] / pos_with[label]) if pos_with[label] else None
            fitted[label] = ArgWeight(
                label=label,
                weight=float(weight),
                mean_distance=float(mean_distance) if mean_distance is not None else None,
                par=1.0 if label.startswith("PAR_") else 0.0,
                quo=1.0 if label == "ASYNQ" else 0.0,
                freq=freq,
            )

        summary = WeightFitSummary(
            total_positive=pos_total,
            total_negative=neg_total,
            labels_considered=len(fitted),
            method="log_odds",
        )
        return fitted, summary


class LogisticWeightEstimator:
    def fit(
        self,
        rows: Iterable[PairwiseTrainingRow],
        *,
        min_freq: int = 2,
        max_iter: int = 2000,
        c_value: float = 1.0,
    ) -> tuple[dict[str, ArgWeight], WeightFitSummary]:
        from sklearn.feature_extraction import DictVectorizer
        from sklearn.linear_model import LogisticRegression

        prepared: list[PairwiseTrainingRow] = list(rows)
        pos_with: Counter[str] = Counter()
        dist_sum: Counter[str] = Counter()
        neg_with: Counter[str] = Counter()
        xs: list[dict[str, int]] = []
        ys: list[int] = []

        for row in prepared:
            labels = set(row.labels)
            xs.append({f"lab={label}": 1 for label in labels})
            ys.append(row.y)
            if row.y:
                for label in labels:
                    pos_with[label] += 1
                    dist_sum[label] += row.distance
            else:
                for label in labels:
                    neg_with[label] += 1

        vec = DictVectorizer(sparse=True)
        X = vec.fit_transform(xs)
        clf = LogisticRegression(max_iter=max_iter, solver="liblinear", class_weight="balanced", C=c_value)
        clf.fit(X, ys)

        fitted: dict[str, ArgWeight] = {}
        for feat_name, coef in zip(vec.feature_names_, clf.coef_[0]):
            if not feat_name.startswith("lab="):
                continue
            label = feat_name[4:]
            freq = pos_with[label]
            if freq < min_freq:
                continue
            mean_distance = (dist_sum[label] / pos_with[label]) if pos_with[label] else None
            fitted[label] = ArgWeight(
                label=label,
                weight=float(coef),
                mean_distance=float(mean_distance) if mean_distance is not None else None,
                par=1.0 if label.startswith("PAR_") else 0.0,
                quo=1.0 if label == "ASYNQ" else 0.0,
                freq=freq,
            )

        summary = WeightFitSummary(
            total_positive=sum(ys),
            total_negative=len(ys) - sum(ys),
            labels_considered=len(fitted),
            method="logistic",
        )
        return fitted, summary


# ---------------------------------------------------------------------------
# Recommended registry and bootstrap
# ---------------------------------------------------------------------------


def default_feature_registry() -> tuple[ArgumentFeature, ...]:
    return (
        VSeqFeature(),
        VLexFeature(),
        ParallelOpeningFeature(),
        PngAgreementFeature(),
        AsyndeticQuoteFeature(),
        AdjunctClauseFeature(),
        AttributiveClauseFeature(),
        ObjectClauseFeature(),
        PredicativeClauseFeature(),
        SubjectClauseFeature(),
        ResumptiveClauseFeature(),
        ReferralToVocativeFeature(),
        RegensRectumFeature(),
        DownwardFeature(),
        ExtraposedConstituentFeature(),
    )


def build_generator(api: Any, resources: ResourceTables | None = None) -> MotherCandidateGenerator:
    ctx = BhsaContext(api, resources=resources)
    extractor = ClauseAtomExtractor(ctx)
    pool_builder = CandidatePoolBuilder(ctx, extractor)
    scorer = EtcBcStyleScorer(ctx)
    return MotherCandidateGenerator(
        ctx=ctx,
        extractor=extractor,
        pool_builder=pool_builder,
        features=default_feature_registry(),
        scorer=scorer,
    )


def fit_resources_from_gold(
    api: Any,
    base_resources: ResourceTables | None = None,
    *,
    method: str = "log_odds",
    limit: int | None = None,
    min_freq: int = 2,
) -> tuple[ResourceTables, WeightFitSummary]:
    resources = base_resources or ResourceTables()
    generator = build_generator(api, resources=resources)
    rows = TrainingBuilder(generator.ctx, generator).build_rows(limit=limit)
    if method == "logistic":
        fitted, summary = LogisticWeightEstimator().fit(rows, min_freq=min_freq)
    else:
        fitted, summary = LogOddsWeightEstimator().fit(rows, min_freq=min_freq)

    merged = ResourceTables(
        arg_weights=fitted,
        quote_verbs=resources.quote_verbs,
        object_clause_governors=resources.object_clause_governors,
        subject_clause_governors=resources.subject_clause_governors,
        predicative_clause_governors=resources.predicative_clause_governors,
        conjunction_classes=resources.conjunction_classes,
        preposition_classes=resources.preposition_classes,
        relative_lexemes=resources.relative_lexemes,
    )
    return merged, summary


# ---------------------------------------------------------------------------
# CLI helpers
# ---------------------------------------------------------------------------


def _demo(args: argparse.Namespace) -> None:
    api = load_bhsa(args.app)
    resources = ResourceTables.load_json(args.resources) if args.resources else ResourceTables()
    generator = build_generator(api, resources=resources)
    preds = generator.predict_for_atom(args.daughter, top_k=args.top_k)
    if not preds:
        print("No candidates")
        return
    print("daughter", args.daughter, generator.ctx.section_of(args.daughter), generator.ctx.text_of(args.daughter))
    for cand in preds:
        labels = ", ".join(ev.label for ev in cand.evidences)
        print(
            f"mother={cand.mother:<7} score={cand.score:0.4f} sub={cand.predicted_sub1}{cand.predicted_sub2} "
            f"rela={cand.predicted_rela or '-'} typ={cand.predicted_typ or '-'} labels=[{labels}]"
        )


def _fit(args: argparse.Namespace) -> None:
    api = load_bhsa(args.app)
    resources = ResourceTables.load_json(args.resources) if args.resources else ResourceTables()
    fitted, summary = fit_resources_from_gold(
        api,
        base_resources=resources,
        method=args.method,
        limit=args.limit,
        min_freq=args.min_freq,
    )
    fitted.save_json(args.out)
    print(json.dumps(asdict(summary), ensure_ascii=False, indent=2))
    print(f"saved -> {args.out}")


# ---------------------------------------------------------------------------
# Example usage
# ---------------------------------------------------------------------------


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ETCBC-style BHSA mother candidate generator skeleton")
    sub = parser.add_subparsers(dest="cmd", required=False)

    p_demo = sub.add_parser("demo", help="show top-k candidates for one clause_atom")
    p_demo.add_argument("daughter", type=int)
    p_demo.add_argument("--app", default="ETCBC/bhsa")
    p_demo.add_argument("--resources")
    p_demo.add_argument("--top-k", type=int, default=5)
    p_demo.set_defaults(func=_demo)

    p_fit = sub.add_parser("fit", help="fit argument weights from BHSA mother gold")
    p_fit.add_argument("out")
    p_fit.add_argument("--app", default="ETCBC/bhsa")
    p_fit.add_argument("--resources")
    p_fit.add_argument("--method", choices={"log_odds", "logistic"}, default="log_odds")
    p_fit.add_argument("--limit", type=int)
    p_fit.add_argument("--min-freq", type=int, default=2)
    p_fit.set_defaults(func=_fit)

    args = parser.parse_args()
    if getattr(args, "func", None) is None:
        parser.print_help()
    else:
        args.func(args)
