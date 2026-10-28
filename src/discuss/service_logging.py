"""Content-safe operational events with native OS sinks and bounded file fallback."""

from __future__ import annotations

import ctypes
import json
import logging
import math
import os
import re
import sys
import threading
import traceback
from datetime import UTC, datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from types import TracebackType

from .config import Config, check_private_file

FIELDS = frozenset(
    "identity server channel previous_channel reason attempt delay_seconds code status errno "
    "error_type queue_depth processed_chunks speech_failures playback_started playback_failures "
    "dropped_chunks interval_seconds mode configured_level version duration_seconds healthy listeners_ready "
    "playback_skipped".split()
)


class SafeFormatter(logging.Formatter):
    def __init__(self, *, journal: bool = False) -> None:
        super().__init__()
        self.journal = journal
        self.secrets: tuple[str, ...] = ()

    def clean(self, value: str) -> str:
        for secret in self.secrets:
            value = value.replace(secret, "[redacted]")
        return value[:300]

    def format(self, record: logging.LogRecord) -> str:
        # Only our controlled event identifiers are retained. SDK messages may contain speech or URLs.
        own = record.name == "discuss" or record.name.startswith("discuss.")
        event = str(record.msg) if own and not record.args else "library_diagnostic"
        if not re.fullmatch(r"[a-z][a-z0-9_]{0,79}", event):
            event = "application_diagnostic" if own else "library_diagnostic"
        data: dict[str, object] = {
            "timestamp": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": "ERROR" if record.levelno >= logging.ERROR else record.levelname,
            "event": event,
            "logger": self.clean(record.name),
            "pid": os.getpid(),
        }
        if own:
            for field in FIELDS:
                value = getattr(record, field, None)
                if isinstance(value, (str, int, float, bool)):
                    if isinstance(value, float) and not math.isfinite(value):
                        continue
                    data[field] = self.clean(value) if isinstance(value, str) else value
        else:
            code = re.search(r"(?:code|clos(?:e|ed))\D{0,15}(\d{3,5})\b", record.getMessage(), re.I)
            if code:
                data["code"] = int(code.group(1))
        if record.exc_info and record.exc_info[1] is not None:
            error = record.exc_info[1]
            data["error_type"] = type(error).__name__
            for field in ("code", "status", "errno"):
                value = getattr(error, field, None)
                if isinstance(value, int):
                    data[field] = value
            data["stack"] = [
                f"{self.clean(Path(frame.filename).name)}:{frame.lineno}:{self.clean(frame.name)}"
                for frame in traceback.extract_tb(record.exc_info[2], limit=-8)
            ]
        text = json.dumps(data, ensure_ascii=True, allow_nan=False)
        if self.journal:
            priority = 3 if record.levelno >= logging.ERROR else 4 if record.levelno >= logging.WARNING else 6
            text = f"<{priority}>" + text
        return text


class WindowsEventHandler(logging.Handler):
    """Write a registered Application source through the OS API, without pywin32."""

    def __init__(self, source: str = "DisCuss") -> None:
        super().__init__()
        from ctypes import wintypes

        api = ctypes.WinDLL("advapi32", use_last_error=True)
        self.register = api.RegisterEventSourceW
        self.register.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]
        self.register.restype = wintypes.HANDLE
        self.report = api.ReportEventW
        self.report.argtypes = [
            wintypes.HANDLE,
            wintypes.WORD,
            wintypes.WORD,
            wintypes.DWORD,
            ctypes.c_void_p,
            wintypes.WORD,
            wintypes.DWORD,
            ctypes.POINTER(wintypes.LPCWSTR),
            ctypes.c_void_p,
        ]
        self.report.restype = wintypes.BOOL
        self.deregister = api.DeregisterEventSource
        self.deregister.argtypes = [wintypes.HANDLE]
        self.deregister.restype = wintypes.BOOL
        self.event_handle = self.register(None, source)
        if not self.event_handle:
            raise ctypes.WinError(ctypes.get_last_error())
        self.failed = False

    def emit(self, record: logging.LogRecord) -> None:
        if self.failed:
            return
        try:
            kind = 1 if record.levelno >= logging.ERROR else 2 if record.levelno >= logging.WARNING else 4
            strings = (ctypes.c_wchar_p * 1)(self.format(record))
            if not self.report(self.event_handle, kind, 0, 0, None, 1, 0, strings, None):
                raise ctypes.WinError(ctypes.get_last_error())
        except OSError:
            self.failed = True
            logging.getLogger(__name__).warning("native_logging_unavailable", exc_info=True)

    def close(self) -> None:
        if getattr(self, "event_handle", None):
            self.deregister(self.event_handle)
            self.event_handle = None
        super().close()


class SafeStreamHandler(logging.StreamHandler):
    def handleError(self, record: logging.LogRecord) -> None:
        # The default logging failure path dumps the original, potentially private record.
        return


class OperationalFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        own = record.name == "discuss" or record.name.startswith("discuss.")
        return own or record.levelno >= logging.WARNING


class SafeFileHandler(RotatingFileHandler):
    failed = False

    def emit(self, record: logging.LogRecord) -> None:
        if not self.failed:
            super().emit(record)

    def handleError(self, record: logging.LogRecord) -> None:
        if not self.failed:
            self.failed = True
            logging.getLogger(__name__).error("file_logging_failed", exc_info=True)


def update_logging(config: Config) -> None:
    for handler in logging.getLogger().handlers:
        if getattr(handler, "discuss_handler", False):
            handler.setLevel(config.logging.level)
            if isinstance(handler.formatter, SafeFormatter):
                handler.formatter.secrets = tuple(b.token.get_secret_value() for b in config.bots)


class ServiceLogging:
    def __init__(self, path: Path | None = None, *, native: bool = True) -> None:
        self.path, self.native = path, native
        self.handlers: list[logging.Handler] = []
        self.config: Config | None = None

    def add(self, handler: logging.Handler, *, journal: bool = False) -> None:
        setattr(handler, "discuss_handler", True)
        handler.setFormatter(SafeFormatter(journal=journal))
        handler.addFilter(OperationalFilter())
        handler.setLevel(self.config.logging.level if self.config else "INFO")
        self.handlers.append(handler)
        logging.getLogger().addHandler(handler)
        if self.config:
            update_logging(self.config)

    def file(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        descriptor = os.open(path, os.O_CREAT | os.O_APPEND | os.O_WRONLY, 0o600)
        os.close(descriptor)
        check_private_file(path)
        self.add(SafeFileHandler(path, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"))

    def configure(self, config: Config, state: Path) -> None:
        self.config = config
        update_logging(config)
        if self.path is None:
            self.path = state / "runtime.log"
            self.file(self.path)

    def __enter__(self) -> ServiceLogging:
        root = logging.getLogger()
        self.previous = root.handlers[:], root.level
        self.previous_hooks = sys.excepthook, threading.excepthook

        def unhandled(kind, error, tb):
            logging.getLogger(__name__).error("unhandled_exception", exc_info=(kind, error, tb))

        def thread_failed(args):
            logging.getLogger(__name__).error(
                "thread_failed", exc_info=(args.exc_type, args.exc_value, args.exc_traceback)
            )

        sys.excepthook, threading.excepthook = unhandled, thread_failed
        root.handlers = []
        root.setLevel(logging.INFO)
        self.library_levels = {name: logging.getLogger(name).level for name in ("discord", "faster_whisper")}
        for name in self.library_levels:
            logging.getLogger(name).setLevel(logging.WARNING)
        self.add(SafeStreamHandler(), journal=bool(os.environ.get("JOURNAL_STREAM")) and sys.platform != "win32")
        try:
            if self.path:
                self.file(self.path)
            if self.native and sys.platform == "win32":
                try:
                    self.add(WindowsEventHandler())
                except OSError:
                    logging.getLogger(__name__).warning("native_logging_unavailable", exc_info=True)
        except BaseException:
            self.__exit__(*sys.exc_info())
            raise
        return self

    def __exit__(self, kind: type[BaseException] | None, error: BaseException | None, tb: TracebackType | None) -> None:
        root = logging.getLogger()
        for handler in self.handlers:
            root.removeHandler(handler)
            handler.close()
        root.handlers, previous_level = self.previous
        root.setLevel(previous_level)
        sys.excepthook, threading.excepthook = self.previous_hooks
        for name, level in self.library_levels.items():
            logging.getLogger(name).setLevel(level)
