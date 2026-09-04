#!/usr/bin/env python3
"""Safely update subscription nodes directly in ShellCrash config.yaml."""
from __future__ import annotations

import argparse, base64, binascii, json, os, re, shutil, subprocess, sys, tempfile
import urllib.error, urllib.request
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlsplit, parse_qs
import yaml

BASE_DIR = Path(__file__).resolve().parent
SCHEMES = {"vmess", "ss", "trojan"}

class UpdateError(RuntimeError): pass

def load_dotenv(path: Path) -> None:
    if not path.exists(): raise UpdateError(f"环境文件不存在: {path}（请复制 .env.example 并填写）")
    for number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"): continue
        if line.startswith("export "): line = line[7:].lstrip()
        if "=" not in line: raise UpdateError(f"{path}:{number}: 不是 KEY=VALUE 格式")
        key, value = line.split("=", 1); key, value = key.strip(), value.strip()
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key): raise UpdateError(f"{path}:{number}: 环境变量名无效")
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'": value = value[1:-1]
        os.environ.setdefault(key, value)

def env_path(name: str, default: str) -> Path:
    return Path(os.getenv(name, default)).expanduser().resolve()

def decode_b64(value: str) -> bytes:
    compact = "".join(value.split()) + "=" * (-len("".join(value.split())) % 4)
    try: return base64.urlsafe_b64decode(compact)
    except (binascii.Error, ValueError) as exc: raise UpdateError("订阅内容不是有效的 Base64") from exc

def fetch(url: str, timeout: int, user_agent: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": user_agent, "Accept": "application/yaml,text/plain,*/*"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            data = response.read()
            if not data: raise UpdateError("订阅源返回空内容")
            return data
    except (urllib.error.URLError, TimeoutError) as exc: raise UpdateError(f"下载订阅失败: {exc}") from exc

def parse_vmess(uri: str) -> dict[str, Any]:
    try:
        raw = json.loads(decode_b64(uri[8:]).decode("utf-8-sig"))
        proxy: dict[str, Any] = {"name": str(raw.get("ps") or "").strip(), "type": "vmess",
            "server": str(raw.get("add") or "").strip(), "port": int(raw.get("port")),
            "uuid": str(raw.get("id") or "").strip(), "alterId": int(raw.get("aid") or 0),
            "cipher": str(raw.get("scy") or "auto"), "udp": True}
    except (ValueError, TypeError, json.JSONDecodeError, UnicodeDecodeError) as exc: raise UpdateError("VMess 节点格式无效") from exc
    network = str(raw.get("net") or "tcp").lower(); proxy["network"] = network
    if str(raw.get("tls") or "").lower() in {"tls", "true", "1"}:
        proxy.update({"tls": True, "skip-cert-verify": True})
        if raw.get("sni") or raw.get("host"): proxy["servername"] = str(raw.get("sni") or raw.get("host"))
    if network == "ws":
        proxy["ws-opts"] = {"path": str(raw.get("path") or "/")}
        if raw.get("host"): proxy["ws-opts"]["headers"] = {"Host": str(raw["host"])}
    return proxy

def parse_ss(uri: str) -> dict[str, Any]:
    body, _, fragment = uri[5:].partition("#"); body = body.split("?", 1)[0]
    try:
        if "@" not in body: body = decode_b64(body).decode()
        credentials, endpoint = body.rsplit("@", 1)
        if ":" not in credentials: credentials = decode_b64(credentials).decode()
        cipher, password = credentials.split(":", 1); server, port = endpoint.rsplit(":", 1)
        return {"name": unquote(fragment) or server, "type": "ss", "server": server.strip("[]"), "port": int(port), "cipher": cipher, "password": password, "udp": True}
    except (ValueError, UnicodeDecodeError) as exc: raise UpdateError("Shadowsocks 节点格式无效") from exc

def parse_trojan(uri: str) -> dict[str, Any]:
    parsed = urlsplit(uri)
    if not parsed.hostname or not parsed.port or not parsed.username: raise UpdateError("Trojan 节点格式无效")
    query = parse_qs(parsed.query)
    return {"name": unquote(parsed.fragment) or parsed.hostname, "type": "trojan", "server": parsed.hostname,
        "port": parsed.port, "password": unquote(parsed.username), "sni": query.get("sni", [parsed.hostname])[0],
        "skip-cert-verify": True, "udp": True}

def parse_uri_list(text: str) -> list[dict[str, Any]]:
    proxies, errors = [], []
    parsers = {"vmess": parse_vmess, "ss": parse_ss, "trojan": parse_trojan}
    for uri in map(str.strip, text.splitlines()):
        scheme = uri.split("://", 1)[0].lower()
        if scheme not in SCHEMES: continue
        try: proxies.append(parsers[scheme](uri))
        except UpdateError as exc: errors.append(str(exc))
    if not proxies: raise UpdateError("订阅中没有可用节点" + (f"（{errors[0]}）" if errors else ""))
    return proxies

def parse_subscription(data: bytes) -> list[dict[str, Any]]:
    text = data.decode("utf-8-sig", errors="replace").strip()
    try: document = yaml.safe_load(text)
    except yaml.YAMLError: document = None
    if isinstance(document, dict) and isinstance(document.get("proxies"), list): return document["proxies"]
    if isinstance(document, list) and all(isinstance(x, dict) for x in document): return document
    if not any(f"{x}://" in text for x in SCHEMES): text = decode_b64(text).decode("utf-8-sig")
    return parse_uri_list(text)

def validate_proxies(proxies: list[Any], minimum: int) -> list[dict[str, Any]]:
    required, cleaned, seen = {"name", "type", "server", "port"}, [], {}
    for index, item in enumerate(proxies, 1):
        if not isinstance(item, dict) or not required.issubset(item): raise UpdateError(f"第 {index} 个节点缺少必要字段")
        try: port = int(item["port"])
        except (ValueError, TypeError): raise UpdateError(f"第 {index} 个节点端口无效")
        if not str(item["server"]).strip() or not 1 <= port <= 65535: raise UpdateError(f"第 {index} 个节点地址或端口无效")
        proxy = dict(item); proxy["port"] = port
        base = str(proxy["name"]).strip() or f"node-{index}"; seen[base] = seen.get(base, 0) + 1
        proxy["name"] = base if seen[base] == 1 else f"{base} #{seen[base]}"; cleaned.append(proxy)
    if len(cleaned) < minimum: raise UpdateError(f"仅解析到 {len(cleaned)} 个节点，低于 MIN_PROXY_COUNT={minimum}，拒绝覆盖")
    return cleaned

def validate_with_core(proxies: list[dict[str, Any]], core: Path) -> None:
    if not core.is_file(): raise UpdateError(f"找不到 Mihomo 核心: {core}")
    with tempfile.TemporaryDirectory(prefix="vpnupdate-test-") as directory:
        names = [x["name"] for x in proxies]
        config = Path(directory) / "config.yaml"
        config.write_text(yaml.safe_dump({"mixed-port": 0, "mode": "rule", "log-level": "silent", "proxies": proxies,
            "proxy-groups": [{"name": "PROXY", "type": "select", "proxies": names}], "rules": ["MATCH,PROXY"]}, allow_unicode=True, sort_keys=False), encoding="utf-8")
        result = subprocess.run([str(core), "-t", "-d", directory, "-f", str(config)], text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        if result.returncode: raise UpdateError("Mihomo 配置校验失败: " + result.stdout.strip()[-1000:])

def atomic_install(source: Path, target: Path, backup_count: int) -> bool:
    target.parent.mkdir(parents=True, exist_ok=True); new_bytes = source.read_bytes()
    if target.exists() and target.read_bytes() == new_bytes: return False
    if target.exists() and backup_count > 0:
        from datetime import datetime
        backup_dir = target.parent / ".vpnupdate-backups"; backup_dir.mkdir(mode=0o700, exist_ok=True)
        shutil.copy2(target, backup_dir / f"{target.name}.{datetime.now():%Y%m%d-%H%M%S}.bak")
        for old in sorted(backup_dir.glob(f"{target.name}.*.bak"), reverse=True)[backup_count:]: old.unlink()
    fd, temp_name = tempfile.mkstemp(prefix=f".{target.name}.", dir=target.parent)
    try:
        with os.fdopen(fd, "wb") as handle: handle.write(new_bytes); handle.flush(); os.fsync(handle.fileno())
        os.chmod(temp_name, 0o640)
        if target.exists(): os.chown(temp_name, target.stat().st_uid, target.stat().st_gid)
        os.replace(temp_name, target)
    finally:
        if os.path.exists(temp_name): os.unlink(temp_name)
    return True

def build_config(config_path: Path, proxies: list[dict[str, Any]]) -> dict[str, Any]:
    if not config_path.is_file(): raise UpdateError(f"找不到 ShellCrash 主配置: {config_path}")
    document = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    if not isinstance(document, dict): raise UpdateError("ShellCrash 主配置不是 YAML 对象")
    old_names = {str(x.get("name")) for x in document.get("proxies", []) if isinstance(x, dict)}
    new_names = [str(x["name"]) for x in proxies]
    document["proxies"] = proxies
    providers = document.get("proxy-providers")
    if isinstance(providers, dict):
        providers.pop("b", None)
        if not providers: document.pop("proxy-providers", None)
    managed = {x.strip() for x in os.getenv("UPDATE_GROUPS", "🚀 节点选择,🎮 Steam,🤖 ChatGPT").split(",") if x.strip()}
    updated = 0
    for group in document.get("proxy-groups", []):
        if not isinstance(group, dict): continue
        uses_b = "b" in (group.get("use") or [])
        if uses_b:
            group["use"] = [x for x in group["use"] if x != "b"]
            if not group["use"]: group.pop("use")
        if uses_b or group.get("name") in managed:
            retained = [x for x in (group.get("proxies") or []) if str(x) not in old_names]
            group["proxies"] = retained + [x for x in new_names if x not in retained]
            updated += 1
    if not updated: raise UpdateError("没有找到需要写入节点的策略组，请设置 UPDATE_GROUPS")
    return document

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument("--env-file", type=Path, default=BASE_DIR / ".env"); parser.add_argument("--dry-run", action="store_true"); args = parser.parse_args()
    try:
        load_dotenv(args.env_file.resolve()); url = os.getenv("SUBSCRIPTION_URL", "").strip()
        if not url.startswith(("https://", "http://")): raise UpdateError("SUBSCRIPTION_URL 必须是 http(s) URL")
        config_path, core = env_path("CONFIG_PATH", "/etc/ShellCrash/yamls/config.yaml"), env_path("MIHOMO_CORE", "/tmp/ShellCrash/CrashCore")
        proxies = validate_proxies(parse_subscription(fetch(url, int(os.getenv("HTTP_TIMEOUT", "30")), os.getenv("SUBSCRIPTION_USER_AGENT", "clash.meta"))), int(os.getenv("MIN_PROXY_COUNT", "1")))
        validate_with_core(proxies, core)
        document = build_config(config_path, proxies)
        with tempfile.TemporaryDirectory(prefix="vpnupdate-") as directory:
            candidate = Path(directory) / "config.yaml"; candidate.write_text(yaml.safe_dump(document, allow_unicode=True, sort_keys=False, width=4096), encoding="utf-8")
            if args.dry_run: print(f"校验通过：解析到 {len(proxies)} 个节点（dry-run，未写入）"); return 0
            changed = atomic_install(candidate, config_path, int(os.getenv("BACKUP_COUNT", "5")))
        restart = os.getenv("RESTART_COMMAND", "systemctl restart shellcrash").strip()
        if changed and restart: subprocess.run(restart.split(), check=True)
        state = "内容未变化" if not changed else ("已安装并重载" if restart else "已安装（未配置重载命令）")
        print(f"更新成功：{len(proxies)} 个节点，{state}"); return 0
    except (UpdateError, OSError, ValueError, subprocess.CalledProcessError) as exc:
        print(f"更新失败：{exc}", file=sys.stderr); return 1

if __name__ == "__main__": raise SystemExit(main())
