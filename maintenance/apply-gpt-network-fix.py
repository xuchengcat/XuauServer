import copy
import hashlib
import json
import os
import pathlib
import re
import shutil
import subprocess
import tempfile
import urllib.request

import yaml

p = pathlib.Path(pathlib.Path('/mnt/SDD128G/maintenance/current-gpt-netfix').read_text())
base = pathlib.Path('/etc/ShellCrash')
mainpath = base / 'yamls/config.yaml'
rulepath = base / 'yamls/rules.yaml'
userpath = base / 'yamls/user.yaml'
cfgpath = base / 'configs/ShellCrash.cfg'
paths = [mainpath, rulepath, userpath, cfgpath] + [base / n for n in ['Country.mmdb', 'GeoSite.dat', 'cn_ip.txt', 'cn_ipv6.txt']]
previous = {f: f.read_bytes() for f in paths}
live = yaml.safe_load(pathlib.Path('/tmp/ShellCrash/config.yaml').read_text())
main = yaml.safe_load(mainpath.read_text())
group = next(g for g in main['proxy-groups'] if g['name'] == '🤖 ChatGPT')
preferred = ['美国LA-优化-GPT', '美国LA-优化2-GPT', '美国LA-优化3-GPT', '新加坡-优化-GPT', '新加坡-优化2-GPT', '台湾-优化2-GPT', '英国-优化-GPT']
available = {n['name'] for n in main['proxies']}
group.update(type='fallback', proxies=[n for n in preferred if n in available], url='https://chatgpt.com/cdn-cgi/trace', interval=300, lazy=False)
group['expected-status'] = '200'
group.pop('tolerance', None)
suffixes = ['chatgpt.com', 'openai.com', 'oaistatic.com', 'oaiusercontent.com', 'oaistatsig.com', 'openaimerge.com', 'workos.com', 'workoscdn.com', 'intercom.io', 'intercomcdn.com', 'ct.sendgrid.net']
exact = ['workos.imgix.net', 'challenges.cloudflare.com', 'humb.apple.com', 'js.stripe.com', 'o207216.ingest.sentry.io', 'o33249.ingest.sentry.io', 'rum.browser-intake-datadoghq.com']
ai_rules = [f'DOMAIN-SUFFIX,{n},🤖 ChatGPT' for n in suffixes] + [f'DOMAIN,{n},🤖 ChatGPT' for n in exact]
original_rules = yaml.safe_load(rulepath.read_text()) or []
other_rules = [r for r in original_rules if not str(r).endswith(',🤖 ChatGPT')]
rules = ai_rules + other_rules
user = yaml.safe_load(userpath.read_text()) or {}
dns = copy.deepcopy(live['dns'])
dns.pop('fake-ip-range6', None)
dns.update({'fake-ip-filter-mode': 'whitelist', 'fake-ip-filter': ['+.' + n for n in suffixes] + exact, 'proxy-server-nameserver': ['223.5.5.5', '119.29.29.29']})
policy = dns.setdefault('nameserver-policy', {})
for n in suffixes:
    policy['+.' + n] = ['https://1.1.1.1/dns-query#🤖 ChatGPT&disable-ipv6=true&disable-qtype-65=true']
for n in exact:
    policy[n] = ['https://1.1.1.1/dns-query#🤖 ChatGPT&disable-ipv6=true&disable-qtype-65=true']
user['dns'] = dns
user.setdefault('profile', {}).update({'store-selected': True, 'store-fake-ip': True})
cfg = cfgpath.read_text()
version = re.search(r'^GeoIP_v=(\d+)$', (p / 'version').read_text(), re.M).group(1)
for key, value in {'ipv6_redir': 'ON', 'Country_v': version, 'geosite_v': version, 'china_ip_list_v': version, 'china_ipv6_list_v': version}.items():
    cfg = re.sub(r'^' + re.escape(key) + r'=.*\n?', '', cfg, flags=re.M)
    cfg += f'{key}={value}\n'
candidate = copy.deepcopy(live)
candidate['proxy-groups'] = [copy.deepcopy(group) if g['name'] == '🤖 ChatGPT' else g for g in candidate['proxy-groups']]
candidate['rules'] = ai_rules + [r for r in live['rules'] if not str(r).endswith(',🤖 ChatGPT')]
candidate.update(user)

def install(path, content):
    fd, name = tempfile.mkstemp(prefix='.' + path.name + '.', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as out:
            out.write(content)
            out.flush()
            os.fsync(out.fileno())
        st = path.stat()
        os.chmod(name, st.st_mode & 0o777)
        os.chown(name, st.st_uid, st.st_gid)
        os.replace(name, path)
    finally:
        pathlib.Path(name).unlink(missing_ok=True)

with tempfile.TemporaryDirectory(prefix='gpt-deploy-') as stage:
    stage = pathlib.Path(stage)
    for name in ['Country.mmdb', 'GeoSite.dat', 'cn_ip.txt', 'cn_ipv6.txt']:
        shutil.copy2(p / name, stage / name)
    test = copy.deepcopy(candidate)
    for provider in test.get('rule-providers', {}).values():
        source = (base / provider['path']).resolve()
        target = stage / 'ruleset' / source.name
        target.parent.mkdir(exist_ok=True)
        shutil.copy2(source, target)
        provider.update(type='file', path=str(target))
        for k in ['url', 'interval', 'proxy']:
            provider.pop(k, None)
    test['rules'] = ['GEOSITE,cn,DIRECT', 'GEOIP,CN,DIRECT'] + test['rules']
    f = stage / 'config.yaml'
    f.write_text(yaml.safe_dump(test, allow_unicode=True, sort_keys=False))
    f.chmod(0o600)
    r = subprocess.run(['/tmp/ShellCrash/CrashCore', '-t', '-d', str(stage), '-f', str(f)], capture_output=True, text=True)
    (p / 'candidate-validation.log').write_text(r.stdout + r.stderr)
    print('Staged config and Geo databases validation:', r.returncode, flush=True)
    r.check_returncode()
    try:
        for path, doc in [(mainpath, main), (rulepath, rules), (userpath, user)]:
            install(path, yaml.safe_dump(doc, allow_unicode=True, sort_keys=False, width=4096).encode())
        install(cfgpath, cfg.encode())
        for name in ['Country.mmdb', 'GeoSite.dat', 'cn_ip.txt', 'cn_ipv6.txt']:
            install(base / name, (p / name).read_bytes())
        print('Config and data installed; restarting local ShellCrash.', flush=True)
        r = subprocess.run(['systemctl', 'restart', 'shellcrash'], capture_output=True, text=True, timeout=120)
        (p / 'restart.log').write_text(r.stdout + r.stderr)
        r.check_returncode()
        subprocess.run(['systemctl', 'is-active', '--quiet', 'shellcrash'], check=True)
        runtime = yaml.safe_load(pathlib.Path('/tmp/ShellCrash/config.yaml').read_text())
        g = next(g for g in runtime['proxy-groups'] if g['name'] == '🤖 ChatGPT')
        assert g['type'] == 'fallback' and g['interval'] == 300
        assert runtime['dns']['fake-ip-filter-mode'] == 'whitelist'
        assert runtime['rules'][0] == ai_rules[0]
        print('Runtime config verified; no persistent rollback configuration retained.', flush=True)
        (p / 'deployment-summary.json').write_text(json.dumps({'gpt_group': g, 'ai_suffixes': suffixes, 'ai_exact_domains': exact, 'geodata_version': version, 'local_ipv6_redirection': True, 'lan_proxy_enabled': False}, ensure_ascii=False, indent=2))
    except BaseException:
        for path, content in previous.items():
            install(path, content)
        subprocess.run(['systemctl', 'restart', 'shellcrash'], timeout=120)
        raise
