"""Unit tests for Jellyfin client authentication."""

import httpx
import pytest

from jfc.clients.jellyfin import JellyfinClient
from jfc.models.media import MediaType


def test_uses_authorization_header_not_legacy_token() -> None:
    """Jellyfin 12 rejects X-Emby-Token; the client must use the Authorization scheme."""
    client = JellyfinClient(url="http://jellyfin:8096", api_key="abc123")

    assert client.headers["Authorization"] == 'MediaBrowser Token="abc123"'
    assert "X-Emby-Token" not in client.headers


@pytest.mark.asyncio
async def test_authorization_header_sent_on_requests() -> None:
    """The header must actually reach the server on normal API calls."""
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(request.headers)
        return httpx.Response(200, json=[])

    client = JellyfinClient(url="http://jellyfin:8096", api_key="abc123")
    client._client = httpx.AsyncClient(
        base_url=client.base_url,
        headers=client.headers,
        transport=httpx.MockTransport(handler),
    )

    assert await client.get_libraries() == []
    assert seen["authorization"] == 'MediaBrowser Token="abc123"'
    assert "x-emby-token" not in seen
    await client.close()


def _collapsing_jellyfin(request: httpx.Request) -> httpx.Response:
    """Mimic Jellyfin 12: movies in a collection collapse into their BoxSet by default."""
    movies = [
        {"Id": "m1", "Name": "Inception", "Type": "Movie", "ProviderIds": {"Tmdb": "27205"}},
        {"Id": "m2", "Name": "Tenet", "Type": "Movie", "ProviderIds": {"Tmdb": "577922"}},
        {"Id": "m3", "Name": "Heat", "Type": "Movie", "ProviderIds": {"Tmdb": "949"}},
    ]
    if request.url.params.get("CollapseBoxSetItems") != "false":
        # Inception and Tenet are in the "Christopher Nolan" collection
        movies = [
            {"Id": "b1", "Name": "Christopher Nolan", "Type": "BoxSet", "ProviderIds": {}},
            movies[2],
        ]
    return httpx.Response(200, json={"Items": movies})


def _mock_client(handler) -> JellyfinClient:
    client = JellyfinClient(url="http://jellyfin:8096", api_key="abc123")
    client._client = httpx.AsyncClient(
        base_url=client.base_url,
        headers=client.headers,
        transport=httpx.MockTransport(handler),
    )
    return client


@pytest.mark.asyncio
async def test_library_items_include_movies_inside_collections() -> None:
    """Movies that belong to a collection must still be returned individually."""
    client = _mock_client(_collapsing_jellyfin)

    items = await client.get_library_items("lib1", media_type=MediaType.MOVIE)

    assert {i.tmdb_id for i in items} == {27205, 577922, 949}
    assert all(i.media_type == MediaType.MOVIE for i in items)
    await client.close()


@pytest.mark.asyncio
async def test_search_and_tmdb_lookup_do_not_collapse_box_sets() -> None:
    """Title search and TMDb lookup must also see movies inside collections."""
    client = _mock_client(_collapsing_jellyfin)

    found = await client.find_by_tmdb_id(27205, media_type=MediaType.MOVIE)
    results = await client.search_items("Tenet", media_type=MediaType.MOVIE)

    assert found is not None and found.tmdb_id == 27205
    assert 577922 in {i.tmdb_id for i in results}
    await client.close()
