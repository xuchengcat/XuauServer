import json
import pathlib
import sqlite3
import subprocess
import time

p = pathlib.Path(pathlib.Path('/mnt/SDD128G/maintenance/current').read_text())
before = json.loads((p / 'running.json').read_text())
roots = {
    'homeassistant': ['homeassistant/config'],
    'frigate': ['frigate'],
    'photoprism': ['photoprism/storage'],
    'jellyfin': ['jellyfin/config'],
    'nginx-proxy-manager': ['nginx_proxy_manager/data'],
    'dockhand': ['dockhand/data'],
    'kavita': ['kavita/config'],
    'prowlarr': ['prowlarr/config'],
    'moontv': ['moontvplus/data'],
    'nextcloud': ['../HDD14T/nextcloud_data'],
}
records = json.loads((p / 'applied.json').read_text()) if (p / 'applied.json').exists() else []
done = {r['service'] for r in records if r['code'] == 0}
for c in before:
    service = c['service']
    if service in done or c['image'].startswith(('openclaw-local:', 'xhs-readonly-local:', 'local/')):
        continue
    new = json.loads(subprocess.check_output(['docker', 'image', 'inspect', c['image']]))[0]['Id']
    if new == c['id']:
        continue
    print('Updating', service, flush=True)
    subprocess.run(['docker', 'tag', c['id'], 'local-maintenance/' + service + ':20261022'], check=True)
    subprocess.run(['docker', 'stop', '--time', '60', c['name']], check=True)
    try:
        if service == 'nextcloud':
            subprocess.run(['tar', '-cf', str(p / 'nextcloud-program-before.tar'), '--exclude=nextcloud/data', '-C', '/mnt/SDD128G', 'nextcloud'], check=True)
        dbdir = p / 'sqlite-before' / service
        dbdir.mkdir(parents=True, exist_ok=True, mode=0o700)
        for root in roots.get(service, []):
            rootpath = pathlib.Path('/mnt/SDD128G') / root
            candidates = [rootpath / 'owncloud.db'] if service == 'nextcloud' else rootpath.rglob('*')
            for f in candidates:
                if f.suffix.lower() not in ('.db', '.sqlite', '.sqlite3') or not f.is_file():
                    continue
                if any(x in f.parts for x in ('cache', 'node_modules', 'model_cache')):
                    continue
                if service == 'frigate' and f.name == 'backup.db':
                    continue
                with f.open('rb') as stream:
                    if stream.read(16) != b'SQLite format 3\x00':
                        continue
                target = dbdir / f.relative_to(rootpath)
                target.parent.mkdir(parents=True, exist_ok=True)
                with sqlite3.connect(f.as_uri() + '?mode=ro', uri=True, timeout=30) as src:
                    with sqlite3.connect(target) as dst:
                        src.backup(dst)
        with (p / ('apply-' + service + '.log')).open('w') as out:
            result = subprocess.run(['docker', 'compose', '-f', c['files'], 'up', '-d', '--no-deps', '--no-build', '--pull', 'never', service], stdout=out, stderr=subprocess.STDOUT)
        records.append({'service': service, 'name': c['name'], 'old': c['id'], 'new': new, 'code': result.returncode})
        (p / 'applied.json').write_text(json.dumps(records, indent=2))
        print(service, 'exit', result.returncode, flush=True)
        if result.returncode:
            subprocess.run(['docker', 'start', c['name']])
    except BaseException:
        subprocess.run(['docker', 'start', c['name']])
        raise
print('Completed', len(records), 'image updates', flush=True)
