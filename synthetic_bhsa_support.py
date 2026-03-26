from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any, Mapping, Sequence


class FakeFeature:
    def __init__(self, values: Mapping[int, Any] | None = None, by_type: Mapping[str, Sequence[int]] | None = None) -> None:
        self.values = dict(values or {})
        self.by_type = {k: tuple(v) for (k, v) in dict(by_type or {}).items()}

    def v(self, node: int) -> Any:
        return self.values.get(node)

    def s(self, otype: str) -> tuple[int, ...]:
        return tuple(self.by_type.get(otype, ()))


class FakeEdge:
    def __init__(self, mapping: Mapping[int, Sequence[int]] | None = None) -> None:
        self.mapping = {k: tuple(v) for (k, v) in dict(mapping or {}).items()}

    def s(self, node: int) -> tuple[int, ...]:
        return tuple(self.mapping.get(node, ()))

    def f(self, node: int) -> tuple[int, ...] | None:
        values = self.mapping.get(node)
        return None if values is None else tuple(values)


class FakeLocality:
    def __init__(
        self,
        *,
        up: Mapping[tuple[int, str], Sequence[int]] | None = None,
        inter: Mapping[tuple[int, str], Sequence[int]] | None = None,
        down: Mapping[tuple[int, str], Sequence[int]] | None = None,
    ) -> None:
        self._up = {k: tuple(v) for (k, v) in dict(up or {}).items()}
        self._inter = {k: tuple(v) for (k, v) in dict(inter or {}).items()}
        self._down = {k: tuple(v) for (k, v) in dict(down or {}).items()}

    def u(self, node: int, otype: str | None = None) -> tuple[int, ...]:
        return tuple(self._up.get((node, otype), ()))

    def i(self, node: int, otype: str | None = None) -> tuple[int, ...]:
        return tuple(self._inter.get((node, otype), ()))

    def d(self, node: int, otype: str | None = None) -> tuple[int, ...]:
        return tuple(self._down.get((node, otype), ()))


class FakeText:
    def __init__(self, texts: Mapping[int, str], sections: Mapping[int, tuple[str, int, int]]) -> None:
        self._texts = dict(texts)
        self._sections = dict(sections)

    def text(self, node: int) -> str:
        return self._texts.get(node, f"<{node}>")

    def sectionFromNode(self, node: int) -> tuple[str, int, int]:
        return self._sections.get(node, ("Genesis", 1, 1))


@dataclass(frozen=True)
class SyntheticNodeSpec:
    clause_atom: int
    clause: int
    phrases: tuple[int, ...]
    words: tuple[int, ...]
    section: tuple[str, int, int]


SPECS = (
    SyntheticNodeSpec(clause_atom=1, clause=101, phrases=(201, 202), words=(11, 12), section=("Genesis", 1, 1)),
    SyntheticNodeSpec(clause_atom=2, clause=102, phrases=(203,), words=(21,), section=("Genesis", 1, 2)),
    SyntheticNodeSpec(clause_atom=3, clause=103, phrases=(204, 205, 206), words=(31, 32, 33), section=("Genesis", 1, 3)),
    SyntheticNodeSpec(clause_atom=4, clause=104, phrases=(207, 208), words=(41, 42), section=("Genesis", 1, 4)),
)


def build_synthetic_api() -> Any:
    by_type = {
        "clause_atom": tuple(spec.clause_atom for spec in SPECS),
        "clause": tuple(spec.clause for spec in SPECS),
        "phrase": tuple(p for spec in SPECS for p in spec.phrases),
        "word": tuple(w for spec in SPECS for w in spec.words),
    }

    feature_values = {
        "instruction": {
            1: "..",
            2: "..",
            3: "..",
            4: "..",
        },
        "tab": {
            1: 0,
            2: 1,
            3: 0,
            4: 1,
        },
        "pargr": {
            1: "1",
            2: "1.1",
            3: "1.2",
            4: "1.2.1",
        },
        "typ": {
            1: "WayX",
            2: "WayX",
            3: "WayX",
            4: "WayX",
            201: "NP",
            202: "VP",
            203: "VP",
            204: "CP",
            205: "NP",
            206: "VP",
            207: "CP",
            208: "VP",
        },
        "txt": {
            101: "N",
            102: "Q",
            103: "N",
            104: "N",
        },
        "function": {
            201: "Subj",
            202: "Pred",
            203: "Pred",
            204: "Conj",
            205: "Subj",
            206: "Pred",
            207: "Rela",
            208: "Pred",
        },
        "rela": {
            3: "Coor",
            4: "Attr",
        },
        "code": {
            2: 999,
            3: 200,
        },
        "lex": {
            11: "DWD[",
            12: "DBR[",
            21: "LK[",
            31: "W",
            32: "HW>",
            33: "HLK[",
            41: "ASR[",
            42: "HLK[",
        },
        "vt": {
            12: "wayq",
            21: "impv",
            33: "wayq",
            42: "wayq",
        },
        "vs": {
            12: "qal",
            21: "qal",
            33: "qal",
            42: "qal",
        },
        "ps": {
            12: "3",
            21: "2",
            33: "3",
            42: "3",
        },
        "nu": {
            12: "sg",
            21: "sg",
            33: "sg",
            42: "sg",
        },
        "gn": {
            12: "m",
            21: "m",
            33: "m",
            42: "m",
        },
        "prs": {},
        "prs_ps": {},
        "prs_nu": {},
        "prs_gn": {},
    }

    F = SimpleNamespace()
    F.otype = FakeFeature(by_type=by_type)
    for (name, values) in feature_values.items():
        setattr(F, name, FakeFeature(values=values))

    oslots = {
        1: (11, 12),
        101: (11, 12),
        201: (11,),
        202: (12,),
        2: (21,),
        102: (21,),
        203: (21,),
        3: (31, 32, 33),
        103: (31, 32, 33),
        204: (31,),
        205: (32,),
        206: (33,),
        4: (41, 42),
        104: (41, 42),
        207: (41,),
        208: (42,),
        11: (11,),
        12: (12,),
        21: (21,),
        31: (31,),
        32: (32,),
        33: (33,),
        41: (41,),
        42: (42,),
    }
    mother = {
        2: (1,),
        3: (1,),
        4: (3,),
    }
    E = SimpleNamespace(oslots=FakeEdge(oslots), mother=FakeEdge(mother))

    up = {
        (1, "clause"): (101,),
        (2, "clause"): (102,),
        (3, "clause"): (103,),
        (4, "clause"): (104,),
    }
    phrase_map = {
        1: (201, 202),
        2: (203,),
        3: (204, 205, 206),
        4: (207, 208),
    }
    inter = {(atom, "phrase"): phrases for (atom, phrases) in phrase_map.items()}
    down = {(atom, "phrase"): phrases for (atom, phrases) in phrase_map.items()}
    L = FakeLocality(up=up, inter=inter, down=down)

    texts = {
        1: "David said",
        2: "Go",
        3: "And he went",
        4: "who went",
        101: "Clause 1",
        102: "Clause 2",
        103: "Clause 3",
        104: "Clause 4",
        201: "David",
        202: "said",
        203: "Go",
        204: "And",
        205: "he",
        206: "went",
        207: "who",
        208: "went",
        11: "David",
        12: "said",
        21: "Go",
        31: "And",
        32: "he",
        33: "went",
        41: "who",
        42: "went",
    }
    sections = {}
    for spec in SPECS:
        for node in (spec.clause_atom, spec.clause, *spec.phrases, *spec.words):
            sections[node] = spec.section
    T = FakeText(texts=texts, sections=sections)

    return SimpleNamespace(F=F, E=E, L=L, T=T)


def build_seed_resources(module: Any) -> Any:
    return module.ResourceTables(
        quote_verbs=frozenset({"DBR["}),
        object_clause_governors=frozenset({"DBR["}),
        conjunction_classes={"W": "coord", ">W": "coord"},
        relative_lexemes=frozenset({"ASR["}),
    )
