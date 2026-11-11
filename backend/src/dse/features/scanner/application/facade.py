"""The ONLY entry point other features may use (import-linter enforces this)."""

from typing import Any

from dse.features.scanner.domain.rules import parse_scan_definition


class ScannerFacade:
    def validate_scan(self, definition: Any) -> None:
        """Raises ScanError (a 400) when `definition` is not a well-formed scan."""
        parse_scan_definition(definition)
