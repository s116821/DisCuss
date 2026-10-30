from __future__ import annotations

import asyncio
import errno
import logging
import socket
import ssl
from types import SimpleNamespace
from unittest.mock import AsyncMock

import aiohttp
import discord
import pytest

from discuss.discord_adapter import DiscordListener
from discuss.service_logging import SafeFormatter
from discuss.speech import SpeechPipeline
from discuss.storage import Store
from test_runtime import Transcriber, config


def listener(path, name="primary"):
    cfg = config()
    store = Store(path)
    bot = cfg.bots[0].model_copy(update={"name": name})
    return DiscordListener(bot, cfg, store, SpeechPipeline(cfg, store, Transcriber())), store


def http_error(status):
    return discord.HTTPException(SimpleNamespace(status=status, reason="synthetic"), "private error fixture")


def gateway_error(code):
    return discord.ConnectionClosed(SimpleNamespace(close_code=code), shard_id=None, code=code)


def test_extended_boot_outage_recovers_and_reopens_real_sdk_state(tmp_path, monkeypatch, caplog):
    async def run():
        worker, store = listener(tmp_path / "state.sqlite3")
        ready_handler = worker.client.on_ready
        key = SimpleNamespace(host="invalid.example", port=443, ssl=True, is_ssl=True)
        errors = [
            aiohttp.ClientConnectorDNSError(key, OSError(11001, "synthetic DNS")),
            aiohttp.ClientConnectorError(key, OSError(22, "synthetic unavailable network")),
            ConnectionResetError(),
            TimeoutError(),
            aiohttp.ServerDisconnectedError(),
            socket.gaierror(11001, "synthetic DNS"),
            OSError(errno.ENETUNREACH, "synthetic network unreachable"),
            OSError(10051, "synthetic Windows network unreachable"),
            gateway_error(1001),
            gateway_error(1012),
            ConnectionRefusedError(),
            gateway_error(1006),
        ]
        delays, attempts, contexts, connectors = [], [], [], []

        def verified_context():
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            contexts.append(context)
            return context

        async def start(token, *, reconnect):
            # Exercise real SDK close/clear/context setup without HTTP/socket I/O.
            assert reconnect and token == worker.bot.token.get_secret_value()
            assert worker.client.loop is asyncio.get_running_loop()
            assert not worker.client.is_closed() and not worker.client.is_ready()
            connectors.append(worker.client.http.connector)
            attempts.append(1)
            if len(attempts) <= len(errors):
                raise errors[len(attempts) - 1]

        async def sleep(delay):
            delays.append(delay)

        monkeypatch.setattr(worker.client, "start", start)
        monkeypatch.setattr("discuss.discord_adapter.ssl.create_default_context", verified_context)
        monkeypatch.setattr("discuss.discord_adapter.asyncio.sleep", sleep)
        with caplog.at_level(logging.INFO, logger="discuss.discord_adapter"):
            await worker._run()
        assert len(attempts) == len(errors) + 1
        assert delays == [1, 2, 4, 8, 16] + [30] * (len(errors) - 5)
        assert worker.client.is_closed() and not worker.setup_failed
        assert worker._startup_failures == 0
        assert len(contexts) == len(attempts) == len({id(c) for c in connectors})
        assert all(c.verify_mode == ssl.CERT_REQUIRED and c.check_hostname for c in contexts)
        assert all(c.closed for c in connectors)
        assert worker.client.on_ready == ready_handler
        assert worker.tree.client is worker.client and worker.commands.get_command("standings") is not None
        failures = [r for r in caplog.records if r.msg == "gateway_connection_failed"]
        assert len(failures) == len(errors) and failures[-1].attempt > 5
        safe = "\n".join(SafeFormatter().format(r) for r in failures)
        assert "private error fixture" not in safe and worker.bot.token.get_secret_value() not in safe
        await worker.close()
        store.close()

    asyncio.run(run())


@pytest.mark.parametrize(
    "error",
    [discord.LoginFailure("synthetic"), discord.PrivilegedIntentsRequired(None)]
    + [gateway_error(code) for code in (4004, 4010, 4011, 4012, 4013, 4014)]
    + [http_error(status) for status in (400, 401, 403, 404)],
)
def test_permanent_setup_failure_does_not_retry(tmp_path, monkeypatch, error):
    async def run():
        worker, store = listener(tmp_path / "state.sqlite3")
        start = AsyncMock(side_effect=error)
        sleep = AsyncMock()
        monkeypatch.setattr(worker.client, "start", start)
        monkeypatch.setattr("discuss.discord_adapter.asyncio.sleep", sleep)
        await worker._run()
        assert worker.setup_failed and worker.client.is_closed()
        assert start.await_count == 1 and sleep.await_count == 0
        await worker.close()
        store.close()

    asyncio.run(run())


@pytest.mark.parametrize(
    "error",
    [
        aiohttp.ClientConnectorCertificateError(
            SimpleNamespace(host="invalid.example", port=443), ssl.SSLCertVerificationError(1, "synthetic certificate")
        ),
        ssl.SSLError(1, "synthetic TLS failure"),
        aiohttp.ClientPayloadError(),
        discord.GatewayNotFound(),
        http_error(500),
        http_error(503),
        http_error(429),
        gateway_error(1011),
        gateway_error(1013),
        gateway_error(4009),
        OSError(errno.EINVAL, "synthetic invalid operation"),
        PermissionError("synthetic filesystem error"),
    ],
)
def test_non_connectivity_errors_exhaust_five_attempts(tmp_path, monkeypatch, caplog, error):
    async def run():
        worker, store = listener(tmp_path / "state.sqlite3")
        start, sleep = AsyncMock(side_effect=error), AsyncMock()
        monkeypatch.setattr(worker.client, "start", start)
        monkeypatch.setattr("discuss.discord_adapter.asyncio.sleep", sleep)
        await worker._run()
        assert not worker.setup_failed and worker.client.is_closed()
        assert start.await_count == 5 and [c.args[0] for c in sleep.await_args_list] == [1, 2, 4, 8]
        assert any(r.msg == "gateway_retry_exhausted" and r.levelno == logging.ERROR for r in caplog.records)
        await worker.close()
        store.close()

    asyncio.run(run())


def test_network_outages_do_not_consume_or_reset_real_error_budget(tmp_path, monkeypatch):
    async def run():
        worker, store = listener(tmp_path / "state.sqlite3")
        errors = [http_error(503)] * 4 + [ConnectionResetError()] * 8 + [http_error(503)]
        start, sleep = AsyncMock(side_effect=errors), AsyncMock()
        monkeypatch.setattr(worker.client, "start", start)
        monkeypatch.setattr("discuss.discord_adapter.asyncio.sleep", sleep)
        await worker._run()
        assert start.await_count == 13 and sleep.await_count == 12
        assert worker._startup_failures == 5 and not worker.setup_failed
        await worker.close()
        store.close()

    asyncio.run(run())


def test_gateway_readiness_resets_real_error_budget(tmp_path, monkeypatch):
    async def run():
        worker, store = listener(tmp_path / "state.sqlite3")
        errors = [http_error(503)] * 8
        attempts = 0

        async def start(*args, **kwargs):
            nonlocal attempts
            attempts += 1
            if attempts == 5:
                # Exercise the real ready event without command-sync HTTP I/O.
                worker.config = worker.config.model_copy(update={"servers": []})
                await worker.client.on_ready()
            if attempts <= len(errors):
                raise errors[attempts - 1]

        monkeypatch.setattr(worker.client, "start", start)
        monkeypatch.setattr("discuss.discord_adapter.asyncio.sleep", AsyncMock())
        await worker._run()
        assert attempts == 9 and worker._startup_failures == 4 and not worker.setup_failed
        await worker.close()
        store.close()

    asyncio.run(run())


def test_backoff_cancels_without_stopping_a_healthy_peer(tmp_path, monkeypatch):
    async def run():
        failed, failed_store = listener(tmp_path / "failed.sqlite3")
        healthy, healthy_store = listener(tmp_path / "healthy.sqlite3", "secondary")
        waiting, ready = asyncio.Event(), asyncio.Event()
        failed_start = AsyncMock(side_effect=ConnectionResetError("synthetic outage"))

        async def sleep(delay):
            waiting.set()
            await asyncio.Event().wait()

        async def healthy_start(token, *, reconnect):
            ready.set()
            await asyncio.Event().wait()

        monkeypatch.setattr(failed.client, "start", failed_start)
        monkeypatch.setattr(healthy.client, "start", healthy_start)
        monkeypatch.setattr("discuss.discord_adapter.asyncio.sleep", sleep)
        failed.start()
        healthy.start()
        await asyncio.wait_for(waiting.wait(), 1)
        await asyncio.wait_for(ready.wait(), 1)
        await failed.close()
        assert failed._task.done() and failed_start.await_count == 1
        assert not healthy._task.done() and not healthy.setup_failed
        await healthy.close()
        assert healthy.client.is_closed()
        failed_store.close()
        healthy_store.close()

    asyncio.run(run())


def test_unexpected_fault_propagates_after_sdk_cleanup(tmp_path, monkeypatch):
    async def run():
        worker, store = listener(tmp_path / "state.sqlite3")
        monkeypatch.setattr(worker.client, "start", AsyncMock(side_effect=RuntimeError("synthetic bug")))
        with pytest.raises(RuntimeError, match="synthetic bug"):
            await worker._run()
        assert worker.client.is_closed() and not worker.setup_failed
        await worker.close()
        store.close()

    asyncio.run(run())
