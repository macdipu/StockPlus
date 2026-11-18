"""Parse and validate the `indicators` query: "rsi(14),macd(12,26,9),bbands" -> resolved specs. Pure."""

import hashlib
from collections.abc import Mapping
from dataclasses import dataclass

from dse.indicators import REGISTRY, Indicator
from dse.shared_kernel.errors import ValidationFailedError

MAX_INDICATORS = 8
MAX_SPEC_LENGTH = 400


@dataclass(frozen=True, slots=True)
class ResolvedSpec:
    key: str  # canonical, unique within a request: "rsi(14)", "macd(12,26,9)", "obv"
    indicator: Indicator
    params: Mapping[str, float]


def _split_top_level(raw: str) -> list[str]:
    parts: list[str] = []
    cur: list[str] = []
    depth = 0
    for ch in raw:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth < 0:
                raise ValidationFailedError("indicators: unbalanced ')'")
        if ch == "," and depth == 0:
            parts.append("".join(cur))
            cur = []
        else:
            cur.append(ch)
    if depth != 0:
        raise ValidationFailedError("indicators: unbalanced '('")
    parts.append("".join(cur))
    return [p.strip() for p in parts if p.strip()]


def _fmt(v: float) -> str:
    return str(int(v)) if float(v).is_integer() else f"{v:g}"


def parse_specs(raw: str | None, registry: Mapping[str, Indicator] = REGISTRY) -> list[ResolvedSpec]:
    """Positional arguments follow the indicator's parameter order; omitted ones take their defaults."""
    if not raw or not raw.strip():
        return []
    if len(raw) > MAX_SPEC_LENGTH:
        raise ValidationFailedError(f"indicators: at most {MAX_SPEC_LENGTH} characters")
    out: list[ResolvedSpec] = []
    for item in _split_top_level(raw):
        name, _, rest = item.partition("(")
        ind_id = name.strip().lower()
        ind = registry.get(ind_id)
        if ind is None:
            raise ValidationFailedError(
                f"indicators: unknown indicator '{ind_id}'. See GET /api/v1/charts/indicators"
            )
        args: list[float] = []
        if rest:
            if not rest.endswith(")"):
                raise ValidationFailedError(f"indicators: '{item}' is missing ')'")
            body = rest[:-1].strip()
            try:
                args = [float(a) for a in body.split(",") if a.strip()]
            except ValueError as e:
                raise ValidationFailedError(f"indicators: arguments of '{ind_id}' must be numbers") from e
        if len(args) > len(ind.params):
            raise ValidationFailedError(f"indicators: {ind_id} takes at most {len(ind.params)} parameter(s)")
        params = ind.resolve({p.key: a for p, a in zip(ind.params, args, strict=False)})
        key = ind_id if not ind.params else f"{ind_id}({','.join(_fmt(params[p.key]) for p in ind.params)})"
        if any(s.key == key for s in out):
            continue  # asking for the same thing twice draws it once
        out.append(ResolvedSpec(key, ind, params))
        if len(out) > MAX_INDICATORS:
            raise ValidationFailedError(f"indicators: at most {MAX_INDICATORS} per chart")
    return out


def spec_hash(specs: list[ResolvedSpec]) -> str:
    return hashlib.blake2b("|".join(s.key for s in specs).encode(), digest_size=6).hexdigest()
