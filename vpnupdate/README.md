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
5. 更新主配置中的 `proxies` 和指定策略组。
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
└── update_subscription.py  # 下载、解析、验证及更新逻辑
```

本地 `.env` 含敏感数据，不应进入版本控制。
