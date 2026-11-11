"""HTTP adapter for watchlists and saved scans. Every route needs a signed-in user; ownership is enforced in
the use cases (a resource that is not yours is a 404)."""

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Response, status
from pydantic import BaseModel, Field

from dse.core.auth import CurrentPrincipal
from dse.core.http import envelope
from dse.features.watchlists.presentation.dependencies import WatchlistsContainer, container

router = APIRouter(tags=["watchlists"])
Container = Annotated[WatchlistsContainer, Depends(container)]


class CreateWatchlistBody(BaseModel):
    name: str = Field(max_length=200)
    symbols: list[str] = Field(default_factory=list, max_length=200, examples=[["GP", "BATBC"]])


class RenameBody(BaseModel):
    name: str = Field(max_length=200)


class SymbolsBody(BaseModel):
    symbols: list[str] = Field(max_length=200, examples=[["GP", "BATBC"]])


class SavedScanBody(BaseModel):
    name: str = Field(max_length=200)
    definition: dict[str, Any] = Field(
        examples=[{"rules": [{"field": "rsi14", "op": "<", "value": 30}], "match": "all", "limit": 50}]
    )


class SavedScanPatch(BaseModel):
    name: str | None = Field(None, max_length=200)
    definition: dict[str, Any] | None = None


# ------------------------------------------------------------------------------------ watchlists
@router.get("/watchlists", summary="Your watchlists")
async def list_watchlists(me: CurrentPrincipal, c: Container) -> dict[str, Any]:
    rows = await c.list_watchlists(me.user_id)
    return envelope([w.model_dump(mode="json") for w in rows], count=len(rows))


@router.post("/watchlists", status_code=status.HTTP_201_CREATED, summary="Create a watchlist")
async def create_watchlist(body: CreateWatchlistBody, me: CurrentPrincipal, c: Container) -> dict[str, Any]:
    return envelope((await c.create_watchlist(me.user_id, body.name, body.symbols)).model_dump(mode="json"))


@router.get("/watchlists/{watchlist_id}", summary="One watchlist")
async def get_watchlist(watchlist_id: UUID, me: CurrentPrincipal, c: Container) -> dict[str, Any]:
    return envelope((await c.get_watchlist(me.user_id, watchlist_id)).model_dump(mode="json"))


@router.patch("/watchlists/{watchlist_id}", summary="Rename a watchlist")
async def rename_watchlist(
    watchlist_id: UUID, body: RenameBody, me: CurrentPrincipal, c: Container
) -> dict[str, Any]:
    return envelope((await c.rename_watchlist(me.user_id, watchlist_id, body.name)).model_dump(mode="json"))


@router.put("/watchlists/{watchlist_id}/symbols", summary="Replace the whole ordered symbol list")
async def replace_symbols(
    watchlist_id: UUID, body: SymbolsBody, me: CurrentPrincipal, c: Container
) -> dict[str, Any]:
    out = await c.replace_symbols(me.user_id, watchlist_id, body.symbols)
    return envelope(out.model_dump(mode="json"))


@router.post("/watchlists/{watchlist_id}/symbols", summary="Add symbols (idempotent)")
async def add_symbols(
    watchlist_id: UUID, body: SymbolsBody, me: CurrentPrincipal, c: Container
) -> dict[str, Any]:
    return envelope((await c.add_symbols(me.user_id, watchlist_id, body.symbols)).model_dump(mode="json"))


@router.delete("/watchlists/{watchlist_id}/symbols/{symbol}", summary="Remove a symbol (idempotent)")
async def remove_symbol(
    watchlist_id: UUID, symbol: str, me: CurrentPrincipal, c: Container
) -> dict[str, Any]:
    return envelope((await c.remove_symbol(me.user_id, watchlist_id, symbol)).model_dump(mode="json"))


@router.delete(
    "/watchlists/{watchlist_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete a watchlist"
)
async def delete_watchlist(watchlist_id: UUID, me: CurrentPrincipal, c: Container) -> Response:
    await c.delete_watchlist(me.user_id, watchlist_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ------------------------------------------------------------------------------------ saved scans
@router.get("/saved-scans", summary="Your saved scans")
async def list_saved_scans(me: CurrentPrincipal, c: Container) -> dict[str, Any]:
    rows = await c.list_scans(me.user_id)
    return envelope([s.model_dump(mode="json") for s in rows], count=len(rows))


@router.post("/saved-scans", status_code=status.HTTP_201_CREATED, summary="Save a scan definition")
async def create_saved_scan(body: SavedScanBody, me: CurrentPrincipal, c: Container) -> dict[str, Any]:
    return envelope((await c.create_scan(me.user_id, body.name, body.definition)).model_dump(mode="json"))


@router.get("/saved-scans/{scan_id}", summary="One saved scan")
async def get_saved_scan(scan_id: UUID, me: CurrentPrincipal, c: Container) -> dict[str, Any]:
    return envelope((await c.get_scan(me.user_id, scan_id)).model_dump(mode="json"))


@router.patch("/saved-scans/{scan_id}", summary="Rename and/or redefine a saved scan")
async def update_saved_scan(
    scan_id: UUID, body: SavedScanPatch, me: CurrentPrincipal, c: Container
) -> dict[str, Any]:
    out = await c.update_scan(me.user_id, scan_id, body.name, body.definition)
    return envelope(out.model_dump(mode="json"))


@router.delete(
    "/saved-scans/{scan_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete a saved scan"
)
async def delete_saved_scan(scan_id: UUID, me: CurrentPrincipal, c: Container) -> Response:
    await c.delete_scan(me.user_id, scan_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
