#!/usr/bin/env python3
"""Read HDD temperatures, publish them to Home Assistant, and send Bark alerts."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from urllib.parse import quote

import requests


SCRIPT_DIR = Path(__file__).resolve().parent
ENV_FILE = SCRIPT_DIR / ".env"

DISKS = (
    {
        "path": "/dev/sdb",
        "entity_id": "input_number.disk_temp_sdb",
        "alert_entity_id": "input_select.hdd_temp_alert_sdb",
        "label": "14TB Exos X16",
        "warm": 45,
    },
    {
        "path": "/dev/sdc",
        "entity_id": "input_number.disk_temp_sdc",
        "alert_entity_id": "input_select.hdd_temp_alert_sdc",
        "label": "6TB SkyHawk",
        "warm": None,
    },
)

LEVEL_RANK = {"normal": 0, "warm": 1, "danger": 2, "critical": 3}
LEVEL_TITLE = {
    "warm": "HDD温度偏高",
    "danger": "HDD温度危险预警",
    "critical": "HDD温度严重告警",
}


def load_env(path: Path) -> None:
    """Load a small KEY=VALUE file without executing it as shell code."""
    if not path.is_file():
        raise RuntimeError(f"缺少配置文件：{path}")

    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        key, separator, value = line.partition("=")
        if not separator or not key.strip():
            raise RuntimeError(f"{path}:{line_number} 不是有效的 KEY=VALUE")
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        os.environ.setdefault(key.strip(), value)


def require_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"{ENV_FILE} 缺少 {name}")
    return value


def get_disk_temp(disk: str) -> int:
    result = subprocess.run(
        ["smartctl", "-j", "-A", disk],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
        timeout=30,
    )
    try:
        payload = json.loads(result.stdout)
        temperature = int(payload["temperature"]["current"])
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        detail = result.stderr.strip() or "smartctl 未返回温度"
        raise RuntimeError(f"读取 {disk} 失败：{detail}") from exc
    if not 0 <= temperature <= 100:
        raise RuntimeError(f"{disk} 返回异常温度：{temperature}°C")
    return temperature


class HomeAssistantClient:
    def __init__(self, base_url: str, token: str) -> None:
        # Accept both the old full action URL and the preferred HA base URL.
        self.base_url = base_url.split("/api/", 1)[0].rstrip("/")
        self.session = requests.Session()
        self.session.headers.update(
            {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        )

    def get_state(self, entity_id: str) -> str | None:
        response = self.session.get(
            f"{self.base_url}/api/states/{entity_id}", timeout=20
        )
        if response.status_code == 404:
            return None
        response.raise_for_status()
        return response.json().get("state")

    def set_temperature(self, entity_id: str, temperature: int) -> None:
        response = self.session.post(
            f"{self.base_url}/api/services/input_number/set_value",
            json={"entity_id": entity_id, "value": temperature},
            timeout=20,
        )
        response.raise_for_status()

    def set_alert_level(self, entity_id: str, level: str) -> None:
        response = self.session.post(
            f"{self.base_url}/api/services/input_select/select_option",
            json={"entity_id": entity_id, "option": level},
            timeout=20,
        )
        response.raise_for_status()


def desired_level(temperature: int, previous: str, warm_threshold: int | None) -> str:
    """Apply rising thresholds plus hysteresis based on HA's persisted alert state."""
    if temperature >= 55:
        return "critical"
    if previous == "critical" and temperature >= 53:
        return "critical"

    if temperature >= 50:
        return "danger"
    if previous == "danger" and temperature >= 48:
        return "danger"

    if warm_threshold is not None:
        if temperature >= warm_threshold:
            return "warm"
        if previous == "warm" and temperature >= warm_threshold - 2:
            return "warm"

    return "normal"


def notify_bark(server: str, token: str, title: str, body: str) -> None:
    url = f"https://{server}/{token}/{quote(title, safe='')}/{quote(body, safe='')}"
    response = requests.get(url, params={"group": "Server"}, timeout=20)
    response.raise_for_status()


def alert_body(hostname: str, disk: dict, temperature: int, level: str) -> str:
    if level == "critical":
        advice = "已接近硬盘温度极限，请立即检查散热和负载"
    elif level == "danger":
        advice = "请检查机箱风扇、风道和硬盘负载"
    else:
        advice = "已超过建议温度，建议检查散热"
    return f"{hostname} {disk['path']} {disk['label']} 当前{temperature}°C；{advice}"


def run_monitor(ha: HomeAssistantClient, bark_server: str, bark_token: str) -> int:
    hostname = os.uname().nodename
    failures = 0

    for disk in DISKS:
        try:
            temperature = get_disk_temp(disk["path"])
            previous_level = ha.get_state(disk["alert_entity_id"])
            if previous_level not in LEVEL_RANK:
                previous_level = "normal"

            ha.set_temperature(disk["entity_id"], temperature)
            level = desired_level(temperature, previous_level, disk["warm"])

            if LEVEL_RANK[level] > LEVEL_RANK[previous_level]:
                notify_bark(
                    bark_server,
                    bark_token,
                    LEVEL_TITLE[level],
                    alert_body(hostname, disk, temperature, level),
                )
                print(f"Bark alert: {disk['path']} {previous_level} -> {level}")
            elif level == "normal" and previous_level != "normal":
                notify_bark(
                    bark_server,
                    bark_token,
                    "HDD温度已恢复",
                    f"{hostname} {disk['path']} {disk['label']} 已降至{temperature}°C",
                )
                print(f"Bark recovery: {disk['path']} {previous_level} -> normal")

            if level != previous_level:
                # Update HA only after Bark succeeds, so a failed notification is retried.
                ha.set_alert_level(disk["alert_entity_id"], level)

            print(
                f"Set {disk['entity_id']}: {temperature}°C; "
                f"alert_level={level}"
            )
        except Exception as exc:  # Keep the other disk updating if one disk fails.
            failures += 1
            print(f"ERROR {disk['path']}: {exc}", file=sys.stderr)

    return 1 if failures else 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--check", action="store_true", help="read temperatures without contacting HA or Bark"
    )
    parser.add_argument("--test-bark", action="store_true", help="send one Bark test message")
    args = parser.parse_args()

    if args.check:
        failures = 0
        for disk in DISKS:
            try:
                print(f"{disk['path']} {disk['label']}: {get_disk_temp(disk['path'])}°C")
            except Exception as exc:
                failures += 1
                print(f"ERROR {disk['path']}: {exc}", file=sys.stderr)
        return 1 if failures else 0

    load_env(ENV_FILE)
    bark_server = require_env("BARK_SERVER")
    bark_token = require_env("BARK_TOKEN")

    if args.test_bark:
        notify_bark(
            bark_server,
            bark_token,
            "HDD温度监控测试",
            f"{os.uname().nodename} Bark通知配置正常",
        )
        print("Bark test sent")
        return 0

    ha = HomeAssistantClient(require_env("HA_URL"), require_env("HA_TOKEN"))
    return run_monitor(ha, bark_server, bark_token)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RuntimeError, requests.RequestException, subprocess.SubprocessError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
