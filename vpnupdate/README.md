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
ShellCrash 重启时会重新合并它们，因此规则不会被正常订阅更新覆盖。
当前更新器只调用核心验证订阅节点，不会验证 ShellCrash 最终合并后的自定义配置。

## 定时更新

使用 root 的 crontab，例如每天 04:17 更新：

```cron
17 4 * * * cd /mnt/SDD128G/vpnupdate && ./refresh_config.sh >>/var/log/vpnupdate.log 2>&1
```

配置定时任务前，建议先手动完成一次正式更新。

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
