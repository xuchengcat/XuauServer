#!/usr/bin/env python3
"""为 TMDB 配置独立故障切换出口，校验成功后发布，失败恢复原配置。"""

import datetime
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
import urllib.request

import yaml


BASE = Path('/etc/ShellCrash')
GROUP = '🎬 媒体元数据'
RULES = [f'DOMAIN-SUFFIX,{domain},{GROUP}' for domain in ('themoviedb.org', 'tmdb.org')]
NODES = ['新加坡-优化-GPT', '美国LA-优化-GPT', '香港WAP-优化2']


def atomic_write(path: Path, content: bytes) -> None:
    """原子替换并保留文件权限和属主。"""
    stat = path.stat()
    fd, name = tempfile.mkstemp(dir=path.parent, prefix='.' + path.name)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(name, stat.st_mode & 0o777)
        os.chown(name, stat.st_uid, stat.st_gid)
        os.replace(name, path)
    finally:
        Path(name).unlink(missing_ok=True)


def verify(runtime: dict) -> None:
    """等待控制器就绪并确认实际加载了独立路由。"""
    port = str(runtime.get('external-controller', ':9999')).rsplit(':', 1)[1]
    for attempt in range(20):
        try:
            req = urllib.request.Request(
                f'http://127.0.0.1:{port}/proxies',
                headers={'Authorization': 'Bearer ' + str(runtime.get('secret', ''))},
            )
            with urllib.request.urlopen(req, timeout=2) as response:
                data = json.load(response)
            live = yaml.safe_load(Path('/tmp/ShellCrash/config.yaml').read_text())
            if GROUP in data['proxies'] and all(rule in live['rules'] for rule in RULES):
                return
        except (OSError, ValueError, KeyError):
            pass
        if attempt < 19:
            time.sleep(1)
    raise RuntimeError('媒体路由未在控制器中生效')


def main() -> None:
    """只修改媒体域名规则和对应策略组，不触发任何下载。"""
    runtime = yaml.safe_load(Path('/tmp/ShellCrash/config.yaml').read_text())
    available = {node['name'] for node in runtime['proxies']}
    nodes = [node for node in NODES if node in available]
    if len(nodes) < 2:
        raise RuntimeError('媒体故障切换至少需要两个已验证节点')
    group = {
        'name': GROUP, 'type': 'fallback', 'proxies': nodes,
        'url': 'https://api.themoviedb.org/3/configuration',
        'expected-status': '401', 'interval': 300, 'lazy': False,
    }
    rules_path = BASE / 'yamls/rules.yaml'
    groups_path = BASE / 'yamls/proxy-groups.yaml'
    original = {p: p.read_bytes() for p in (rules_path, groups_path)}
    rules = yaml.safe_load(original[rules_path]) or []
    groups = yaml.safe_load(original[groups_path]) or []
    rules = RULES + [rule for rule in rules if rule not in RULES]
    groups = [item for item in groups if item['name'] != GROUP] + [group]
    runtime['rules'] = RULES + [rule for rule in runtime['rules'] if rule not in RULES]
    runtime['proxy-groups'] = [item for item in runtime['proxy-groups'] if item['name'] != GROUP] + [group]
    with tempfile.TemporaryDirectory(prefix='media-route-') as directory:
        candidate = Path(directory) / 'config.yaml'
        candidate.write_text(yaml.safe_dump(runtime, allow_unicode=True, sort_keys=False))
        candidate.chmod(0o600)
        result = subprocess.run(
            ['/tmp/ShellCrash/CrashCore', '-t', '-d', str(BASE), '-f', str(candidate)],
            capture_output=True, text=True,
        )
        if result.returncode:
            raise RuntimeError('Mihomo 拒绝媒体路由配置，未修改现有文件')
    backup = Path('/mnt/SDD128G/maintenance-backups') / ('media-route-' + datetime.datetime.now().strftime('%Y%m%d-%H%M%S'))
    backup.mkdir(mode=0o700)
    for path, content in original.items():
        (backup / path.name).write_bytes(content)
    try:
        for path, content in ((rules_path, rules), (groups_path, groups)):
            atomic_write(path, yaml.safe_dump(content, allow_unicode=True, sort_keys=False).encode())
        subprocess.run(['systemctl', 'restart', 'shellcrash'], check=True, timeout=120)
        verify(runtime)
    except BaseException:
        for path, content in original.items():
            atomic_write(path, content)
        subprocess.run(['systemctl', 'restart', 'shellcrash'], check=True, timeout=120)
        raise
    print('TMDB 独立故障切换路由已生效；未创建下载任务。')


if __name__ == '__main__':
    main()
