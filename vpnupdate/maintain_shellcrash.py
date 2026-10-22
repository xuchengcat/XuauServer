#!/usr/bin/env python3
"""Scheduled subscription and Geo data maintenance for this ShellCrash host."""
from __future__ import annotations

import argparse
import copy
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import time
import urllib.request
import ipaddress
import yaml

BASE = Path('/etc/ShellCrash')
RUNTIME = Path('/tmp/ShellCrash/config.yaml')
CORE = Path('/tmp/ShellCrash/CrashCore')
HERE = Path(__file__).resolve().parent
ORIGIN = 'https://raw.githubusercontent.com/juewuy/ShellCrash/update/bin/'


def log(message: str) -> None:
    print(message, flush=True)


def atomic_write(path: Path, data: bytes) -> None:
    fd, temporary = tempfile.mkstemp(prefix='.' + path.name + '.', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        if path.exists():
            stat = path.stat()
            os.chmod(temporary, stat.st_mode & 0o777)
            os.chown(temporary, stat.st_uid, stat.st_gid)
        else:
            os.chmod(temporary, 0o644)
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def verify_service() -> None:
    for attempt in range(30):
        try:
            runtime = yaml.safe_load(RUNTIME.read_text())
            controller = str(runtime.get('external-controller', ':9999'))
            port = controller.rsplit(':', 1)[1]
            headers = {'Authorization': 'Bearer ' + str(runtime['secret'])} if runtime.get('secret') else {}
            with urllib.request.urlopen(urllib.request.Request('http://127.0.0.1:' + port + '/version', headers=headers), timeout=2) as response:
                json.load(response)
            subprocess.run(['systemctl', 'is-active', '--quiet', 'shellcrash'], check=True)
            return
        except (OSError, ValueError, KeyError, subprocess.CalledProcessError):
            if attempt == 29:
                raise RuntimeError('ShellCrash controller did not become healthy') from None
            time.sleep(1)


def restart() -> None:
    subprocess.run(['systemctl', 'restart', 'shellcrash'], check=True, timeout=120)
    verify_service()


def validate(runtime: dict, directory: Path, geo: bool = False) -> None:
    candidate = copy.deepcopy(runtime)
    for provider in candidate.get('rule-providers', {}).values():
        source = (BASE / provider['path']).resolve()
        destination = directory / 'ruleset' / source.name
        destination.parent.mkdir(exist_ok=True)
        destination.write_bytes(source.read_bytes())
        provider.update(type='file', path=str(destination))
        for key in ('url', 'interval', 'proxy'):
            provider.pop(key, None)
    if geo:
        candidate['rules'] = ['GEOSITE,cn,DIRECT', 'GEOIP,CN,DIRECT'] + candidate.get('rules', [])
    config = directory / 'validation.yaml'
    config.write_text(yaml.safe_dump(candidate, allow_unicode=True, sort_keys=False))
    config.chmod(0o600)
    result = subprocess.run([str(CORE), '-t', '-d', str(directory), '-f', str(config)], capture_output=True, text=True, timeout=90)
    if result.returncode:
        raise RuntimeError('Mihomo rejected the staged configuration or data; installed files were kept')


def subscription() -> None:
    import update_subscription as updater
    updater.load_dotenv(HERE / '.env')
    target = updater.env_path('CONFIG_PATH', str(BASE / 'yamls/config.yaml'))
    original = target.read_bytes()
    url = os.getenv('SUBSCRIPTION_URL', '').strip()
    if not url.startswith(('http://', 'https://')):
        raise RuntimeError('Subscription URL is missing or invalid')
    try:
        fetched = updater.fetch(url, int(os.getenv('HTTP_TIMEOUT', '30')), os.getenv('SUBSCRIPTION_USER_AGENT', 'clash.meta'))
        nodes = updater.validate_proxies(updater.parse_subscription(fetched), int(os.getenv('MIN_PROXY_COUNT', '1')))
        updater.validate_with_core(nodes, CORE)
        main = updater.build_config(target, nodes)
        current = yaml.safe_load(RUNTIME.read_text())
        candidate = copy.deepcopy(current)
        candidate['proxies'] = nodes
        managed = {group['name']: group for group in main.get('proxy-groups', [])}
        custom = BASE / 'yamls/proxy-groups.yaml'
        if custom.exists():
            for group in yaml.safe_load(custom.read_text()) or []:
                managed[group['name']] = group
        candidate['proxy-groups'] = list(managed.values())
        with tempfile.TemporaryDirectory(prefix='shellcrash-subscription-') as directory:
            directory = Path(directory)
            validate(candidate, directory)
            staged = directory / 'config.yaml'
            staged.write_text(yaml.safe_dump(main, allow_unicode=True, sort_keys=False, width=4096))
            changed = updater.atomic_install(staged, target, int(os.getenv('BACKUP_COUNT', '5')))
        if changed:
            try:
                restart()
                live = yaml.safe_load(RUNTIME.read_text())
                identity = lambda node: (node['name'], node['type'], node['server'], int(node['port']))
                if {identity(node) for node in live['proxies']} != {identity(node) for node in nodes}:
                    raise RuntimeError('Runtime nodes differ from the new subscription')
            except BaseException:
                atomic_write(target, original)
                restart()
                raise
        log(f'Subscription OK: {len(nodes)} entries; ' + ('updated and restarted' if changed else 'unchanged, no restart'))
    except Exception as error:
        # Avoid subscription tokens or node secrets in the system journal.
        raise RuntimeError('Subscription update failed; previous configuration retained (' + type(error).__name__ + ')') from None


def geodata(force_check: bool) -> None:
    current = yaml.safe_load(RUNTIME.read_text())
    cfg_path = BASE / 'configs/ShellCrash.cfg'
    cfg = cfg_path.read_text()
    flags = dict(re.findall(r'^([A-Za-z_][A-Za-z0-9_]*)=(.*)$', cfg, re.M))
    geoip = ('cn_mini.mmdb', 'cn_mini_v') if flags.get('cn_mini_v') else ('Country.mmdb', 'Country_v')
    files = [('Country.mmdb', geoip[0], geoip[1]), ('GeoSite.dat', 'geosite.dat', 'geosite_v'), ('cn_ip.txt', 'china_ip_list.txt', 'china_ip_list_v'), ('cn_ipv6.txt', 'china_ipv6_list.txt', 'china_ipv6_list_v')]
    port = current.get('mixed-port', 17890)
    authentication = (current.get('authentication') or [''])[0]
    curl_config = 'proxy = ' + json.dumps('http://127.0.0.1:' + str(port)) + '\n'
    if authentication:
        curl_config += 'proxy-user = ' + json.dumps(authentication) + '\n'

    def download(url: str, target: Path) -> None:
        result = subprocess.run(['curl', '--config', '-', '--noproxy', '', '--fail', '--location', '--silent', '--show-error', '--retry', '3', '--retry-all-errors', '--retry-delay', '5', '--retry-max-time', '90', '--connect-timeout', '10', '--max-time', '30', '--output', str(target), url], input=curl_config, capture_output=True, text=True, timeout=135)
        if result.returncode:
            raise RuntimeError('Geo data download failed for ' + target.name + ' (curl exit ' + str(result.returncode) + '); installed files were kept')

    with tempfile.TemporaryDirectory(prefix='shellcrash-geodata-') as directory:
        directory = Path(directory)
        download(ORIGIN + 'version', directory / 'version')
        match = re.search(r'^GeoIP_v=(\d{8})$', (directory / 'version').read_text(), re.M)
        if not match:
            raise RuntimeError('Geo data version response is invalid')
        version = match.group(1)
        if not force_check and all(flags.get(key) == version and (BASE / name).exists() and (BASE / name).stat().st_size > 100 for name, _, key in files):
            log('Geo data already at ' + version + '; no download or restart needed')
            return
        for name, remote, _ in files:
            target = directory / name
            download(ORIGIN + 'geodata/' + remote, target)
            data = target.read_bytes()
            if len(data) < 100:
                raise RuntimeError('Geo data file is too small: ' + name)
            if name.endswith('.txt'):
                networks = [ipaddress.ip_network(line.strip()) for line in data.decode().splitlines() if line.strip() and not line.startswith('#')]
                expected = 4 if name == 'cn_ip.txt' else 6
                if len(networks) < 100 or any(network.version != expected for network in networks):
                    raise RuntimeError('Invalid IP list: ' + name)
            if name == 'Country.mmdb' and b'\xab\xcd\xefMaxMind.com' not in data[-131072:]:
                raise RuntimeError('Invalid GeoIP database')
        validate(current, directory, geo=True)
        new_cfg = cfg
        for _, _, key in files:
            new_cfg = re.sub(r'^' + re.escape(key) + r'=.*\n?', '', new_cfg, flags=re.M)
            new_cfg += key + '=' + version + '\n'
        targets = [BASE / name for name, _, _ in files]
        previous = {path: path.read_bytes() if path.exists() else None for path in targets + [cfg_path]}
        changed = [path for path in targets if previous[path] != (directory / path.name).read_bytes()]
        try:
            for target in changed:
                atomic_write(target, (directory / target.name).read_bytes())
            if cfg != new_cfg:
                atomic_write(cfg_path, new_cfg.encode())
            if changed:
                restart()
        except BaseException:
            for target, data in previous.items():
                if data is None:
                    target.unlink(missing_ok=True)
                else:
                    atomic_write(target, data)
            restart()
            raise
        log(f'Geo data OK: {version}; staged validation passed; {len(changed)} files changed; ' + ('restarted' if changed else 'no restart'))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('task', choices=['subscription', 'geodata'])
    parser.add_argument('--force-check', action='store_true', help='Download and validate Geo data even if versions match')
    args = parser.parse_args()
    try:
        verify_service()
        if args.task == 'subscription':
            subscription()
        else:
            geodata(args.force_check)
    except Exception as error:
        log('ERROR: ' + str(error))
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
