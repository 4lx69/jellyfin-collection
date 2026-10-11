"""Tests for long-running daemon auth handling (Jellyfin header, Trakt token, startup retry)."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from jfc.clients.jellyfin import JellyfinClient
from jfc.services.runner import Runner
from jfc.services.startup import StartupService


class _StopRun(Exception):
    """Raised by the fake startup to stop run() right after Trakt init."""


class _FakeTraktAuth:
    def __init__(self, token: str | None):
        self.token = token

    async def get_valid_token(self) -> str | None:
        return self.token


def _make_runner(trakt_auth: _FakeTraktAuth) -> Runner:
    runner = Runner.__new__(Runner)
    runner.trakt = None
    runner.trakt_auth = trakt_auth
    runner.builder = SimpleNamespace(trakt=None, matcher=None)
    runner.settings = SimpleNamespace(
        trakt=SimpleNamespace(client_id="id", client_secret="secret"),
        openai=SimpleNamespace(force_regenerate=False),
    )
    runner._startup_done = False
    runner.startup = SimpleNamespace(run_startup=AsyncMock(side_effect=_StopRun))
    return runner


async def _run_until_startup(runner: Runner) -> None:
    with pytest.raises(_StopRun):
        await runner.run()


def test_jellyfin_uses_mediabrowser_authorization_header() -> None:
    """Jellyfin 12+ rejects X-Emby-Token; the Authorization header must be used."""
    client = JellyfinClient(url="http://jellyfin:8096", api_key="abc123")

    assert client.headers["Authorization"] == 'MediaBrowser Token="abc123"'
    assert "X-Emby-Token" not in client.headers


@pytest.mark.asyncio
async def test_trakt_client_rebuilt_when_token_refreshed() -> None:
    """A refreshed Trakt token must replace the client held by the daemon."""
    auth = _FakeTraktAuth("token-a")
    runner = _make_runner(auth)

    await _run_until_startup(runner)
    first = runner.trakt
    assert first.access_token == "token-a"

    # Same token: client is reused
    await _run_until_startup(runner)
    assert runner.trakt is first

    # Token refreshed: client is rebuilt and builder updated
    auth.token = "token-b"
    await _run_until_startup(runner)
    assert runner.trakt is not first
    assert runner.trakt.access_token == "token-b"
    assert runner.builder.trakt is runner.trakt


@pytest.mark.asyncio
async def test_trakt_client_dropped_when_token_lost() -> None:
    """If the token can no longer be refreshed, the stale client is dropped."""
    auth = _FakeTraktAuth("token-a")
    runner = _make_runner(auth)
    await _run_until_startup(runner)

    auth.token = None
    await _run_until_startup(runner)

    assert runner.trakt is None
    assert runner.builder.trakt is None


@pytest.mark.asyncio
async def test_startup_failure_is_retried_on_next_run() -> None:
    """A failed startup must not be marked as done."""
    runner = _make_runner(_FakeTraktAuth(None))
    runner.startup = SimpleNamespace(run_startup=AsyncMock(return_value=False))

    with pytest.raises(RuntimeError):
        await runner.run()

    assert runner._startup_done is False


@pytest.mark.asyncio
async def test_startup_retries_until_services_available(monkeypatch) -> None:
    """Startup should retry connection checks when required services are down."""
    sleep = AsyncMock()
    monkeypatch.setattr("jfc.services.startup.asyncio.sleep", sleep)

    service = StartupService.__new__(StartupService)
    service.radarr = None
    service.sonarr = None
    service.print_banner = lambda: None
    service.check_connections = AsyncMock(
        side_effect=[
            {"Jellyfin": False, "TMDb": True},
            {"Jellyfin": True, "TMDb": True},
        ]
    )

    assert await service.run_startup() is True
    assert service.check_connections.await_count == 2
    sleep.assert_awaited_once_with(StartupService.STARTUP_RETRY_DELAY)


@pytest.mark.asyncio
async def test_startup_gives_up_after_max_attempts(monkeypatch) -> None:
    """Startup should fail after exhausting all attempts."""
    monkeypatch.setattr("jfc.services.startup.asyncio.sleep", AsyncMock())

    service = StartupService.__new__(StartupService)
    service.print_banner = lambda: None
    service.check_connections = AsyncMock(return_value={"Jellyfin": False, "TMDb": True})

    assert await service.run_startup() is False
    assert service.check_connections.await_count == StartupService.STARTUP_MAX_ATTEMPTS
