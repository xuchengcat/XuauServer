# ShellCrash 节点订阅更新器

从订阅源获取节点，并直接更新 ShellCrash 主配置：

```text
/etc/ShellCrash/yamls/config.yaml
```

本项目不使用 `b.yaml`、`proxy-providers` 或中间订阅文件。节点会写入主配置的
`proxies`，并同步更新指定的 `proxy-groups`。

## 工作流程

1. 从 `.env` 读取订阅地址和运行参数。
2. 下载并解析 Clash YAML 或 Base64 节点订阅。
3. 检查节点字段、端口、重复名称和最低节点数量。
4. 调用当前 Mihomo 核心验证节点配置。
5. 更新主配置中的 `proxies` 和指定策略组；组内存在 `filter` 时按节点名称筛选。
6. 原子替换主配置，然后重启 ShellCrash。

任一下载、解析或验证步骤失败，均不会覆盖现有配置。修改前的主配置保存在：

```text
/etc/ShellCrash/yamls/.vpnupdate-backups/
```

## 环境要求

- Python 3.9 或更高版本
- PyYAML 6.x
- 已安装并正常运行的 ShellCrash/Mihomo
- 正式更新时具备修改 `/etc/ShellCrash` 和重启服务的 root 权限

安装依赖：

```bash
python3 -m pip install -r requirements.txt
```

## 配置

首次使用时创建本地环境文件：

```bash
cp .env.example .env
chmod 600 .env
```

编辑 `.env`，至少填写完整的订阅地址：

```dotenv
SUBSCRIPTION_URL=https://example.com/subscribe?token=replace-me
```

| 变量 | 默认值 | 用途 |
| --- | --- | --- |
| `SUBSCRIPTION_URL` | 无 | 完整订阅地址，必填 |
| `CONFIG_PATH` | `/etc/ShellCrash/yamls/config.yaml` | ShellCrash 主配置路径 |
| `MIHOMO_CORE` | `/tmp/ShellCrash/CrashCore` | Mihomo 核心路径 |
| `RESTART_COMMAND` | `systemctl restart shellcrash` | 更新后的重启命令 |
| `UPDATE_GROUPS` | `🚀 节点选择,🎮 Steam,🤖 ChatGPT` | 写入节点的策略组，逗号分隔 |
| `STEAM_TEST_URL` | `https://store.steampowered.com/` | Steam 策略组的健康检查地址 |
| `MIN_PROXY_COUNT` | `1` | 最少节点数，低于该值拒绝覆盖 |
| `HTTP_TIMEOUT` | `30` | 下载超时秒数 |
| `BACKUP_COUNT` | `5` | 主配置备份保留数量 |

`.env` 已加入 `.gitignore`。不要提交订阅 URL、token、UUID 或节点密码。

## 使用

先执行只读验证，不修改配置、不重启服务：

```bash
./refresh_config.sh --dry-run
```

验证通过后正式更新：

```bash
sudo ./refresh_config.sh
```

### 普通用户读取权限

dry run 不要求 root，但需要读取主配置。如果主配置为 `root:shellcrash 640`，
可仅授予当前用户读取权限：

```bash
sudo setfacl -m "u:$(id -un):r--" /etc/ShellCrash/yamls/config.yaml
```

正式更新会原子替换主配置，不保留这项单文件 ACL；替换后需要重新授予。

### 订阅服务器专用分流

本机排查发现，`47.242.128.61:5000` 经 HY2 节点访问失败，而
“新加坡-优化-GPT”和“香港-优化”可以下载订阅。可使用仓库中的
`shellcrash/` 配置片段，为该 IP 建立独立的 `subscription` 故障切换组。
它直接检查目标服务器，每 60 秒检测一次，优先新加坡，失败时切换香港。

1. 将 `shellcrash/proxy-groups.yaml` 中的策略组合并到
   `/etc/ShellCrash/yamls/proxy-groups.yaml`。保留其他策略组，同名组只留一份。
   示例中的 `oversea` 使用 `include-all: true`，替代已经删除的 provider `b`。
2. 将 `shellcrash/rules.yaml` 中的 IP 规则放在
   `/etc/ShellCrash/yamls/rules.yaml` 最前面，保留已有规则。
3. 两个文件都是 YAML 列表，不添加 `proxy-groups:` 或 `rules:` 顶层标题。
4. 重启并以普通用户验证：

```bash
sudo systemctl restart shellcrash
./refresh_config.sh --dry-run
```

不要直接覆盖整个自定义文件。此配置依赖示例中的节点名称；部署到其他订阅或
节点被重命名、删除时，应同步调整策略组。故障切换不能保证服务始终可用。

更新器仅写入 `CONFIG_PATH` 指定的主配置，不修改这两个自定义文件。
对于 `fallback` 策略组，更新器保留仍然有效的节点优先顺序，新节点追加到末尾，
避免订阅刷新改变 ChatGPT 等服务的优先出口。
ShellCrash 重启时会重新合并它们，因此规则不会被正常订阅更新覆盖。
当前更新器只调用核心验证订阅节点，不会验证 ShellCrash 最终合并后的自定义配置。

## 定时更新

当前服务器使用 systemd timers，时区为 Asia/Shanghai：

| 时间 | 任务 | Timer |
| --- | --- | --- |
| 每天 04:17 左右 | 刷新订阅，检查最终配置，有变化才重启 | `shellcrash-subscription-update.timer` |
| 每天 04:47 左右 | 检查并更新 GeoIP、GeoSite、CN IPv4/IPv6 列表 | `shellcrash-geodata-update.timer` |

两个任务共享互斥锁，防止同时修改文件或重启服务。关机错过的执行会在开机后补跑。
ShellCrash 停止时跳过更新。下载或校验失败保留原文件；重启失败则恢复旧文件并重启。
任务日志保存在 systemd journal，不包含订阅地址或节点凭据。

2026-10-23 修复：`shellcrash/fw_getlanip.sh` 按 `via` 关键字读取 IPv6 网关，
跳过 PPPoE 的 `default dev pppoe_dial`，避免把接口名写入 nftables 地址集合。
本机关闭保守模式（`start_old=OFF`），统一由 systemd 管理，避免核心在运行但
systemd 显示 inactive、定时更新被跳过的情况。
已恢复 `shellcrash.service` 开机启动，并移除禁用启动标记（原标记已备份）。
`systemd/shellcrash.service.d/privileges.conf` 明确以 root 运行启动/停止钩子及核心，
保留 `shellcrash` 组（GID 7890）供防回环规则使用。
重启后同时检查控制器、systemd 状态和本机代理链的 IPv6 保护规则；缺失则报错并回滚。
手动 `refresh_config.sh` 正式更新自动通过 sudo 提权，直接运行 Python 正式更新时必须为 root。

Geo 更新保留当前全球版/精简版 GeoIP 类型。只有数据实际变化才重启，已通过配置版本检查
的任务直接结束；使用 `--force-check` 可以强制下载并校验而不强制重启。
MRS 规则集仍由 Mihomo 按配置的 86400 秒周期自动刷新。

安装或更新 unit 文件：

```bash
sudo install -m 644 systemd/shellcrash-*.service systemd/shellcrash-*.timer /etc/systemd/system/
sudo install -D -m 644 systemd/shellcrash.service.d/privileges.conf /etc/systemd/system/shellcrash.service.d/privileges.conf
sudo install -m 755 shellcrash/fw_getlanip.sh /etc/ShellCrash/starts/fw_getlanip.sh
sudo systemctl daemon-reload
sudo systemctl enable --now shellcrash-subscription-update.timer shellcrash-geodata-update.timer
```

检查执行计划和最近日志：

```bash
systemctl list-timers 'shellcrash-*-update.timer'
sudo journalctl -u shellcrash-subscription-update.service -u shellcrash-geodata-update.service -n 60
```

手动执行同一套维护逻辑：

```bash
sudo systemctl start shellcrash-subscription-update.service
sudo systemctl start shellcrash-geodata-update.service
sudo flock --wait 300 /run/lock/shellcrash-maintenance.lock python3 maintain_shellcrash.py geodata --force-check
```

订阅备份仍受 `.env` 中的 `BACKUP_COUNT` 控制；重启失败使用的临时回滚数据只保存在进程内存。
ShellCrash 自身升级可能覆盖 `starts/fw_getlanip.sh`，升级后应复查或重新安装此修复文件。
本次修复前的文件保存在 `/mnt/SDD128G/maintenance-backups/shellcrash-fix-20261023/`。

回归检查：`python3 -m unittest discover -s . -p 'test_shellcrash_health.py' -v`。

### 2026-11-18 节点入口 DNS 与冷启动修复

节点自身的解析与 OpenAI 目标域名的解析是两条独立链路。节点入口曾被明文 DNS
解析到不可用 IP；因此只保护 `chatgpt.com` 等目标域名仍会出现 TLS 握手 EOF。
当前 `/etc/ShellCrash/yamls/user.yaml` 使用经本机直连、验证 TLS 证书的国内 DoH：

```yaml
dns:
  proxy-server-nameserver:
    - https://223.5.5.5/dns-query#DIRECT
    - https://1.12.12.12/dns-query#DIRECT
```

此项应合并到已有 `dns`，保留 OpenAI 独立 DNS、局域网域名策略和 Fake-IP 白名单。
直接使用加密 DNS 的 IP 地址，避免引入解析 DNS 服务器域名的额外依赖；不固定节点 IP。

GPT fallback 健康检查改为 `https://1.1.1.1/cdn-cgi/trace`，状态码为 `200/302`。
Mihomo 探测发送 HEAD，该地址在验证时返回 302；不跟随重定向，避免再引入域名解析。
这使健康检查不再依赖经 GPT 分组发送的 ChatGPT DNS，故障线路可以自动切换。
它检查 TLS/HTTP 连通性，账号、模型调用和长连接另需实际验证。节点优先顺序和
300 秒检查周期保留，订阅更新器会保留这些组参数。

`/etc/ShellCrash/configs/ShellCrash.cfg` 的 `start_delay=60`，systemd 启动超时为
90 秒。通过清除临时启动标记再重启服务，实测冷启动等待路径；没有重启整台服务器。

维护脚本在更新前和重启后拒绝明文/依赖代理的节点 DNS、DNS 与健康检查相互依赖的
配置；同时要求 systemd 超时至少比延迟多 15 秒。本地控制器检查直接连接回环地址，
不依赖代理环境。正常订阅和 Geo 更新不会覆盖 `user.yaml`、启动延迟或健康检查参数。

本次生产配置备份仅 root 可读，位于
`/mnt/SDD128G/maintenance-backups/codex-shellcrash-fix-20261118-205222/`。
定位与修复验证记录位于 `/mnt/SDD128G/codex/codex-proxy-diagnosis-20261118/`。

## 文件说明

```text
.
├── .env.example            # 环境变量模板
├── .gitignore              # 敏感文件和缓存忽略规则
├── README.md               # 使用文档
├── refresh_config.sh       # 命令行入口
├── requirements.txt        # Python 依赖
├── shellcrash/             # 订阅服务器分流规则与策略组示例
└── update_subscription.py  # 下载、解析、验证及更新逻辑
```

本地 `.env` 含敏感数据，不应进入版本控制。


## 家庭服务 speedtest 域名策略（2026-11-18）

对外域名为 `<服务名>.speedtest.xuchengcat.cn:444`。持久分流位于
`/etc/ShellCrash/yamls/rules.yaml`，最前面保留以下规则：

```yaml
- DOMAIN-SUFFIX,speedtest.xuchengcat.cn,DIRECT
- DOMAIN-SUFFIX,xuchengcat.cn,DIRECT
```

`service_domain_policy.py` 提供规则合并、持久/运行配置校验、候选验证与维护锁。
预览不联网、不写入、不重启：

```bash
python3 /mnt/SDD128G/vpnupdate/service_domain_policy.py
```

正式安装（幂等；核心校验通过后发布，失败恢复规则并启动旧配置）：

```bash
sudo python3 /mnt/SDD128G/vpnupdate/service_domain_policy.py --apply
```

手动订阅、定时维护、媒体路由安装及上述安装器在 Python 入口共用
`/run/lock/shellcrash-maintenance.lock`；systemd ExecStart 不再外套 flock，避免嵌套锁。
当前 timer 时间不变。无节点变化时仍验证域名策略，不无条件重启。
缺失或被覆盖的规则会明确报错，应先检查持久片段，不能通过只改
`/tmp/ShellCrash/config.yaml` 修复。

公网 DNS/DDNS、系统 hosts 与域名 IP 映射由用户管理。本次保留既有
`+.xuchengcat.cn -> 127.0.0.1:53` 转发及 fake-IP whitelist 模式；不向白名单
加入 speedtest 后缀，不切换全局 DNS 模式。
Shadowrocket/Clash 订阅生成项目 `clashsubscribemerge` 的现有通配绑定保持原样，
客户端匹配行为留待后续验证。

离线回归测试：

```bash
python3 -m unittest discover -s /mnt/SDD128G/vpnupdate -p 'test_*.py' -v
```

回滚时先恢复本次备份的 Python 脚本、rules.yaml、配套 systemd unit，再执行
`systemctl daemon-reload` 并校验/恢复 ShellCrash；旧 unit 的 flock 与新 Python 锁
不能混用。备份位于本次迁移工作目录 `backup/`，其中含私密配置，勿公开。
