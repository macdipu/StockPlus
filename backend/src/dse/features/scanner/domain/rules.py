"""The scan rule engine. A `Rule` is a Specification over the universe frame: it answers, per instrument,
"does this hold?". `AllOf` / `AnyOf` compose specifications, so presets and custom scans are the same thing.

Rule shapes (semantics identical to the legacy engine):
  Rule("rsi14", "<", 30)
  Rule("close", ">", field2="sma50")                    compare two fields
  Rule("sma50", "crosses_above", field2="sma200")       uses <field>_prev columns
  Rule("rsi14", "between", [50, 70])
  Rule("category", "in", ["A", "B"])
  Rule("bullish_pattern", "is_true")
"""

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

import numpy as np
import pandas as pd

from dse.shared_kernel.errors import ValidationFailedError

COMPARISON: dict[str, Callable[[Any, Any], Any]] = {
    "<": np.less,
    "<=": np.less_equal,
    ">": np.greater,
    ">=": np.greater_equal,
    "==": np.equal,
    "!=": np.not_equal,
}
OTHER_OPS = ("between", "in", "not_in", "is_true", "is_false", "contains", "crosses_above", "crosses_below")
ALL_OPS = (*COMPARISON, *OTHER_OPS)
MatchMode = Literal["all", "any"]


class ScanError(ValidationFailedError):
    """The scan definition is invalid (unknown field/op, malformed value)."""


def _col(u: pd.DataFrame, name: str) -> pd.Series:
    if name not in u.columns:
        raise ScanError(f"Unknown field '{name}'. See GET /api/v1/scanner/fields")
    series: pd.Series = u[name]
    return series


def _num(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s, errors="coerce")


class Specification(Protocol):
    def mask(self, u: pd.DataFrame) -> pd.Series: ...


@dataclass(frozen=True, slots=True)
class Rule:
    field: str
    op: str
    value: Any = None
    field2: str | None = None

    def __post_init__(self) -> None:
        if self.op not in ALL_OPS:
            raise ScanError(f"Unknown op '{self.op}'. Use one of {sorted(ALL_OPS)}")
        if self.op == "between" and not (isinstance(self.value, list | tuple) and len(self.value) == 2):
            raise ScanError(f"'between' on '{self.field}' needs value [low, high]")
        if self.op in ("in", "not_in") and not isinstance(self.value, list | tuple):
            raise ScanError(f"'{self.op}' on '{self.field}' needs a list value")
        if self.op == "contains" and self.value is None:
            raise ScanError(f"'contains' on '{self.field}' needs a value")
        needs_operand = self.op in COMPARISON or self.op in ("crosses_above", "crosses_below")
        if needs_operand and self.value is None and self.field2 is None:
            raise ScanError(f"Rule on '{self.field}' needs 'value' or 'field2'")

    def mask(self, u: pd.DataFrame) -> pd.Series:
        a = _col(u, self.field)
        op = self.op
        if op in COMPARISON:
            b: Any = _num(_col(u, self.field2)) if self.field2 is not None else self.value
            if isinstance(b, str):  # text fields (sector, vpa_bias, …): compare as text, never coerce
                if op not in ("==", "!="):
                    raise ScanError(f"'{op}' needs a number; use == / != / in for text")
                m = a == b
                return (m if op == "==" else ~m).fillna(False)
            return pd.Series(COMPARISON[op](_num(a), b), index=u.index).fillna(False).astype(bool)
        if op == "between":
            lo, hi = self.value
            return _num(a).between(lo, hi).fillna(False)
        if op in ("in", "not_in"):
            m = a.isin(self.value)
            return m if op == "in" else ~m
        if op == "is_true":
            return a.fillna(False).astype(bool)
        if op == "is_false":
            return ~a.fillna(False).astype(bool)
        if op == "contains":  # list fields, e.g. patterns contains "Hammer"
            contained: pd.Series = a.apply(lambda x: self.value in (x or []))
            return contained
        # crosses_above / crosses_below
        a0 = _num(_col(u, f"{self.field}_prev"))
        if self.field2 is not None:
            b, b0 = _num(_col(u, self.field2)), _num(_col(u, f"{self.field2}_prev"))
        else:
            b = b0 = self.value
        a = _num(a)
        crossed: pd.Series = (a0 <= b0) & (a > b) if op == "crosses_above" else (a0 >= b0) & (a < b)
        return crossed.fillna(False)


@dataclass(frozen=True, slots=True)
class AllOf:
    parts: Sequence[Specification]

    def mask(self, u: pd.DataFrame) -> pd.Series:
        if not self.parts:
            return pd.Series(True, index=u.index)
        return pd.concat([p.mask(u) for p in self.parts], axis=1).all(axis=1)


@dataclass(frozen=True, slots=True)
class AnyOf:
    parts: Sequence[Specification]

    def mask(self, u: pd.DataFrame) -> pd.Series:
        if not self.parts:
            return pd.Series(True, index=u.index)
        return pd.concat([p.mask(u) for p in self.parts], axis=1).any(axis=1)


def compose(rules: Sequence[Rule], match: MatchMode = "all") -> Specification:
    return AllOf(rules) if match == "all" else AnyOf(rules)


@dataclass(frozen=True, slots=True)
class UniverseFilter:
    sectors: tuple[str, ...] = ()
    categories: tuple[str, ...] = ()
    asset_types: tuple[str, ...] = ()
    min_value_mn: float | None = None

    def mask(self, u: pd.DataFrame) -> pd.Series:
        base = pd.Series(True, index=u.index)
        for values, column in (
            (self.sectors, "sector"),
            (self.categories, "category"),
            (self.asset_types, "asset_type"),
        ):
            if values:
                base &= _col(u, column).isin(values)
        if self.min_value_mn:
            base &= _num(_col(u, "value_mn")).fillna(0) >= self.min_value_mn
        return base


@dataclass(frozen=True, slots=True)
class Sort:
    field: str = "value_mn"
    desc: bool = True


@dataclass(frozen=True, slots=True)
class ScanSpec:
    rules: tuple[Rule, ...]
    match: MatchMode = "all"
    universe: UniverseFilter = field(default_factory=UniverseFilter)
    sort: Sort | None = None
    limit: int = 100


@dataclass(frozen=True, slots=True)
class Preset:
    key: str
    name: str
    group: str
    description: str
    rules: tuple[Rule, ...]
    sort: Sort
    match: MatchMode = "all"
    premarket: bool = False  # evaluates the last completed session by default

    def spec(self, universe: UniverseFilter, limit: int) -> ScanSpec:
        return ScanSpec(self.rules, self.match, universe, self.sort, limit)


def run_scan(u: pd.DataFrame, spec: ScanSpec) -> pd.DataFrame:
    """Matching rows of the universe frame, sorted and limited. Raises ScanError on a bad definition."""
    if u.empty:
        return u
    hit = compose(spec.rules, spec.match).mask(u)
    out = u[spec.universe.mask(u) & hit]
    if spec.sort:
        _col(out, spec.sort.field)  # unknown sort field → ScanError, not a KeyError
        out = out.sort_values(
            by=str(spec.sort.field), ascending=not spec.sort.desc, na_position="last", kind="stable"
        )
    return out.head(spec.limit)


_DEFINITION_KEYS = {"rules", "match", "universe", "sort", "limit", "columns", "live"}
MAX_RULES = 20


def _str_list(v: Any, what: str) -> tuple[str, ...]:
    if v is None:
        return ()
    if not isinstance(v, list) or not all(isinstance(x, str) for x in v):
        raise ScanError(f"'{what}' must be a list of strings")
    return tuple(v)


def parse_scan_definition(d: Any) -> ScanSpec:
    """A scan as plain JSON (what a client POSTs, and what a saved scan stores) → a validated ScanSpec.
    Strict: unknown keys and malformed rules are rejected. Whether a *field name* exists is only known against
    a built universe, so an unknown field still fails when the scan runs."""
    if not isinstance(d, dict):
        raise ScanError("A scan definition must be a JSON object")
    unknown = set(d) - _DEFINITION_KEYS
    if unknown:
        raise ScanError(f"Unknown key(s) in scan definition: {sorted(unknown)}")
    raw = d.get("rules")
    if not isinstance(raw, list) or not 1 <= len(raw) <= MAX_RULES:
        raise ScanError(f"'rules' must be a list of 1–{MAX_RULES} rules")
    rules = []
    for r in raw:
        if not isinstance(r, dict) or not isinstance(r.get("field"), str) or not isinstance(r.get("op"), str):
            raise ScanError("Each rule needs a string 'field' and 'op'")
        extra = set(r) - {"field", "op", "value", "field2"}
        if extra:
            raise ScanError(f"Unknown key(s) in rule: {sorted(extra)}")
        rules.append(Rule(r["field"], r["op"], r.get("value"), r.get("field2")))
    match = d.get("match", "all")
    if match not in ("all", "any"):
        raise ScanError("'match' must be 'all' or 'any'")
    u = d.get("universe")
    u = {} if u is None else u
    if not isinstance(u, dict):
        raise ScanError("'universe' must be an object")
    mv = u.get("min_value_mn")
    if mv is not None and (isinstance(mv, bool) or not isinstance(mv, int | float)):
        raise ScanError("'min_value_mn' must be a number")
    sort = d.get("sort")
    if sort is not None and not (isinstance(sort, dict) and isinstance(sort.get("field"), str)):
        raise ScanError("'sort' needs a string 'field'")
    limit = d.get("limit", 100)
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 500:
        raise ScanError("'limit' must be an integer between 1 and 500")
    return ScanSpec(
        rules=tuple(rules),
        match=match,
        universe=UniverseFilter(
            _str_list(u.get("sectors"), "sectors"),
            _str_list(u.get("categories"), "categories"),
            _str_list(u.get("asset_types"), "asset_types"),
            mv,
        ),
        sort=Sort(sort["field"], bool(sort.get("desc", True))) if sort else None,
        limit=limit,
    )
