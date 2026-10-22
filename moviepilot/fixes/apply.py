"""为当前固定版本应用可重复构建的本地修复；源码漂移时停止构建。"""

from pathlib import Path
import json
import sys


def replace_once(text: str, old: str, new: str) -> str:
    """严格匹配修改位置，避免镜像升级后静默修改错误代码。"""
    if text.count(old) != 1:
        raise ValueError(f"修复锚点不唯一或已变化：{old[:70]!r}")
    return text.replace(old, new, 1)


def patch_executor(text: str) -> str:
    """长搜索使用独立超时，并在请求前拒绝缺失媒体类型的搜索。"""
    text = replace_once(text, '        request = self._request_factory(\n', '''        if operation_id == "search.torrents" and not query_data.get("mtype"):
            return json.dumps({
                "success": False,
                "error": "invalid_input",
                "message": "search.torrents 必须传 mtype（movie/tv/music）；请从已选媒体复制类型，重试时保留。",
            }, ensure_ascii=False)
        # 站点单次请求允许 60 秒，别名搜索可能继续执行；写操作维持原超时且不重试。
        timeout = 180 if operation_id in {"search.torrents", "search.title"} else 30
        if operation_id == "media.search":
            timeout = 60
        request = self._request_factory(
''')
    text = replace_once(text, '            timeout=30,\n', '            timeout=timeout,\n')
    text = replace_once(text, '            transport_failed = isinstance(error, (AsyncHttpRequestError, ConnectionError, TimeoutError))\n', '''            if operation_id in {"search.torrents", "search.title"} and (
                isinstance(error, TimeoutError) or stable_type_name(error) in {"ReadTimeout", "ConnectTimeout"}
            ):
                return json.dumps({
                    "success": False,
                    "error": "search_timeout",
                    "message": "资源搜索超时，后台可能仍在执行；不能据此判断没有资源。稍后保留原媒体身份、mtype 和站点重查。",
                }, ensure_ascii=False)
            transport_failed = isinstance(error, (AsyncHttpRequestError, ConnectionError, TimeoutError))
''')
    return text


def patch_contract(text: str) -> str:
    """让 MCP 输入合同也要求显式媒体类型，避免模型反复遗漏。"""
    return replace_once(text, '    if operation_id == "media.person.search" and query_schema is not None:\n', '''    if operation_id == "search.torrents" and query_schema is not None:
        required = query_schema.setdefault("required", [])
        if "mtype" not in required:
            required.append("mtype")
        query_schema["properties"]["mtype"]["description"] = (
            "Required media type copied from the selected identity: movie, tv, or music. "
            "Preserve this value on every retry; a bare TMDB ID does not identify its type."
        )
    if operation_id == "media.person.search" and query_schema is not None:
''')


def patch_schema(text: str) -> str:
    """同步运行时加载的预生成 MCP 合同。"""
    schema = json.loads(text)
    branch = next(item for item in schema['oneOf'] if item.get('title') == 'search.torrents')
    query = branch['properties']['query']
    if 'mtype' in query.get('required', []):
        raise ValueError('MCP 合同已包含修复，请重新审查基础版本')
    query.setdefault('required', []).append('mtype')
    query['properties']['mtype']['description'] = (
        'Required media type copied from the selected identity: movie, tv, or music. '
        'Preserve this value on every retry; a bare TMDB ID does not identify its type.'
    )
    return json.dumps(schema, ensure_ascii=False, indent=2, sort_keys=True) + '\n'


def patch_site(text: str) -> str:
    """仅在种子 GET 的传输异常后重试一次，保留 HTTP 错误且不重试 POST。"""
    text = replace_once(text, 'from app.adapters.network.http import RequestUtils\n',
                        'from app.adapters.network.http import HttpRequestError, RequestUtils\nfrom app.runtime.log import logger\n')
    start = text.index('class _TorrentHttpAdapter:')
    end = text.index('\n\nclass _SiteHttpAdapter:', start)
    old = text[start:end]
    new = old[:old.index('        if method == "POST":')] + '''        attempts = 2 if method.upper() == "GET" else 1
        for attempt in range(attempts):
            try:
                response = request.request(
                    method=method, url=url, data=data,
                    allow_redirects=allow_redirects, raise_exception=True,
                )
                return cast(Optional[TorrentResponsePort], response)
            except HttpRequestError as error:
                # 下载地址含临时令牌，日志只记录异常类型，不记录 URL 或异常文本。
                logger.warning(
                    f"种子 HTTP 传输失败：{type(error).__name__}，尝试 {attempt + 1}/{attempts}"
                )
        return None
'''
    return text[:start] + new + text[end:]


PATCHES = {
    "app/agent/api/executor.py": patch_executor,
    "app/agent/policy/mcp.py": patch_contract,
    "app/agent/policy/resources/api_mcp_schema.json": patch_schema,
    "app/startup/composition/site.py": patch_site,
}


def apply(root: Path) -> None:
    """先验证所有修改，再写文件，防止部分应用。"""
    changed = {root / name: patch((root / name).read_text()) for name, patch in PATCHES.items()}
    for path, content in changed.items():
        if path.suffix == '.py':
            compile(content, str(path), "exec")
        else:
            json.loads(content)
    for path, content in changed.items():
        path.write_text(content)
        print(f"Patched {path.relative_to(root)}")


if __name__ == "__main__":
    apply(Path(sys.argv[1]))
