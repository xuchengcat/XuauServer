import json
from datetime import datetime
from pathlib import Path
import re
import sys
from typing import List, Optional, Tuple

# Script updates config.yaml proxies using the most recent subscription_*.json payload.
BASE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = BASE_DIR / "config.yaml"
TIMESTAMP_PATTERN = re.compile(r"subscription_(\d{8}_\d{6})\.json$")
SAFE_PLAIN_SCALAR = re.compile(r"^[A-Za-z0-9_.:/-]+$")
SKIP_PREFIXES = ("剩余流量", "套餐到期")
SKIP_NAMES = {"过滤掉12条线路"}


def find_latest_subscription_file() -> Path:
    candidates = list(BASE_DIR.glob("subscription_*.json"))
    if not candidates:
        raise FileNotFoundError("No subscription_*.json files found")

    def file_timestamp(path: Path) -> datetime:
        match = TIMESTAMP_PATTERN.search(path.name)
        if not match:
            return datetime.min
        try:
            return datetime.strptime(match.group(1), "%Y%m%d_%H%M%S")
        except ValueError:
            return datetime.min

    return max(candidates, key=file_timestamp)


def yaml_value(value) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    text = "" if value is None else str(value)
    if not text or not SAFE_PLAIN_SCALAR.match(text):
        escaped = text.replace("'", "''")
        return f"'{escaped}'"
    return text


def build_proxy_entry(entry: dict) -> Optional[Tuple[str, str]]:
    name = (entry.get("ps") or "").strip()
    if not name or name.startswith(SKIP_PREFIXES) or name in SKIP_NAMES:
        return None

    server = (entry.get("add") or "").strip()
    port_raw = entry.get("port", "0")
    uuid = (entry.get("id") or "").strip()
    alter_id_raw = entry.get("aid", "0")
    network = (entry.get("net") or "").strip() or "tcp"
    tls_value = (entry.get("tls") or "").strip().lower()
    host = (entry.get("host") or "").strip()
    path = (entry.get("path") or "").strip()

    try:
        port = int(port_raw)
    except (TypeError, ValueError):
        raise ValueError(f"Invalid port value for proxy '{name}': {port_raw}")

    try:
        alter_id = int(alter_id_raw)
    except (TypeError, ValueError):
        raise ValueError(f"Invalid alterId value for proxy '{name}': {alter_id_raw}")

    tls_enabled = tls_value in {"true", "tls", "1", "on"}

    parts = [
        f"name: {yaml_value(name)}",
        f"server: {yaml_value(server)}",
        f"port: {port}",
        "client-fingerprint: chrome",
        "type: vmess",
        f"uuid: {yaml_value(uuid)}",
        f"alterId: {alter_id}",
        "cipher: auto",
        f"tls: {yaml_value(tls_enabled)}",
        "skip-cert-verify: true",
        f"network: {yaml_value(network)}",
    ]

    if network.lower() == "ws":
        ws_opts = []
        if path:
            ws_opts.append(f"path: {yaml_value(path)}")
        if host:
            ws_opts.append(f"headers: {{Host: {yaml_value(host)}}}")
        if ws_opts:
            parts.append(f"ws-opts: {{{', '.join(ws_opts)}}}")
    if host and network.lower() != "ws" and tls_enabled:
        parts.append(f"servername: {yaml_value(host)}")

    parts.append("udp: true")
    return name, "  - {" + ", ".join(parts) + "}"

def unique(items: List[str]) -> List[str]:
    seen = set()
    ordered: List[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            ordered.append(item)
    return ordered


def format_select_group(name: str, proxies: List[str]) -> str:
    lines = [
        f"  - name: {yaml_value(name)}",
        "    type: select",
        "    proxies:",
    ]
    for proxy in proxies:
        lines.append(f"      - {yaml_value(proxy)}")
    return "\n".join(lines)


def format_url_test_group(
    name: str, proxies: List[str], url: str, interval: int, tolerance: int
) -> str:
    lines = [
        f"  - name: {yaml_value(name)}",
        "    type: url-test",
        f"    url: {yaml_value(url)}",
        f"    interval: {interval}",
        f"    tolerance: {tolerance}",
        "    proxies:",
    ]
    for proxy in proxies:
        lines.append(f"      - {yaml_value(proxy)}")
    return "\n".join(lines)


STEAM_KEYWORDS = [
    "香港",
    "日本",
    "新加坡",
    "台湾",
    "美国",
    "英国",
    "德国",
    "加拿大",
    "印度",
]


def build_groups_block(proxy_names: List[str]) -> str:
    ai_gpt_names = unique([name for name in proxy_names if "GPT" in name] + ["DIRECT"])
    streaming_names = unique([name for name in proxy_names if "优化" in name])

    developer_keywords = ["日本", "台湾", "英国", "美国"]
    developer_names = unique([
        name for name in proxy_names if any(keyword in name for keyword in developer_keywords)
    ] + ["DIRECT"])

    steam_names = unique([
        name for name in proxy_names if any(keyword in name for keyword in STEAM_KEYWORDS)
    ])

    ai_gpt_set = {name for name in proxy_names if "GPT" in name}
    other_names = unique(proxy_names + ["DIRECT"])

    global_direct_names = ["DIRECT"]

    steam_group = format_url_test_group(
        "Steam", steam_names, "https://store.steampowered.com", 1800, 50
    )
    stream_media_group = format_url_test_group(
        "流媒体", streaming_names, "https://www.youtube.com/generate_204", 1800, 50
    )

    group_sections = [
        format_select_group("AI-GPT", ai_gpt_names),
        format_select_group("Developer", developer_names),
        steam_group,
        stream_media_group,
        format_select_group("其他", other_names),
    format_select_group("全球直连", global_direct_names),
    ]

    return "proxy-groups:\n" + "\n\n".join(group_sections) + "\n"


def update_config(config_path: Path, proxies_block: str, groups_block: str) -> None:
    text = config_path.read_text(encoding="utf-8")
    proxies_start = text.find("proxies:")
    if proxies_start == -1:
        raise ValueError("No 'proxies:' section found in config.yaml")

    groups_start = text.find("proxy-groups:", proxies_start)
    if groups_start == -1:
        raise ValueError("No 'proxy-groups:' section found after proxies in config.yaml")

    rules_start = text.find("\nrules:", groups_start)
    if rules_start == -1:
        raise ValueError("No 'rules:' section found after proxy-groups in config.yaml")

    new_text = text[:proxies_start] + proxies_block + groups_block + text[rules_start:]
    config_path.write_text(new_text, encoding="utf-8")


def main() -> None:
    try:
        latest_file = find_latest_subscription_file()
    except FileNotFoundError as exc:
        print(exc)
        sys.exit(1)

    with latest_file.open("r", encoding="utf-8") as fh:
        entries = json.load(fh)

    proxy_entries: List[Tuple[str, str]] = []
    for entry in entries:
        result = build_proxy_entry(entry)
        if result:
            proxy_entries.append(result)

    if not proxy_entries:
        print(f"No usable proxies found in {latest_file.name}")
        sys.exit(1)

    proxy_names = [name for name, _ in proxy_entries]
    proxy_lines = [line for _, line in proxy_entries]

    proxies_block = "proxies:\n" + "\n".join(proxy_lines) + "\n\n"
    groups_block = build_groups_block(proxy_names)

    if not CONFIG_PATH.exists():
        print(f"Config file {CONFIG_PATH} not found")
        sys.exit(1)

    update_config(CONFIG_PATH, proxies_block, groups_block)
    print(
        f"Updated proxies ({len(proxy_lines)}) and proxy groups in {CONFIG_PATH.name} using {latest_file.name}"
    )


if __name__ == "__main__":
    main()
