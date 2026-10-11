"""Unit tests for TMDb client."""

from unittest.mock import AsyncMock

import pytest

from jfc.clients.tmdb import TMDbClient


class _NotFoundResponse:
    """Minimal response object for 404 simulations."""

    status_code = 404

    def raise_for_status(self) -> None:
        raise AssertionError("raise_for_status should not be called on 404 branch")

    def json(self) -> dict:
        return {}


@pytest.mark.asyncio
async def test_get_list_returns_empty_on_404() -> None:
    """TMDb list fetch should return empty list on 404."""
    client = TMDbClient(api_key="test-api-key")
    client.get = AsyncMock(return_value=_NotFoundResponse())

    items = await client.get_list(8232)

    assert items == []
    client.get.assert_awaited_once()



class _JsonResponse:
    """Minimal JSON response object for TMDb client tests."""

    def __init__(self, data: dict, status_code: int = 200):
        self._data = data
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self) -> dict:
        return self._data


@pytest.mark.asyncio
async def test_find_by_imdb_id_returns_movie() -> None:
    """TMDb find endpoint should resolve a movie result."""
    client = TMDbClient(api_key="test-api-key")
    client.get = AsyncMock(
        return_value=_JsonResponse(
            {
                "movie_results": [{"id": 13, "title": "Forrest Gump", "release_date": "1994-07-06"}],
                "tv_results": [],
            }
        )
    )

    item = await client.find_by_imdb_id("tt0109830")

    assert item is not None
    assert item.tmdb_id == 13
    assert item.imdb_id == "tt0109830"


def _results_page(start_id: int, count: int, media: str = "movie") -> list[dict]:
    """Generate TMDb-like paged results payload."""
    results = []
    for idx in range(count):
        tmdb_id = start_id + idx
        if media == "movie":
            results.append(
                {
                    "id": tmdb_id,
                    "title": f"Movie {tmdb_id}",
                    "release_date": "2024-01-01",
                }
            )
        else:
            results.append(
                {
                    "id": tmdb_id,
                    "name": f"Show {tmdb_id}",
                    "first_air_date": "2024-01-01",
                }
            )
    return results


@pytest.mark.asyncio
async def test_get_popular_movies_paginates_past_20() -> None:
    """Popular movies should paginate when limit exceeds one page."""
    client = TMDbClient(api_key="test-api-key")
    client.get = AsyncMock(
        side_effect=[
            _JsonResponse({"results": _results_page(1, 20, "movie"), "total_pages": 3}),
            _JsonResponse({"results": _results_page(21, 20, "movie"), "total_pages": 3}),
            _JsonResponse({"results": _results_page(41, 20, "movie"), "total_pages": 3}),
        ]
    )

    items = await client.get_popular_movies(limit=50)

    assert len(items) == 50
    assert client.get.await_count == 3
    assert client.get.await_args_list[0].kwargs["params"]["page"] == 1
    assert client.get.await_args_list[1].kwargs["params"]["page"] == 2
    assert client.get.await_args_list[2].kwargs["params"]["page"] == 3


@pytest.mark.asyncio
async def test_get_trending_series_paginates_past_20() -> None:
    """Trending series should paginate when limit exceeds one page."""
    client = TMDbClient(api_key="test-api-key")
    client.get = AsyncMock(
        side_effect=[
            _JsonResponse({"results": _results_page(1, 20, "tv"), "total_pages": 2}),
            _JsonResponse({"results": _results_page(21, 20, "tv"), "total_pages": 2}),
        ]
    )

    items = await client.get_trending_series(time_window="week", limit=30)

    assert len(items) == 30
    assert client.get.await_count == 2
    assert client.get.await_args_list[0].kwargs["params"]["page"] == 1
    assert client.get.await_args_list[1].kwargs["params"]["page"] == 2


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("method", "endpoint", "media"),
    [
        ("get_now_playing_movies", "/movie/now_playing", "movie"),
        ("get_airing_today_series", "/tv/airing_today", "tv"),
        ("get_on_the_air_series", "/tv/on_the_air", "tv"),
    ],
)
async def test_list_endpoints_hit_expected_route(method: str, endpoint: str, media: str) -> None:
    """Now playing / airing today / on the air should query their TMDb endpoint."""
    client = TMDbClient(api_key="test-api-key")
    client.get = AsyncMock(
        return_value=_JsonResponse({"results": _results_page(1, 20, media), "total_pages": 1})
    )

    items = await getattr(client, method)(limit=10)

    assert len(items) == 10
    assert client.get.await_args_list[0].args[0] == endpoint
