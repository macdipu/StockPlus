"""Rule engine behaviour that is new in the port: validation, composition, stable sort, filters."""

from collections.abc import Callable
from typing import Any

import pandas as pd
import pytest

from dse.features.scanner.application.facade import ScannerFacade
from dse.features.scanner.domain.rules import (
    AllOf,
    AnyOf,
    Preset,
    Rule,
    ScanError,
    ScanSpec,
    Sort,
    UniverseFilter,
    compose,
    parse_scan_definition,
    run_scan,
)
from dse.features.scanner.domain.universe import Universe, rows_to_frame
from dse.shared_kernel.errors import ServiceNotReadyError, ValidationFailedError


@pytest.fixture
def u() -> pd.DataFrame:
    rows: list[dict[str, Any]] = [
        {"symbol": "A", "sector": "Bank", "category": "A", "asset_type": "EQ", "rsi14": 25.0, "ltp": 10.0,
         "value_mn": 5.0, "pats": ["Doji"], "flag": True, "sma50": 9.0, "sma50_prev": 11.0, "sma200": 10.0,
         "sma200_prev": 10.0},
        {"symbol": "B", "sector": "Bank", "category": "B", "asset_type": "EQ", "rsi14": 55.0, "ltp": 20.0,
         "value_mn": 1.0, "pats": [], "flag": False, "sma50": 12.0, "sma50_prev": 9.0, "sma200": 10.0,
         "sma200_prev": 10.0},
        {"symbol": "C", "sector": "Food", "category": "Z", "asset_type": "MF", "rsi14": None, "ltp": 30.0,
         "value_mn": None, "pats": ["Hammer", "Doji"], "flag": None, "sma50": 10.0, "sma50_prev": 10.0,
         "sma200": 10.0, "sma200_prev": 10.0},
        {"symbol": "D", "sector": "Food", "category": "A", "asset_type": "EQ", "rsi14": 55.0, "ltp": 40.0,
         "value_mn": 9.0, "pats": [], "flag": False, "sma50": 10.0, "sma50_prev": 10.0, "sma200": 10.0,
         "sma200_prev": 10.0},
    ]  # fmt: skip
    return rows_to_frame(rows)


def syms(df: pd.DataFrame) -> list[str]:
    return list(df["symbol"])


def test_invalid_rules_fail_at_construction() -> None:
    bad_rules: list[Callable[[], object]] = [
        lambda: Rule("rsi14", "nope", 1),
        lambda: Rule("rsi14", "<"),
        lambda: Rule("rsi14", "between", 5),
        lambda: Rule("rsi14", "between", [1]),
        lambda: Rule("sector", "in", "Bank"),
        lambda: Rule("pats", "contains"),
        lambda: Rule("a", "crosses_above"),
    ]
    for bad in bad_rules:
        with pytest.raises(ScanError):
            bad()
    assert issubclass(ScanError, ValidationFailedError)  # → HTTP 400 problem+json


def test_unknown_field_and_numeric_op_on_text(u: pd.DataFrame) -> None:
    with pytest.raises(ScanError, match="Unknown field 'nope'"):
        Rule("nope", ">", 1).mask(u)
    with pytest.raises(ScanError, match="needs a number"):
        Rule("sector", ">", "Bank").mask(u)
    with pytest.raises(ScanError, match="Unknown field"):
        Rule("sma50", "crosses_above", field2="sma999").mask(u)


def test_operator_semantics(u: pd.DataFrame) -> None:
    def hit(rule: Rule) -> list[str]:
        return syms(u[rule.mask(u)])

    assert hit(Rule("rsi14", "<", 30)) == ["A"]  # missing RSI never matches
    assert hit(Rule("rsi14", ">=", 55)) == ["B", "D"]
    assert hit(Rule("rsi14", "between", [20, 60])) == ["A", "B", "D"]
    assert hit(Rule("ltp", ">", field2="sma50")) == ["A", "B", "C", "D"]
    assert hit(Rule("category", "in", ["A"])) == ["A", "D"]
    assert hit(Rule("category", "not_in", ["A"])) == ["B", "C"]
    assert hit(Rule("sector", "==", "Food")) == ["C", "D"]
    assert hit(Rule("sector", "!=", "Food")) == ["A", "B"]
    assert hit(Rule("pats", "contains", "Doji")) == ["A", "C"]
    assert hit(Rule("flag", "is_true")) == ["A"]  # None counts as false
    assert hit(Rule("flag", "is_false")) == ["B", "C", "D"]
    assert hit(Rule("sma50", "crosses_above", field2="sma200")) == ["B"]
    assert hit(Rule("sma50", "crosses_below", field2="sma200")) == ["A"]
    assert hit(Rule("sma50", "crosses_above", value=10)) == ["B"]


def test_specifications_compose(u: pd.DataFrame) -> None:
    bank = Rule("sector", "==", "Bank")
    cheap = Rule("ltp", "<", 25)
    z = Rule("category", "==", "Z")
    assert syms(u[AllOf([bank, cheap]).mask(u)]) == ["A", "B"]
    assert syms(u[AnyOf([z, bank]).mask(u)]) == ["A", "B", "C"]
    nested = AnyOf([AllOf([bank, Rule("rsi14", "<", 30)]), z])  # (bank AND rsi<30) OR z
    assert syms(u[nested.mask(u)]) == ["A", "C"]
    assert syms(u[AllOf([]).mask(u)]) == syms(u)  # empty AND = everything
    assert isinstance(compose([bank], "any"), AnyOf)
    assert isinstance(compose([bank], "all"), AllOf)


def test_universe_filter(u: pd.DataFrame) -> None:
    def scan(f: UniverseFilter) -> list[str]:
        return syms(run_scan(u, ScanSpec((), universe=f)))

    assert scan(UniverseFilter()) == ["A", "B", "C", "D"]
    assert scan(UniverseFilter(asset_types=("EQ",))) == ["A", "B", "D"]
    assert scan(UniverseFilter(sectors=("Food",), categories=("A",))) == ["D"]
    assert scan(UniverseFilter(min_value_mn=5.0)) == ["A", "D"]  # missing turnover counts as 0


def test_sort_is_stable_nulls_last_and_validated(u: pd.DataFrame) -> None:
    spec = ScanSpec((), sort=Sort("rsi14", True))
    assert syms(run_scan(u, spec)) == ["B", "D", "A", "C"]  # ties (B, D) keep input order; NaN last
    assert syms(run_scan(u, ScanSpec((), sort=Sort("rsi14", False)))) == ["A", "B", "D", "C"]
    assert syms(run_scan(u, ScanSpec((), sort=Sort("ltp", True), limit=2))) == ["D", "C"]
    with pytest.raises(ScanError, match="Unknown field"):
        run_scan(u, ScanSpec((), sort=Sort("nope", True)))


def test_empty_universe_scans_to_empty() -> None:
    empty = rows_to_frame([])
    assert run_scan(empty, ScanSpec((Rule("rsi14", "<", 30),))).empty


def test_preset_builds_a_spec() -> None:
    p = Preset("k", "K", "G", "d", (Rule("rsi14", "<", 30),), Sort("rsi14", False), "all", True)
    spec = p.spec(UniverseFilter(asset_types=("EQ",)), 7)
    assert (spec.limit, spec.sort, spec.match) == (7, Sort("rsi14", False), "all")


def test_universe_frame_requires_rows() -> None:
    uni = Universe(1, 0, 0, None, None, rows_to_frame([]), rows_to_frame([]))
    with pytest.raises(ServiceNotReadyError):
        uni.frame()


# --- scan definitions as plain JSON (saved scans) ---
def test_parse_scan_definition_builds_a_validated_spec() -> None:
    spec = parse_scan_definition(
        {
            "rules": [
                {"field": "rsi14", "op": "between", "value": [40, 80]},
                {"field": "close", "op": ">", "field2": "ema21"},
            ],
            "match": "any",
            "universe": {"sectors": ["Bank"], "asset_types": ["EQ"], "min_value_mn": 1.5},
            "sort": {"field": "vol_ratio"},
            "limit": 25,
            "columns": ["symbol"],
            "live": False,
        }
    )
    assert spec.rules == (Rule("rsi14", "between", [40, 80]), Rule("close", ">", field2="ema21"))
    assert (spec.match, spec.limit, spec.sort) == ("any", 25, Sort("vol_ratio", True))
    assert spec.universe == UniverseFilter(("Bank",), (), ("EQ",), 1.5)
    minimal = parse_scan_definition({"rules": [{"field": "rsi14", "op": "<", "value": 30}]})
    assert (minimal.match, minimal.limit, minimal.sort) == ("all", 100, None)


@pytest.mark.parametrize(
    "bad",
    [
        None,
        [],
        "rules",
        {},
        {"rules": []},
        {"rules": "x"},
        {"rules": [{"field": "a", "op": "<", "value": 1}] * 21},
        {"rules": [{"op": "<", "value": 1}]},
        {"rules": [{"field": "a", "op": "wat", "value": 1}]},
        {"rules": [{"field": "a", "op": "<"}]},
        {"rules": [{"field": "a", "op": "<", "value": 1, "extra": 1}]},
        {"rules": [{"field": "a", "op": "<", "value": 1}], "match": "some"},
        {"rules": [{"field": "a", "op": "<", "value": 1}], "limit": 0},
        {"rules": [{"field": "a", "op": "<", "value": 1}], "limit": 501},
        {"rules": [{"field": "a", "op": "<", "value": 1}], "limit": True},
        {"rules": [{"field": "a", "op": "<", "value": 1}], "limit": "10"},
        {"rules": [{"field": "a", "op": "<", "value": 1}], "sort": {"desc": True}},
        {"rules": [{"field": "a", "op": "<", "value": 1}], "universe": {"sectors": "Bank"}},
        {"rules": [{"field": "a", "op": "<", "value": 1}], "universe": {"min_value_mn": "5"}},
        {"rules": [{"field": "a", "op": "<", "value": 1}], "universe": []},
        {"rules": [{"field": "a", "op": "<", "value": 1}], "unknown_key": 1},
    ],
)
def test_parse_scan_definition_rejects_malformed_input(bad: object) -> None:
    with pytest.raises(ScanError):
        parse_scan_definition(bad)


def test_scanner_facade_validates_without_needing_a_universe() -> None:
    facade = ScannerFacade()
    facade.validate_scan({"rules": [{"field": "rsi14", "op": "<", "value": 30}]})
    with pytest.raises(ScanError):
        facade.validate_scan({"rules": []})
