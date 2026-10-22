# MoviePilot 本地修复

基于 `jxxghp/moviepilot-v3:3.0.1` 构建 `moviepilot-local:3.0.1-media-fixes`。
数据库、缓存、插件和运行配置仍保存在被 Git 忽略的 `config/`、`core/`。

```bash
docker compose build moviepilot
docker compose up -d --no-deps --no-build moviepilot
```

`fixes/apply.py` 在镜像构建时应用严格匹配的补丁。上游源码不再匹配时构建失败，
需要重新审查补丁，不能直接更换基础版本。运行中执行 MoviePilot 自更新可能替换
已修复源码；此部署应通过审查基础镜像版本并重新构建升级。

## 已修复行为

- `search.torrents`、`search.title` 的内部读取超时为 180 秒；`media.search` 为 60 秒。
  写操作维持 30 秒，绝不自动重试。OpenClaw 对 MoviePilot 的 MCP 外层超时为 240 秒，
  该私有配置在 `openclaw/config/openclaw.json`，不提交 Git。
- MCP 合同和执行器都要求资源精确搜索显式传入 `mtype`。
  搜索超时返回 `search_timeout`，不能解释为零资源。
- 种子 HTTP GET 仅在传输异常时重试一次；POST、403 和 429 不重试。
  日志保留异常类型，不输出含凭据的下载地址。
- OpenClaw 的 `media-assistant` 保留重试参数，使用实际支持的
  `download.tasks.active`、`download.history.list`，检查已有任务和完成记录。
  精确搜索从小页开始；遇到 65536 字符的结果截断时缩到每页 1 条，
  重新获取完整候选，不从预览拼接下载链接。GET 搜索站点 ID 使用字符串，分页从 1 开始。

TMDB 使用 `🎬 媒体元数据` 独立 fallback 组，每 300 秒检测一次，
探测未携带 API key 的 `/3/configuration`，预期 HTTP 401 表示服务可达。
已验证的三个出口为新加坡优化、美国 LA 优化、香港 WAP 优化 2。
持久化于 ShellCrash 自定义规则和策略组；订阅更新保持该自定义组。

```bash
sudo flock --wait 300 /run/lock/shellcrash-maintenance.lock \
  python3 vpnupdate/configure_media_route.py
```

脚本发布前校验 Mihomo 配置，保存本地回滚副本，重启后核查生效，失败恢复旧配置。

## 验证

`fixes/test_regressions.py` 用 pytest 从实际修复源码加载被测类/方法；
网络、身份、配置和日志全部隔离替换，绝不接触实际数据库或下载器。
把修复后源码复制到临时目录再执行，例如：

```bash
mkdir -p /tmp/mediafix-source/app/agent/api /tmp/mediafix-source/app/agent/policy/resources /tmp/mediafix-source/app/startup/composition
docker cp moviepilot:/app/app/agent/api/executor.py /tmp/mediafix-source/app/agent/api/executor.py
docker cp moviepilot:/app/app/agent/policy/mcp.py /tmp/mediafix-source/app/agent/policy/mcp.py
docker cp moviepilot:/app/app/agent/policy/resources/api_mcp_schema.json /tmp/mediafix-source/app/agent/policy/resources/api_mcp_schema.json
docker cp moviepilot:/app/app/startup/composition/site.py /tmp/mediafix-source/app/startup/composition/site.py
MOVIEPILOT_SOURCE=/tmp/mediafix-source python3 -m pytest -q moviepilot/fixes/test_regressions.py
```

`fixes/smoke_readonly.py` 是单独的线上只读诊断，并非 pytest 测试：
通过 OpenClaw 同一凭据调用 MCP，仅允许查询媒体、搜索资源、读取下载状态和历史，
禁止调用下载添加接口，结束时核对下载历史未增加。输出不包含资源下载链接。

```bash
sudo python3 moviepilot/fixes/smoke_readonly.py
```

当前发布镜像不包含上游开发文档和完整 tests，未宣称通过上游完整测试套件。

2026-10-22 验证记录：16 项隔离回归通过；线上 MCP 精确搜索返回
《魅影神捕》94 个、《V字仇杀队》41 个候选；缺失 `mtype` 被拒绝，
状态/历史读取可用，验证前后下载历史均为 33 条。未调用 `download.add`，
未重新获取这两部资源的种子文件；种子读取的异常重试只通过替身测试验证。
