from __future__ import annotations

import json
import random
from pathlib import Path

import pytest

from discuss.cli import main
from discuss.config import ConfigError, HeadHunt, validate_config
from discuss.policy import ChannelPresence, MemberPresence, affinities, choose_channel, fixed_assignments, weights

SECRET = "offline-fixture-" + "x" * 64


def config_data() -> dict:
    return {
        "bots": [{"name": "primary", "token": SECRET}],
        "servers": [
            {
                "server_id": "1",
                "primary_bot": "primary",
                "report_channel_id": "99",
                "voice_channels": ["10", "20"],
                "privacy": {"notice_acknowledged": True},
            }
        ],
    }


def server():
    return validate_config(json.dumps(config_data())).servers[0]


def test_defaults_and_schema_secret_redaction() -> None:
    config = validate_config(json.dumps(config_data()))
    policy = config.servers[0]
    assert policy.mode == "head_hunt" and policy.head_hunt.interval_seconds == 600
    assert policy.leaderboards.reports.enabled_periods() == ["week", "month", "year"]
    assert policy.leaderboards.scaled.minimum_monitored_seconds == 1800
    assert policy.leaderboards.sort_order == "descending"
    assert SECRET not in repr(config) and SECRET not in config.model_dump_json()


@pytest.mark.parametrize(
    "change",
    [
        lambda d: d.update(schema_version=2),
        lambda d: d["bots"][0].update(token="REPLACE_TOKEN"),
        lambda d: d["bots"][0].update(token={"secret": SECRET}),
        lambda d: d["servers"][0].update(primary_bot="unknown"),
        lambda d: d["servers"][0]["privacy"].update(notice_acknowledged=False),
        lambda d: d["servers"][0].update(server_id=str(2**64)),
        lambda d: d["servers"][0].update(voice_channels=[str(2**64)]),
        lambda d: d["servers"][0].update(head_hunt={"minimum_weight": 11, "maximum_weight": 10}),
        lambda d: d["servers"][0].update(leaderboards={"timezone": "Unknown/NotReal"}),
        lambda d: d["servers"].append(d["servers"][0].copy()),
        lambda d: d.update(**{SECRET: SECRET}),
    ],
)
def test_invalid_configuration_never_echoes_secrets(change) -> None:
    data = config_data()
    change(data)
    with pytest.raises(ConfigError) as caught:
        validate_config(json.dumps(data))
    assert SECRET not in str(caught.value)


def test_fixed_modes_and_duplicate_identity_assignments() -> None:
    data = config_data()
    data["bots"].append({"name": "secondary", "token": "second-offline-fixture-" + "y" * 64})
    data["servers"][0].update(
        mode="fixed_channels",
        assignments=[{"bot": "primary", "channel_id": "10"}, {"bot": "secondary", "channel_id": "20"}],
    )
    config = validate_config(json.dumps(data))
    channels = [ChannelPresence("10", (MemberPresence("100"),)), ChannelPresence("20", (MemberPresence("200"),))]
    assert fixed_assignments(config.servers[0], channels) == {"primary": "10", "secondary": "20"}
    data["servers"][0]["assignments"][1]["channel_id"] = "10"
    with pytest.raises(ConfigError, match="Duplicate"):
        validate_config(json.dumps(data))
    data["servers"][0]["assignments"][1]["channel_id"] = "20"
    data["bots"][1]["token"] = SECRET
    with pytest.raises(ConfigError, match="unique"):
        validate_config(json.dumps(data))


def test_affinity_interpolation_exclusions_and_boundaries() -> None:
    policy = server()
    policy.head_hunt.priority_member_ids = ["100", "200", "300"]
    assert weights(policy.head_hunt) == {"100": 10, "200": 5.5, "300": 1}
    assert weights(HeadHunt(priority_member_ids=["100"])) == {"100": 10}
    channels = [
        ChannelPresence("10", (MemberPresence("100"), MemberPresence("400"), MemberPresence("100"))),
        ChannelPresence("20", (MemberPresence("300"), MemberPresence("999", is_bot=True))),
        ChannelPresence("30", (MemberPresence("100"),)),
    ]
    assert affinities(policy, channels) == {"10": 11, "20": 1}
    assert choose_channel(policy, channels, 0) == "10"
    assert choose_channel(policy, channels, 11 / 12) == "20"
    policy.privacy.excluded_member_ids = ["100"]
    assert affinities(policy, channels) == {"10": 1, "20": 1}
    channels[0] = ChannelPresence("10", (MemberPresence("100"),), full=True)
    channels[1] = ChannelPresence("20", (MemberPresence("300"),), permitted=False)
    assert choose_channel(policy, channels, 0.5) is None
    policy.head_hunt = HeadHunt(maximum_weight=0, minimum_weight=0, default_weight=0)
    assert choose_channel(policy, [ChannelPresence("10", (MemberPresence("500"),))], 0.5) is None


def test_affinity_statistical_proportions() -> None:
    policy = server()
    channels = [
        ChannelPresence("10", (MemberPresence("1"),)),
        ChannelPresence("20", (MemberPresence("2"), MemberPresence("3"), MemberPresence("4"))),
    ]
    rng = random.Random(182)
    count = sum(choose_channel(policy, channels, rng.random()) == "20" for _ in range(20000))
    assert abs(count / 20000 - 0.75) < 0.02


def test_doctor_missing_and_valid_config(tmp_path: Path, monkeypatch, capsys) -> None:
    assert main(["--config", str(tmp_path / "missing.json"), "doctor"]) == 2
    path = tmp_path / "config.json"
    path.write_text(json.dumps(config_data()), encoding="utf-8")
    monkeypatch.setattr("discuss.config.check_private_file", lambda p: None)
    assert main(["--config", str(path), "doctor"]) == 0
    output = capsys.readouterr().out
    assert SECRET not in output and "Offline preflight" in output


def test_checked_in_example_and_schema_are_current() -> None:
    from discuss.config import Config

    root = Path(__file__).resolve().parents[1]
    assert json.loads((root / "config.schema.json").read_text(encoding="utf-8")) == Config.model_json_schema()
    example = json.loads((root / "config.example.json").read_text(encoding="utf-8"))
    assert example["bots"][0]["token"].startswith("REPLACE")
    example["bots"][0]["token"] = SECRET
    example["servers"][0]["privacy"]["notice_acknowledged"] = True
    validate_config(json.dumps(example))
