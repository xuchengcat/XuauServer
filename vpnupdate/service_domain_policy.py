"""Persistent service-domain routing checks; never change hosts or DDNS."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import fcntl
import fnmatch
import os
from pathlib import Path
import tempfile
import time

import yaml

SUFFIX = 'speedtest.xuchengcat.cn'
RULES = [f'DOMAIN-SUFFIX,{SUFFIX},DIRECT', 'DOMAIN-SUFFIX,xuchengcat.cn,DIRECT']
BASE = Path('/etc/ShellCrash')
RUNTIME = Path('/tmp/ShellCrash/config.yaml')
LOCK = Path('/run/lock/shellcrash-maintenance.lock')


@contextmanager
def maintenance_lock(timeout: float = 300):
    """Serialize Python entry points; systemd must not take a second outer lock."""
    with LOCK.open('a') as stream:
        deadline = time.monotonic() + timeout
        while True:
            try:
                fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise RuntimeError('Timed out waiting for ShellCrash maintenance lock') from None
                time.sleep(0.2)
        try:
            yield
        finally:
            fcntl.flock(stream, fcntl.LOCK_UN)


def merge_rules(rules: list) -> list:
    return RULES + [rule for rule in rules if rule not in RULES]


def matches(pattern: str, domain: str) -> bool:
    if pattern.startswith('+.'):
        suffix = pattern[2:]
        return domain == suffix or domain.endswith('.' + suffix)
    return fnmatch.fnmatchcase(domain, pattern)


def verify(runtime: dict) -> None:
    rules = runtime.get('rules', [])
    if rules[:2] != RULES:
        raise RuntimeError('Service-domain DIRECT rules missing or overridden; repair persistent rules.yaml')
    dns = runtime.get('dns', {})
    policies = dns.get('nameserver-policy', {})
    if policies.get('+.xuchengcat.cn') != '127.0.0.1:53':
        raise RuntimeError('Existing service-domain local DNS forwarding policy changed')
    if dns.get('fake-ip-filter-mode', 'blacklist') != 'whitelist':
        raise RuntimeError('Service-domain verification expects the existing fake-IP whitelist mode')
    samples = [SUFFIX, 'jellyfin.' + SUFFIX, 'home.' + SUFFIX]
    for pattern in dns.get('fake-ip-filter', []):
        if isinstance(pattern, str) and any(matches(pattern, host) for host in samples):
            raise RuntimeError('Service domains unexpectedly included in the fake-IP whitelist')


def verify_persistent(base: Path = BASE) -> None:
    rules = yaml.safe_load((base / 'yamls/rules.yaml').read_text()) or []
    user = yaml.safe_load((base / 'yamls/user.yaml').read_text()) or {}
    verify({**user, 'rules': rules})


def verify_candidate(main: dict, base: Path = BASE, runtime_path: Path = RUNTIME) -> None:
    """Use persistent overrides with candidate nodes/groups, without writing them."""
    import copy
    import maintain_shellcrash as maintenance
    candidate = copy.deepcopy(yaml.safe_load(runtime_path.read_text()))
    candidate['proxies'] = main['proxies']
    groups = {group['name']: group for group in main.get('proxy-groups', [])}
    custom = base / 'yamls/proxy-groups.yaml'
    if custom.exists():
        for group in yaml.safe_load(custom.read_text()) or []:
            groups[group['name']] = group
    candidate['proxy-groups'] = list(groups.values())
    verify_persistent(base)
    with tempfile.TemporaryDirectory(prefix='service-domain-validation-') as directory:
        maintenance.validate(candidate, Path(directory))


def install() -> None:
    from maintain_shellcrash import atomic_write, restart, validate
    path = BASE / 'yamls/rules.yaml'
    original = path.read_bytes()
    rules = yaml.safe_load(original) or []
    merged = merge_rules(rules)
    runtime = yaml.safe_load(RUNTIME.read_text())
    runtime['rules'] = merge_rules(runtime.get('rules', []))
    with tempfile.TemporaryDirectory(prefix='service-domain-install-') as directory:
        validate(runtime, Path(directory))
    if merged == rules:
        verify_persistent()
        verify(yaml.safe_load(RUNTIME.read_text()))
        print('Service-domain policy unchanged and healthy; no restart')
        return
    try:
        atomic_write(path, yaml.safe_dump(merged, allow_unicode=True, sort_keys=False).encode())
        restart()
        verify_persistent()
        verify(yaml.safe_load(RUNTIME.read_text()))
    except BaseException:
        atomic_write(path, original)
        # The restored pre-migration policy need not contain the new rule yet.
        import subprocess
        subprocess.run(['systemctl', '--no-ask-password', 'restart', 'shellcrash'], check=True, timeout=120)
        raise
    print('Service-domain DIRECT policy installed; hosts and DNS mappings unchanged')


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    if args.apply:
        if os.geteuid() != 0:
            raise RuntimeError('Apply requires root')
        with maintenance_lock():
            install()
    else:
        print('Planned leading rules: ' + '; '.join(RULES))
        print('Preview only: no downloads, writes, restarts or host mapping changes')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
