"""对修复后的真实方法做隔离回归；HTTP、令牌、日志和配置均使用替身。"""

import ast
import asyncio
from dataclasses import dataclass
import json
import os
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Mapping, Optional, cast

import pytest


ROOT = Path(os.environ.get('MOVIEPILOT_SOURCE', '/tmp/mediafix-source'))


def load_nodes(relative, names, namespace):
    tree = ast.parse((ROOT / relative).read_text())
    selected = [node for node in tree.body if getattr(node, 'name', '') in names]
    assert len(selected) == len(names)
    module = ast.Module(body=[ast.ImportFrom(module='__future__', names=[ast.alias(name='annotations')], level=0)] + selected, type_ignores=[])
    exec(compile(ast.fix_missing_locations(module), relative, 'exec'), namespace)
    return namespace


@pytest.fixture
def harness():
    calls = []
    state = {'error': None, 'payload': {'success': True, 'data': [1]}}

    class RequestError(Exception):
        pass

    class Response:
        status_code = 200
        headers = {'x-result-count': '1'}
        async def aclose(self):
            state['closed'] = True
        def json(self):
            return state['payload']

    class Request:
        def __init__(self, **kwargs):
            calls.append(('init', kwargs))
        async def request(self, **kwargs):
            calls.append(('request', kwargs))
            if state['error']:
                raise state['error']
            return Response()

    effect = SimpleNamespace(SAFE_READ='read', SENSITIVE_READ='sensitive')
    namespace = dict(json=json, dataclass=dataclass, Any=Any, Mapping=Mapping,
                     AsyncRequestUtils=Request, AsyncHttpRequestError=RequestError,
                     ActionEffect=effect, logger=SimpleNamespace(warning=lambda *args: None),
                     stable_type_name=lambda error: type(error).__name__,
                     resolve_api_route=lambda operation: SimpleNamespace(method='POST' if operation == 'download.add' else 'GET', path='/api/test'),
                     resolve_api_operation=lambda operation: SimpleNamespace(effect='write' if operation == 'download.add' else 'read'))
    load_nodes('app/agent/api/executor.py', {'ApiExecutionError', 'ApiExecutionContext', 'MoviePilotApiExecutor'}, namespace)
    cls = namespace['MoviePilotApiExecutor']
    cls._resolve_base_url = staticmethod(lambda: 'http://127.0.0.1:3001')
    cls._build_headers = lambda self: {}
    executor = cls(context=None, request_factory=Request)
    return executor, calls, state, namespace


@pytest.mark.parametrize('operation,query,expected', [
    ('search.torrents', {'mtype': 'tv'}, 180),
    ('search.title', {'mtype': 'movie'}, 180),
    ('media.search', {}, 60),
    ('download.add', {}, 30),
    ('download.history.list', {}, 30),
])
def test_timeouts_preserve_write_behavior(harness, operation, query, expected):
    executor, calls, state, _ = harness
    result = json.loads(asyncio.run(executor.execute(operation, query=query)))
    assert result['success']
    assert calls[0][1]['timeout'] == expected
    assert sum(kind == 'request' for kind, _ in calls) == 1
    assert state['closed']


def test_missing_media_type_rejected_before_http(harness):
    executor, calls, _, _ = harness
    result = json.loads(asyncio.run(executor.execute('search.torrents', query={'media_source': 'themoviedb'})))
    assert result['error'] == 'invalid_input'
    assert not calls


def test_search_timeout_is_not_no_resources(harness):
    executor, calls, state, _ = harness
    state['error'] = TimeoutError()
    result = json.loads(asyncio.run(executor.execute('search.torrents', query={'mtype': 'tv'})))
    assert result['error'] == 'search_timeout'
    assert '后台' in result['message']
    assert len(calls) == 2


def test_unknown_write_outcome_never_retries(harness):
    executor, calls, state, namespace = harness
    state['error'] = TimeoutError()
    with pytest.raises(namespace['ApiExecutionError']) as error:
        asyncio.run(executor.execute('download.add', body={'torrent_in': {'title': 'fixture'}}))
    assert error.value.external_may_continue
    assert sum(kind == 'request' for kind, _ in calls) == 1


def test_explicit_media_identity_preserved(harness):
    executor, calls, _, _ = harness
    query = {'media_source': 'themoviedb', 'mtype': 'tv', 'sites': 1}
    asyncio.run(executor.execute('search.torrents', query=query))
    assert calls[-1][1]['params'] == query


def test_mcp_requires_media_type():
    namespace = load_nodes('app/agent/policy/mcp.py', {'_apply_operation_overrides'}, {})
    schema = {'properties': {'mtype': {'type': 'string'}}}
    namespace['_apply_operation_overrides']('search.torrents', schema, None)
    assert 'mtype' in schema['required']


def test_published_mcp_schema_requires_media_type():
    schema = json.loads((ROOT / 'app/agent/policy/resources/api_mcp_schema.json').read_text())
    branch = next(item for item in schema['oneOf'] if item.get('title') == 'search.torrents')
    assert 'mtype' in branch['properties']['query']['required']


@pytest.mark.parametrize('method,failures,status,expected_calls', [
    ('GET', 1, 200, 2), ('GET', 2, 200, 2), ('POST', 1, 200, 1),
    ('GET', 0, 403, 1), ('GET', 0, 429, 1),
])
def test_only_transport_failed_get_is_retried(method, failures, status, expected_calls):
    calls = []
    logs = []
    class RequestError(Exception):
        pass
    response = SimpleNamespace(status_code=status)
    class Request:
        def __init__(self, **kwargs):
            pass
        def request(self, **kwargs):
            calls.append(kwargs)
            if len(calls) <= failures:
                raise RequestError('private URL and token must not reach logs')
            return response
    namespace = dict(RequestUtils=Request, HttpRequestError=RequestError, cast=cast, TorrentResponsePort=Any,
                     Optional=Optional, logger=SimpleNamespace(warning=logs.append))
    load_nodes('app/startup/composition/site.py', {'_TorrentHttpAdapter'}, namespace)
    result = namespace['_TorrentHttpAdapter']().request(
        method=method, url='https://fixture.invalid/private', cookie=None,
        ua=None, referer=None, proxies=None,
    )
    assert len(calls) == expected_calls
    assert result is (None if failures >= expected_calls else response)
    assert all('private' not in line and 'token' not in line for line in logs)
    assert all(call['raise_exception'] is True for call in calls)
