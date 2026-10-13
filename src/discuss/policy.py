"""Deterministic server monitoring policy independent of the Discord SDK."""

from __future__ import annotations

import math
import random
from dataclasses import dataclass

from .config import HeadHunt, Server


@dataclass(frozen=True, slots=True)
class MemberPresence:
    member_id: str
    is_bot: bool = False
    can_transmit: bool = True


@dataclass(frozen=True, slots=True)
class ChannelPresence:
    channel_id: str
    members: tuple[MemberPresence, ...]
    permitted: bool = True
    full: bool = False


def weights(settings: HeadHunt) -> dict[str, float]:
    members = settings.priority_member_ids
    if len(members) == 1:
        return {members[0]: settings.maximum_weight}
    return {
        member: settings.maximum_weight - i * (settings.maximum_weight - settings.minimum_weight) / (len(members) - 1)
        for i, member in enumerate(members)
    }


def affinities(server: Server, channels: list[ChannelPresence]) -> dict[str, float]:
    priority = weights(server.head_hunt)
    excluded = set(server.privacy.excluded_member_ids)
    scores = {}
    for channel in sorted(channels, key=lambda c: int(c.channel_id)):
        if channel.channel_id not in server.voice_channels or not channel.permitted or channel.full:
            continue
        humans = {
            m.member_id for m in channel.members if not m.is_bot and m.can_transmit and m.member_id not in excluded
        }
        score = math.fsum(priority.get(member, server.head_hunt.default_weight) for member in humans)
        if humans and score > 0:
            scores[channel.channel_id] = score
    return scores


def choose_channel(server: Server, channels: list[ChannelPresence], draw: float | None = None) -> str | None:
    scores = affinities(server, channels)
    total = math.fsum(scores.values())
    if total == 0 or not server.monitoring_enabled:
        return None
    value = random.random() if draw is None else draw
    if not math.isfinite(value) or not 0 <= value < 1:
        raise ValueError("Random draw must be within [0, 1)")
    threshold = value * total
    cumulative = 0.0
    for channel, score in scores.items():
        cumulative += score
        if threshold < cumulative:
            return channel
    return next(reversed(scores))


def fixed_assignments(server: Server, channels: list[ChannelPresence]) -> dict[str, str]:
    eligible = {
        c.channel_id
        for c in channels
        if c.permitted
        and not c.full
        and any(
            not m.is_bot and m.can_transmit and m.member_id not in server.privacy.excluded_member_ids for m in c.members
        )
    }
    return (
        {a.bot: a.channel_id for a in server.assignments if a.channel_id in eligible}
        if server.monitoring_enabled
        else {}
    )
