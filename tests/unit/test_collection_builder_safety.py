"""Tests for CollectionBuilder safety guards (wipe protection, Radarr release filter)."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from jfc.models.collection import Collection, CollectionConfig, CollectionItem
from jfc.models.report import CollectionReport
from jfc.services.collection_builder import CollectionBuilder


def _make_builder() -> CollectionBuilder:
    builder = CollectionBuilder.__new__(CollectionBuilder)
    builder.dry_run = False
    builder.jellyfin = MagicMock()
    builder.tmdb = MagicMock()
    builder.radarr = None
    builder.sonarr = None
    builder.poster_generator = None
    builder.radarr_only_released = False
    return builder


def _make_collection(items: list[CollectionItem]) -> Collection:
    collection = Collection(
        config=CollectionConfig(name="Test", library="Films"),
        library_name="Films",
        items=items,
    )
    collection.update_stats()
    return collection


def _report() -> CollectionReport:
    return CollectionReport(name="Test", library="Films", schedule="daily", source_provider="x")


@pytest.mark.asyncio
async def test_sync_skips_wipe_when_nothing_matched() -> None:
    """A populated collection must not be emptied when no source item matched."""
    builder = _make_builder()
    builder.jellyfin.get_collections = AsyncMock(return_value=[{"Name": "Test", "Id": "c1"}])
    builder.jellyfin.get_collection_items = AsyncMock(return_value=["a", "b", "c"])
    builder.jellyfin.remove_from_collection = AsyncMock(return_value=True)
    builder.jellyfin.add_to_collection = AsyncMock(return_value=True)

    collection = _make_collection(
        [CollectionItem(title="Missing 1", tmdb_id=1), CollectionItem(title="Missing 2", tmdb_id=2)]
    )

    added, removed, _ = await builder.sync_collection(collection, _report())

    assert (added, removed) == (0, 0)
    builder.jellyfin.remove_from_collection.assert_not_awaited()
    builder.jellyfin.add_to_collection.assert_not_awaited()


@pytest.mark.asyncio
async def test_radarr_only_released_skips_theatrical_movies() -> None:
    """With only_released, movies without a home release are not sent to Radarr."""
    builder = _make_builder()
    builder.radarr_only_released = True
    builder.radarr = MagicMock()
    builder.radarr.add_movie = AsyncMock(return_value={"title": "x"})
    builder.tmdb.is_movie_released = AsyncMock(side_effect=lambda tmdb_id: tmdb_id == 2)

    collection = _make_collection(
        [
            CollectionItem(title="In theaters", tmdb_id=1, media_type="movie"),
            CollectionItem(title="On VOD", tmdb_id=2, media_type="movie"),
        ]
    )
    report = _report()

    radarr_count, _ = await builder._add_missing_to_arr(collection, report)

    assert radarr_count == 1
    assert report.radarr_titles == ["On VOD"]
    builder.radarr.add_movie.assert_awaited_once()
    assert builder.radarr.add_movie.await_args.kwargs["tmdb_id"] == 2
