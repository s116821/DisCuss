"""Typed machine-local JSON contract and secret-safe setup validation."""

from __future__ import annotations

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
    excluded_member_ids: list[Snowflake] = Field(default_factory=list)
    listening_notice: str = Field(
        default="DisCuss processes voice locally for profanity standings; audio and full "
        "transcripts are discarded. Use opt-out or ask an administrator to disable "
        "monitoring or delete your local data.",
        min_length=20,
        max_length=1000,
    )


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

    @model_validator(mode="after")
    def consistent_policy(self) -> Self:
        if self.monitoring_enabled and not self.privacy.notice_acknowledged:
            raise ValueError("Acknowledge a visible processing notice before enabling monitoring")
        if len(set(self.voice_channels)) != len(self.voice_channels):
            raise ValueError("Eligible voice channels must be unique")
        if self.mode == "head_hunt":
            if not self.voice_channels or self.assignments:
                raise ValueError("Head Hunt requires eligible channels and no fixed assignments")
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


class Config(Model):
    schema_version: Literal[1] = 1
    bots: list[Bot] = Field(min_length=1, max_length=128)
    servers: list[Server] = Field(min_length=1, max_length=1000)
    state_dir: str = Field(default="state", min_length=1)

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
        result = subprocess.run(["pwsh", "-File", str(script), str(path)], capture_output=True)
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
