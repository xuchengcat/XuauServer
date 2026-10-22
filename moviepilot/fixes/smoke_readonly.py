"""通过 OpenClaw 同一 MCP 凭据验证搜索；硬编码只读白名单，绝不提交下载。"""

import json
from pathlib import Path
import re
import sqlite3
import subprocess
import time

import requests


ALLOWED = {'media.search', 'search.torrents', 'download.tasks.active', 'download.history.list'}


def main() -> None:
    config = json.loads(Path('/mnt/SDD128G/openclaw/config/openclaw.json').read_text())
    environment = json.loads(subprocess.check_output([
        'docker', 'inspect', 'openclaw', '--format', '{{json .Config.Env}}',
    ], text=True))
    environment = dict(item.split('=', 1) for item in environment)
    headers = {
        name: re.sub(r'\$\{([A-Z_][A-Z_0-9]*)\}', lambda match: environment[match[1]], value)
        for name, value in config['mcp']['servers']['moviepilot']['headers'].items()
    }
    session = requests.Session()
    session.trust_env = False
    session.headers.update(headers)
    db = sqlite3.connect('file:/mnt/SDD128G/moviepilot/config/user.db?mode=ro', uri=True)
    before = db.execute('select count(*), max(id) from downloadhistory').fetchone()

    def rpc(method, params):
        response = session.post('http://127.0.0.1:3001/api/v1/mcp', json={
            'jsonrpc': '2.0', 'id': 1, 'method': method, 'params': params,
        }, timeout=210)
        response.raise_for_status()
        result = response.json()
        if 'error' in result:
            raise RuntimeError('MCP JSON-RPC 调用失败；未发起写操作')
        return result['result']

    def call(operation, **arguments):
        if operation not in ALLOWED:
            raise ValueError('只读冒烟测试拒绝写操作')
        result = rpc('tools/call', {'name': 'moviepilot_api', 'arguments': {
            'operation_id': operation, **arguments,
        }})
        for item in result.get('content', []):
            if item.get('type') == 'text':
                return json.loads(item['text'])
        raise RuntimeError('MCP 工具未返回 JSON')

    for attempt in range(30):
        try:
            tools = rpc('tools/list', {})['tools']
            break
        except requests.RequestException:
            if attempt == 29:
                raise
            time.sleep(2)
    tool = next(tool for tool in tools if tool['name'] == 'moviepilot_api')
    branches = tool['inputSchema'].get('oneOf', [])
    search = next(branch for branch in branches if branch.get('title') == 'search.torrents')
    assert 'mtype' in search['properties']['query']['required']
    print('MCP 合同已要求 mtype', flush=True)
    rejected = call('search.torrents', path_params={'media_id': '290699'}, query={'media_source': 'themoviedb', 'sites': '1'})
    assert not rejected.get('success') and rejected.get('error') == 'invalid_input'
    print('缺失媒体类型已被拦截', flush=True)
    for title, years, mtype in [('魅影神捕', {'2026'}, 'tv'), ('V字仇杀队', {'2005', '2006'}, 'movie')]:
        start = time.monotonic()
        result = call('media.search', query={'title': title, 'type': 'media', 'count': 8, 'page': 1})
        assert result.get('success'), f'{title} 媒体查询失败'
        media = next(item for item in result['data'] if str(item.get('year')) in years and item.get('media_source') == 'themoviedb')
        print(f'{title} 元数据查询成功，耗时 {time.monotonic() - start:.1f}s', flush=True)
        start = time.monotonic()
        result = call('search.torrents', path_params={'media_id': str(media['media_id'])}, query={
            'media_source': media['media_source'], 'mtype': mtype, 'sites': '1', 'count': 1, 'page': 1,
        })
        if not result.get('success') or not result.get('data'):
            print('搜索响应摘要', {key: result.get(key) for key in ('success', 'error', 'message', 'collection')},
                  'data类型', type(result.get('data')).__name__, 'fields', list(result), flush=True)
            raise AssertionError(f'{title} 资源搜索未返回候选')
        count = result.get('collection', {}).get('total_count', result.get('collection', {}).get('result_count', len(result['data'])))
        print(f'{title} 资源查询成功，结果数 {count}，耗时 {time.monotonic() - start:.1f}s', flush=True)
    for operation in ('download.tasks.active', 'download.history.list'):
        result = call(operation, query={'page': 1, 'count': 1}) if operation == 'download.history.list' else call(operation)
        assert result.get('success'), f'{operation} 查询失败'
        print(f'{operation} 可用', flush=True)
    db.rollback()
    after = db.execute('select count(*), max(id) from downloadhistory').fetchone()
    assert before == after, '测试期间下载历史发生变化，需要检查后台任务'
    print(f'下载历史未增加：{after[0]} 条。全部调用均为只读操作。', flush=True)
    session.close()
    db.close()


if __name__ == '__main__':
    main()
