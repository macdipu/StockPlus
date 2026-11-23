"""Dependency providers for the scanner (read side; the worker wires the write side)."""

from dataclasses import dataclass

from fastapi import Request

from dse.features.scanner.application.ports import RescanChannel
from dse.features.scanner.application.use_cases import (
    GetPe,
    GetPicks,
    GetRange52w,
    GetSectors,
    GetTable,
    GetUniverseStatus,
    ListFields,
    ListPresets,
    RequestRescan,
    RunPreset,
    RunScan,
)
from dse.features.scanner.application.view import UniverseView


@dataclass(frozen=True)
class ScannerContainer:
    view: UniverseView
    rescan_channel: RescanChannel

    @property
    def run_scan(self) -> RunScan:
        return RunScan(self.view)

    @property
    def run_preset(self) -> RunPreset:
        return RunPreset(self.view)

    @property
    def list_presets(self) -> ListPresets:
        return ListPresets()

    @property
    def list_fields(self) -> ListFields:
        return ListFields()

    @property
    def sectors(self) -> GetSectors:
        return GetSectors(self.view)

    @property
    def pe(self) -> GetPe:
        return GetPe(self.view)

    @property
    def range_52w(self) -> GetRange52w:
        return GetRange52w(self.view)

    @property
    def table(self) -> GetTable:
        return GetTable(self.view)

    @property
    def picks(self) -> GetPicks:
        return GetPicks(self.view)

    @property
    def rescan(self) -> RequestRescan:
        return RequestRescan(self.view, self.rescan_channel)

    @property
    def status(self) -> GetUniverseStatus:
        return GetUniverseStatus(self.view)


def container(request: Request) -> ScannerContainer:
    c: ScannerContainer = request.app.state.scanner
    return c
