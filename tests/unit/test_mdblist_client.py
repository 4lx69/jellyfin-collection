"""Unit tests for MDBList client."""

from unittest.mock import AsyncMock

import pytest

from jfc.clients.mdblist import MDBListClient
from jfc.models.media import MediaType


class _JsonResponse:
    """Minimal JSON response wrapper for tests."""

    def __init__(
        self,
        status_code: int,
        payload: dict | None = None,
        headers: dict | None = None,
    ):
        self.status_code = status_code
        self._payload = payload or {}
        self.headers = headers or {}

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self) -> dict:
        return self._payload


def test_parse_list_ref_url() -> None:
    """URL parsing should extract username and slug."""
    client = MDBListClient("key")
    assert client.parse_list_ref(
        "https://mdblist.com/lists/linaspurinis/top-watched-movies-of-the-week"
    ) == {
        "username": "linaspurinis",
        "listname": "top-watched-movies-of-the-week",
    }


def test_parse_list_ref_numeric() -> None:
    """Numeric list references should map to list_id."""
    client = MDBListClient("key")
    assert client.parse_list_ref("2194") == {"list_id": 2194}


def test_parse_list_ref_user_slug() -> None:
    """Bare user/slug references should be accepted."""
    client = MDBListClient("key")
    assert client.parse_list_ref("linaspurinis/top-watched-movies-of-the-week") == {
        "username": "linaspurinis",
        "listname": "top-watched-movies-of-the-week",
    }


def test_parse_sort_by_splits_direction() -> None:
    """Kometa sort_by should map to API sort + order."""
    client = MDBListClient("key")
    assert client._parse_sort_by("imdbrating.desc") == ("imdbrating", "desc")
    assert client._parse_sort_by("rank") == ("rank", None)


@pytest.mark.asyncio
async def test_get_list_items_maps_tmdb_ids() -> None:
    """List items should map nested ids.tmdb / imdb fields."""
    client = MDBListClient("key")
    client.get = AsyncMock(
        return_value=_JsonResponse(
            200,
            {
                "movies": [
                    {
                        "id": 1,
                        "title": "Beetlejuice Beetlejuice",
                        "release_year": 2024,
                        "imdb_id": "tt2049403",
                        "ids": {"tmdb": 917496, "imdb": "tt2049403"},
                    }
                ],
                "shows": [],
                "pagination": {},
            },
        )
    )

    items = await client.get_list_items(
        username="user",
        listname="list",
        media_type=MediaType.MOVIE,
        limit=10,
    )

    assert len(items) == 1
    assert items[0].tmdb_id == 917496
    assert items[0].imdb_id == "tt2049403"
    assert items[0].title == "Beetlejuice Beetlejuice"


@pytest.mark.asyncio
async def test_get_list_items_does_not_use_toplevel_id_as_tmdb() -> None:
    """Top-level MDBList id must not be treated as TMDb id."""
    client = MDBListClient("key")
    client.get = AsyncMock(
        return_value=_JsonResponse(
            200,
            {
                "movies": [
                    {
                        "id": 111,
                        "title": "Unknown Movie",
                        "release_year": 2020,
                        "imdb_id": "tt0000001",
                        "ids": {"imdb": "tt0000001"},
                    }
                ],
                "shows": [],
                "pagination": {},
            },
        )
    )

    items = await client.get_list_items(list_id=1, media_type=MediaType.MOVIE)

    assert len(items) == 1
    assert items[0].tmdb_id is None
    assert items[0].imdb_id == "tt0000001"


@pytest.mark.asyncio
async def test_get_list_items_404_returns_empty() -> None:
    """Missing lists should return an empty result set."""
    client = MDBListClient("key")
    client.get = AsyncMock(return_value=_JsonResponse(404))
    assert await client.get_list_items(list_id=1) == []


@pytest.mark.asyncio
async def test_get_list_items_passes_sort_and_order() -> None:
    """sort_by should be sent as separate sort/order query params."""
    client = MDBListClient("key")
    client.get = AsyncMock(
        return_value=_JsonResponse(200, {"movies": [], "shows": [], "pagination": {}})
    )

    await client.get_list_items(
        username="user",
        listname="list",
        sort_by="imdbrating.desc",
        limit=5,
    )

    params = client.get.await_args.kwargs["params"]
    assert params["sort"] == "imdbrating"
    assert params["order"] == "desc"
    assert params["apikey"] == "key"
