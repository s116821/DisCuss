"""Typed machine-local JSON contract and secret-safe setup validation."""

from __future__ import annotations

import logging
import os
import subprocess
from pathlib import Path
from typing import Annotated, Literal, Self
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    SecretStr,
    StringConstraints,
    ValidationError,
    field_validator,
    model_validator,
)


def valid_identifier(value: str) -> str:
    if int(value) >= 2**64:
        raise ValueError("Discord identifier exceeds supported range")
    return value


Snowflake = Annotated[str, StringConstraints(pattern=r"^[1-9][0-9]{0,19}$"), AfterValidator(valid_identifier)]
BotName = Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9_-]{0,31}$")]


class ConfigError(ValueError):
    """Setup failure safe to show in an operator message."""


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)


class Bot(Model):
    name: BotName
    token: SecretStr
    enabled: bool = True

    @model_validator(mode="after")
    def usable_token(self) -> Self:
        token = self.token.get_secret_value()
        if self.enabled and (len(token) < 40 or token.upper().startswith(("REPLACE", "YOUR_", "TOKEN"))):
            raise ValueError("Enabled bot requires a real bot token in protected local JSON")
        return self


class HeadHunt(Model):
    all_channels: bool = False
    excluded_channel_ids: list[Snowflake] = Field(default_factory=list)
    interval_seconds: float = Field(default=600, ge=1, le=86400)
    priority_member_ids: list[Snowflake] = Field(default_factory=list, max_length=10000)
    maximum_weight: float = Field(default=10, ge=0, le=1000000)
    minimum_weight: float = Field(default=1, ge=0, le=1000000)
    default_weight: float = Field(default=1, ge=0, le=1000000)

    @model_validator(mode="after")
    def weights(self) -> Self:
        if self.minimum_weight > self.maximum_weight:
            raise ValueError("Minimum priority weight exceeds maximum")
        if len(set(self.priority_member_ids)) != len(self.priority_member_ids):
            raise ValueError("Priority members must be unique and ordered")
        if len(set(self.excluded_channel_ids)) != len(self.excluded_channel_ids):
            raise ValueError("Excluded voice channels must be unique")
        return self


class FixedAssignment(Model):
    bot: BotName
    channel_id: Snowflake


class Profanity(Model):
    use_builtin_list: bool = True
    custom_words: list[str] = Field(default_factory=list, max_length=10000)

    @field_validator("custom_words")
    @classmethod
    def custom_entries(cls, values: list[str]) -> list[str]:
        for value in values:
            if len(value) > 100 or not any(c.isalpha() for c in value):
                raise ValueError("Custom tracked entries need letters and at most 100 characters")
        return values


class Scaled(Model):
    enabled: bool = True
    minimum_monitored_seconds: float = Field(default=1800, ge=0, le=31622400)


class Cadences(Model):
    day: bool = False
    week: bool = True
    month: bool = True
    year: bool = True

    def enabled_periods(self) -> list[str]:
        return [name for name in ("day", "week", "month", "year") if getattr(self, name)]


class Leaderboards(Model):
    report_channel_id: Snowflake | None = None
    timezone: str = "UTC"
    sort_order: Literal["ascending", "descending"] = "descending"
    scaled: Scaled = Field(default_factory=Scaled)
    reports: Cadences = Field(default_factory=Cadences)
    suppress_empty_reports: bool = True
    retention_days_when_reports_disabled: int = Field(default=30, ge=1, le=366)

    @field_validator("timezone")
    @classmethod
    def known_zone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError):
            raise ValueError("Unknown reporting timezone") from None
        return value


class Privacy(Model):
    notice_acknowledged: bool = False
    context_reporting_acknowledged: bool = False
    excluded_member_ids: list[Snowflake] = Field(default_factory=list)
    listening_notice: str = Field(
        default="DisCuss counts voice profanity locally; audio/transcripts are discarded; "
        "/discuss opt_out or opt_in controls your participation.",
        min_length=20,
        max_length=1000,
    )


class DetectionReporting(Model):
    enabled: bool = False
    channel_id: Snowflake | None = None
    context_words_per_side: int = Field(default=3, ge=0, le=20)
    interval_seconds: float = Field(default=0, ge=0, le=3600)
    max_pending_instances: int = Field(default=1000, ge=1, le=4096)
    max_pending_bytes: int = Field(default=1048576, ge=1024, le=4194304)
    max_pending_age_seconds: float = Field(default=300, ge=1, le=3600)
    max_pages_per_flush: int = Field(default=10, ge=1, le=50)

    @model_validator(mode="after")
    def age_covers_interval(self) -> Self:
        if self.max_pending_age_seconds < self.interval_seconds:
            raise ValueError("Detection queue age must cover the reporting interval")
        return self


class Playback(Model):
    enabled: bool = False
    interval_seconds: float = Field(default=900, ge=5, le=86400)
    mode: Literal["random", "cadence", "first_curse"] = "random"
    max_clip_seconds: float = Field(default=8, ge=0.2, le=15)
    context_seconds: float = Field(default=1.5, ge=0, le=5)

    @property
    def cadence_timing(self) -> bool:
        return self.mode == "cadence" or self.interval_seconds < 60

    @model_validator(mode="after")
    def safe_timing(self) -> Self:
        if self.mode == "random" and self.interval_seconds < 60:
            logging.getLogger(__name__).warning("Playback interval is too short for random timing; using cadence mode.")
            self.mode = "cadence"
        elif self.mode == "first_curse" and self.interval_seconds < 60:
            logging.getLogger(__name__).warning(
                "Playback interval is too short for random timing; using cadence timing with first-curse eligibility."
            )
        return self


class Server(Model):
    server_id: Snowflake
    primary_bot: BotName
    report_channel_id: Snowflake
    mode: Literal["head_hunt", "fixed_channels"] = "head_hunt"
    monitoring_enabled: bool = True
    voice_channels: list[Snowflake] = Field(default_factory=list)
    head_hunt: HeadHunt = Field(default_factory=HeadHunt)
    assignments: list[FixedAssignment] = Field(default_factory=list)
    profanity: Profanity = Field(default_factory=Profanity)
    leaderboards: Leaderboards = Field(default_factory=Leaderboards)
    privacy: Privacy = Field(default_factory=Privacy)
    detection_reporting: DetectionReporting = Field(default_factory=DetectionReporting)
    playback: Playback = Field(default_factory=Playback)

    @model_validator(mode="after")
    def consistent_policy(self) -> Self:
        if self.monitoring_enabled and not self.privacy.notice_acknowledged:
            raise ValueError("Acknowledge a visible processing notice before enabling monitoring")
        if self.detection_reporting.enabled and not self.privacy.context_reporting_acknowledged:
            raise ValueError("Acknowledge contextual excerpt publication before enabling detection reporting")
        if len(set(self.voice_channels)) != len(self.voice_channels):
            raise ValueError("Eligible voice channels must be unique")
        if self.mode == "head_hunt":
            if self.assignments:
                raise ValueError("Head Hunt cannot have fixed assignments")
            if self.head_hunt.all_channels and self.voice_channels:
                raise ValueError("Automatic Head Hunt cannot also have an explicit voice channel list")
            if not self.head_hunt.all_channels and not self.voice_channels:
                raise ValueError("Head Hunt requires eligible channels or automatic all-channel discovery")
        else:
            if not self.assignments:
                raise ValueError("Fixed Channels requires assignments")
            bots = [a.bot for a in self.assignments]
            channels = [a.channel_id for a in self.assignments]
            if len(set(bots)) != len(bots) or len(set(channels)) != len(channels):
                raise ValueError("Duplicate bot or channel assignment in this server")
            if self.primary_bot not in bots:
                raise ValueError("Fixed Channels must assign the primary bot")
        return self


class Transcription(Model):
    model_id: Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")] = (
        "Systran/faster-whisper-small"
    )
    revision: Annotated[str, StringConstraints(pattern=r"^[a-f0-9]{40}$")] = "536b0662742c02347bc0e980a01041f333bce120"
    device: Literal["cpu", "cuda"] = "cpu"
    compute_type: Literal["int8", "float16", "int8_float16", "float32"] = "int8"
    cpu_threads: int = Field(default=2, ge=1, le=64)
    language: str | None = "en"
    max_queue: int = Field(default=8, ge=1, le=128)
    max_speakers: int = Field(default=64, ge=1, le=128)
    max_buffer_bytes: int = Field(default=16777216, ge=192000, le=268435456)
    max_chunk_seconds: float = Field(default=12, ge=0.1, le=30)
    minimum_chunk_seconds: float = Field(default=0.15, ge=0.02, le=2)
    silence_seconds: float = Field(default=0.5, ge=0.1, le=5)
    vad_threshold: float = Field(default=0.003, ge=0, le=1)

    @model_validator(mode="after")
    def chunk_limits(self) -> Self:
        if self.minimum_chunk_seconds > self.max_chunk_seconds:
            raise ValueError("Minimum speech chunk duration exceeds maximum")
        return self


class Config(Model):
    schema_version: Literal[1] = 1
    bots: list[Bot] = Field(min_length=1, max_length=128)
    servers: list[Server] = Field(min_length=1, max_length=1000)
    state_dir: str = Field(default="state", min_length=1)
    transcription: Transcription = Field(default_factory=Transcription)

    @model_validator(mode="after")
    def identities(self) -> Self:
        names = [bot.name for bot in self.bots]
        enabled = {bot.name for bot in self.bots if bot.enabled}
        tokens = [bot.token.get_secret_value() for bot in self.bots if bot.enabled]
        if len(set(names)) != len(names) or len(set(tokens)) != len(tokens):
            raise ValueError("Bot names and enabled credentials must be unique")
        if len({s.server_id for s in self.servers}) != len(self.servers):
            raise ValueError("Each server must have one policy")
        for server in self.servers:
            references = {server.primary_bot, *(a.bot for a in server.assignments)}
            if not references <= enabled:
                raise ValueError("Unknown or disabled bot reference")
        return self


def validate_config(text: str) -> Config:
    try:
        return Config.model_validate_json(text)
    except ValidationError as error:
        known = set()
        schema = Config.model_json_schema()
        for model in [schema, *schema.get("$defs", {}).values()]:
            known.update(model.get("properties", {}))
        messages = []
        for issue in error.errors(include_input=False, include_url=False):
            location = ".".join(str(p) if isinstance(p, int) or p in known else "<field>" for p in issue["loc"])
            messages.append(f"{location or 'configuration'}: {issue['msg']}")
        raise ConfigError("; ".join(messages)) from None


def check_private_file(path: Path) -> None:
    if os.name == "nt":
        script = Path(__file__).with_name("check_acl.ps1")
        # Use the Windows-provided shell for this read-only ACL query; runtime
        # installation must not require a separate PowerShell 7 installation.
        shell = Path(os.environ["SystemRoot"]) / "System32/WindowsPowerShell/v1.0/powershell.exe"
        code = script.read_text(encoding="utf-8").replace("param([string] $Path)", "$Path = $env:DISCUSS_ACL_PATH", 1)
        # A PowerShell 7 parent can pass its module path to Windows PowerShell.
        # Load the OS shell's own security module explicitly instead.
        security = shell.parent / "Modules/Microsoft.PowerShell.Security/Microsoft.PowerShell.Security.psd1"
        code = "Import-Module -Name $env:DISCUSS_ACL_MODULE -ErrorAction Stop\n" + code
        environment = dict(os.environ, DISCUSS_ACL_PATH=str(path.resolve()))
        environment["DISCUSS_ACL_MODULE"] = str(security)
        result = subprocess.run([str(shell), "-Command", code], env=environment, capture_output=True)
        if result.returncode != 0:
            raise ConfigError("Restrict local file NTFS read access to the runtime identity, SYSTEM and administrators")
    elif path.stat().st_mode & 0o077:
        raise ConfigError("Restrict local file permissions to 0600 before startup")


def load_config(path: Path) -> Config:
    if not path.is_file():
        raise ConfigError("Configuration is missing; copy config.example.json to protected local JSON and finish setup")
    check_private_file(path)
    try:
        text = path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeError):
        raise ConfigError("Configuration cannot be read as UTF-8 JSON") from None
    return validate_config(text)
