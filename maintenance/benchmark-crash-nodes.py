import concurrent.futures
import json
import pathlib
import socket
import statistics
import subprocess
import sys
import time

import yaml

phase = sys.argv[1]
p = pathlib.Path(pathlib.Path('/mnt/SDD128G/maintenance/current-crash').read_text())
source = p / 'runtime-config.yaml' if phase == 'before' else pathlib.Path('/tmp/ShellCrash/config.yaml')
c = yaml.safe_load(source.read_text())
nodes = [n for n in c['proxies'] if not n['name'].startswith(('剩余流量', '套餐到期', '过滤掉'))]
if phase == 'paired':
    old = {n['name']: n for n in yaml.safe_load((p / 'runtime-config.yaml').read_text())['proxies']}
    paired = []
    for n in nodes:
        if n['name'] in old and n.get('server') != old[n['name']].get('server'):
            paired.extend([{**old[n['name']], 'name': n['name'] + ' [old]'}, {**n, 'name': n['name'] + ' [new]'}])
    nodes = paired
runtime = p / ('benchmark-' + phase)
runtime.mkdir(mode=0o700, exist_ok=True)
listeners = []
for i, n in enumerate(nodes):
    port = 19000 + i
    with socket.socket() as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind(('127.0.0.1', port))
    listeners.append({'name': 'test-' + str(i), 'type': 'mixed', 'listen': '127.0.0.1', 'port': port, 'proxy': n['name']})
f = runtime / 'config.yaml'
f.write_text(yaml.safe_dump({'mode': 'rule', 'log-level': 'silent', 'ipv6': c.get('ipv6', True), 'routing-mark': c.get('routing-mark', 7894), 'proxies': nodes, 'listeners': listeners, 'rules': ['MATCH,REJECT']}, allow_unicode=True))
f.chmod(0o600)
with (runtime / 'core.log').open('w') as log:
    core = subprocess.Popen(['/tmp/ShellCrash/CrashCore', '-d', str(runtime), '-f', str(f)], stdout=log, stderr=log)
    try:
        for i in range(50):
            if core.poll() is not None:
                raise RuntimeError('benchmark proxy exited')
            try:
                with socket.create_connection(('127.0.0.1', 19000), timeout=.2):
                    break
            except OSError:
                time.sleep(.1)

        def test(pair):
            i, node = pair
            results = []
            cases = [('general-1', 'https://www.gstatic.com/generate_204', 204), ('general-2', 'https://www.gstatic.com/generate_204', 204), ('google-repository', 'https://packages.cloud.google.com/apt/dists/coral-edgetpu-stable/Release', 200)]
            for label, url, expected in cases:
                body = runtime / (str(i) + '-' + label + '.body')
                body.unlink(missing_ok=True)
                r = subprocess.run(['curl', '--noproxy', '', '--proxy', 'http://127.0.0.1:' + str(19000 + i), '--silent', '--show-error', '--connect-timeout', '5', '--max-time', '10', '--output', str(body), '--write-out', '%{http_code} %{time_total}', url], capture_output=True, text=True)
                fields = r.stdout.split()
                status = int(fields[0]) if fields and fields[0].isdigit() else 0
                elapsed = float(fields[1]) if len(fields) > 1 else None
                content = body.read_text(errors='replace') if body.exists() else ''
                results.append({'test': label, 'curl_exit': r.returncode, 'http': status, 'seconds': elapsed, 'ok': r.returncode == 0 and status == expected, 'project_deleted': r.returncode == 0 and status == 403 and 'Project #844758894060 has been deleted' in content, 'error': r.stderr.strip()})
            row = {'name': node['name'], 'type': node['type'], 'results': results}
            print(json.dumps({'phase': phase, 'name': row['name'], 'general_successes': sum(x['ok'] for x in results[:2]), 'general_attempts': 2, 'repository_http': results[2]['http']}, ensure_ascii=False), flush=True)
            return row

        with concurrent.futures.ThreadPoolExecutor(max_workers=6) as executor:
            rows = list(executor.map(test, enumerate(nodes)))
        valid = [x['seconds'] for row in rows for x in row['results'][:2] if x['ok']]
        summary = {'phase': phase, 'nodes': len(rows), 'attempts': len(rows) * 2, 'successful_attempts': len(valid), 'nodes_any_success': sum(any(x['ok'] for x in row['results'][:2]) for row in rows), 'nodes_both_success': sum(all(x['ok'] for x in row['results'][:2]) for row in rows), 'median_success_seconds': statistics.median(valid) if valid else None, 'repository_successes': sum(row['results'][2]['ok'] for row in rows), 'repository_project_deleted': sum(row['results'][2]['project_deleted'] for row in rows)}
        (p / ('benchmark-' + phase + '.json')).write_text(json.dumps({'summary': summary, 'nodes': rows}, ensure_ascii=False, indent=2))
        print('SUMMARY ' + json.dumps(summary, ensure_ascii=False), flush=True)
    finally:
        core.terminate()
        try:
            core.wait(timeout=5)
        except subprocess.TimeoutExpired:
            core.kill()
            core.wait()
        f.unlink(missing_ok=True)
