"""DSE trading code value object."""

import re
from dataclasses import dataclass

from dse.shared_kernel.errors import ValidationFailedError

_PATTERN = re.compile(r"^[A-Z0-9&().\-]{1,24}$")


@dataclass(frozen=True, slots=True)
class Symbol:
    value: str

    def __post_init__(self) -> None:
        normalised = self.value.strip().upper()
        if not _PATTERN.match(normalised):
            raise ValidationFailedError(f"Invalid DSE trading code: {self.value!r}")
        object.__setattr__(self, "value", normalised)

    def __str__(self) -> str:
        return self.value
