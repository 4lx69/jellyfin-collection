"""Unit tests for Radarr/Sonarr exclusion and blocklist refresh."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from jfc.clients.radarr import RadarrClient
from jfc.clients.sonarr import SonarrClient
from jfc.core.config import Settings
from jfc.services.startup import StartupService


class _JsonResponse:
    """Minimal JSON response wrapper for tests."""

    def __init__(self, payload, status_code: int = 200):
        self._payload = payload
        self.status_code = status_code

    def json(self):
        return self._payload

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


def _radarr() -> RadarrClient:
    return RadarrClient(url="http://radarr:7878", api_key="test")


def _sonarr() -> SonarrClient:
    return SonarrClient(url="http://sonarr:8989", api_key="test")


@pytest.mark.asyncio
async def test_radarr_exclusions_are_cached_by_default() -> None:
    """A second call without force_refresh must not hit the API again."""
    client = _radarr()
    client.get = AsyncMock(return_value=_JsonResponse([{"tmdbId": 1}]))

    assert await client.load_exclusions() == {1}
    assert await client.load_exclusions() == {1}
    assert client.get.await_count == 1


@pytest.mark.asyncio
async def test_radarr_exclusions_refetched_when_forced() -> None:
    """force_refresh must pick up movies excluded after the first load."""
    client = _radarr()
    client.get = AsyncMock(
        side_effect=[
            _JsonResponse([{"tmdbId": 1}]),
            _JsonResponse([{"tmdbId": 1}, {"tmdbId": 2}]),
        ]
    )

    assert await client.load_exclusions() == {1}
    assert await client.load_exclusions(force_refresh=True) == {1, 2}
    assert client.get.await_count == 2


@pytest.mark.asyncio
async def test_radarr_keeps_previous_exclusions_when_refresh_fails() -> None:
    """A failed refresh must not drop the exclusions loaded previously."""
    client = _radarr()
    client.get = AsyncMock(
        side_effect=[_JsonResponse([{"tmdbId": 1}]), RuntimeError("Radarr down")]
    )

    assert await client.load_exclusions() == {1}
    with pytest.raises(RuntimeError):
        await client.load_exclusions(force_refresh=True)
    assert client._exclusion_tmdb_ids == {1}


@pytest.mark.asyncio
async def test_sonarr_exclusions_refetched_when_forced() -> None:
    """Sonarr exclusions behave the same as Radarr's."""
    client = _sonarr()
    client.get = AsyncMock(
        side_effect=[
            _JsonResponse([{"tvdbId": 10}]),
            _JsonResponse([{"tvdbId": 10}, {"tvdbId": 20}]),
        ]
    )

    assert await client.load_exclusions() == {10}
    assert await client.load_exclusions(force_refresh=True) == {10, 20}


@pytest.mark.asyncio
async def test_radarr_skips_newly_excluded_movie_after_refresh() -> None:
    """A movie excluded between two runs must no longer be added."""
    client = _radarr()
    exclusions: list[dict[str, int]] = []

    async def _get(endpoint: str, **kwargs):
        if endpoint == "/api/v3/exclusions":
            return _JsonResponse(list(exclusions))
        if endpoint == "/api/v3/blocklist":
            return _JsonResponse({"records": []})
        raise AssertionError(f"unexpected endpoint: {endpoint}")

    client.get = AsyncMock(side_effect=_get)
    client.movie_exists = AsyncMock(return_value=True)
    client.get_movie_by_tmdb_id = AsyncMock(return_value={"tmdbId": 42})

    assert await client.add_movie(42) == {"tmdbId": 42}

    # User excludes the movie in Radarr, then the next run refreshes the list
    exclusions.append({"tmdbId": 42})
    await client.load_exclusions(force_refresh=True)

    assert await client.add_movie(42) is None


@pytest.mark.asyncio
async def test_refresh_blocklists_forces_reload() -> None:
    """StartupService.refresh_blocklists re-fetches both services' lists."""
    radarr = MagicMock()
    radarr.load_blocklist = AsyncMock(return_value={1})
    radarr.load_exclusions = AsyncMock(return_value={2, 3})

    sonarr = MagicMock()
    sonarr.load_blocklist = AsyncMock(return_value=set())
    sonarr.load_exclusions = AsyncMock(return_value={4})

    startup = StartupService(
        settings=MagicMock(),
        jellyfin=MagicMock(),
        tmdb=MagicMock(),
        radarr=radarr,
        sonarr=sonarr,
    )

    stats = await startup.refresh_blocklists()

    radarr.load_blocklist.assert_awaited_once_with(force_refresh=True)
    radarr.load_exclusions.assert_awaited_once_with(force_refresh=True)
    sonarr.load_exclusions.assert_awaited_once_with(force_refresh=True)
    assert stats["Radarr"] == {"blocklist": 1, "exclusions": 2}
    assert stats["Sonarr"] == {"blocklist": 0, "exclusions": 1}


@pytest.mark.asyncio
async def test_refresh_blocklists_noop_without_arr() -> None:
    """Nothing to refresh when neither Radarr nor Sonarr is configured."""
    startup = StartupService(
        settings=MagicMock(),
        jellyfin=MagicMock(),
        tmdb=MagicMock(),
    )

    assert await startup.refresh_blocklists() == {}


@pytest.fixture
def config_dir(tmp_path, monkeypatch):
    """Minimal config.yml so Settings() can be instantiated."""
    (tmp_path / "config.yml").write_text("settings: {}\n", encoding="utf-8")
    monkeypatch.setenv("CONFIG_PATH", str(tmp_path))
    return tmp_path


def test_force_exclusion_list_refresh_defaults_to_false(config_dir, monkeypatch) -> None:
    """The refresh is opt-in: existing setups keep the startup-only behaviour."""
    monkeypatch.delenv("FORCE_EXCLUSION_LIST_REFRESH", raising=False)

    assert Settings(_env_file=None).force_exclusion_list_refresh is False


def test_force_exclusion_list_refresh_from_env(config_dir, monkeypatch) -> None:
    """FORCE_EXCLUSION_LIST_REFRESH enables the per-run refresh."""
    monkeypatch.setenv("FORCE_EXCLUSION_LIST_REFRESH", "true")

    assert Settings(_env_file=None).force_exclusion_list_refresh is True


def test_force_exclusion_list_refresh_from_yaml(config_dir, monkeypatch) -> None:
    """The toggle can also be set in config.yml."""
    monkeypatch.delenv("FORCE_EXCLUSION_LIST_REFRESH", raising=False)
    (config_dir / "config.yml").write_text(
        "settings:\n  force_exclusion_list_refresh: true\n", encoding="utf-8"
    )

    assert Settings(_env_file=None).force_exclusion_list_refresh is True


@pytest.fixture
def runner_settings(config_dir, monkeypatch, tmp_path):
    """Settings for a Runner with no libraries and no notifications configured."""
    monkeypatch.setenv("DATA_PATH", str(tmp_path / "data"))
    monkeypatch.setenv("LOG_PATH", str(tmp_path / "logs"))
    monkeypatch.delenv("FORCE_EXCLUSION_LIST_REFRESH", raising=False)
    return config_dir


def _build_runner(settings):
    """Build a Runner with startup and Jellyfin stubbed out."""
    from jfc.services.runner import Runner

    runner = Runner(settings)
    runner.startup = MagicMock()
    runner.startup.run_startup = AsyncMock(return_value=True)
    runner.startup.refresh_blocklists = AsyncMock(return_value={})
    runner.jellyfin.get_libraries = AsyncMock(return_value=[])
    return runner


@pytest.mark.asyncio
async def test_runner_skips_refresh_when_disabled(runner_settings) -> None:
    """Default behaviour is unchanged: lists are loaded once, at startup."""
    from jfc.core.config import Settings

    runner = _build_runner(Settings(_env_file=None))

    await runner.run()
    await runner.run()

    runner.startup.run_startup.assert_awaited_once()
    runner.startup.refresh_blocklists.assert_not_awaited()


@pytest.mark.asyncio
async def test_runner_refreshes_when_enabled(runner_settings, monkeypatch) -> None:
    """With the toggle on, every run after startup re-reads the lists."""
    from jfc.core.config import Settings

    monkeypatch.setenv("FORCE_EXCLUSION_LIST_REFRESH", "true")
    runner = _build_runner(Settings(_env_file=None))

    # First run: startup already loaded fresh lists, no extra refresh
    await runner.run()
    runner.startup.refresh_blocklists.assert_not_awaited()

    await runner.run()
    await runner.run()

    assert runner.startup.refresh_blocklists.await_count == 2


@pytest.mark.asyncio
async def test_runner_skips_refresh_in_posters_only_mode(runner_settings, monkeypatch) -> None:
    """posters_only never sends anything to Radarr/Sonarr, so no refresh is needed."""
    from jfc.core.config import Settings

    monkeypatch.setenv("FORCE_EXCLUSION_LIST_REFRESH", "true")
    runner = _build_runner(Settings(_env_file=None))

    await runner.run()
    await runner.run(posters_only=True)

    runner.startup.refresh_blocklists.assert_not_awaited()
