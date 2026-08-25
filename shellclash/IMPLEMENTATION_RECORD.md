# ShellCrash 配置实施记录

实施日期：2026-08-25
系统时区：Asia/Shanghai

## 实施目标

- 通过 provider `b` 动态更新订阅节点。
- 保留原有 PT、小米、Captive Portal 和 ZeroTier 等自定义直连规则。
- 删除普通策略组 `b`，但保留同名 provider。
- `🚀 节点选择` 直接包含 provider `b` 的全部节点。
- 保持 `🎯 本地直连` 的结构不变。
- 新增 `🎮 Steam` 和 `🤖 ChatGPT` 自动测速组。
- Steam 组只包含亚洲节点。
- ChatGPT 组只包含名称带 `GPT` 的节点。
- 两个自动测速组均不包含 `DIRECT` 或其他策略组。
- 每天 00:00 刷新订阅并对两个专用组测速一次。
- 隐藏 Mihomo 内置 `GLOBAL` 组。

## 最终文件

持久配置：

- `/etc/ShellCrash/yamls/config.yaml`
- `/etc/ShellCrash/yamls/rules.yaml`

运行时配置：

- `/tmp/ShellCrash/config.yaml`

定时测速：

- `/etc/ShellCrash/task/daily_group_test.sh`
- `/etc/cron.d/shellcrash-daily-group-test`
- `/etc/ShellCrash/task/daily_group_test.log`

工作副本及安装材料：

- `/mnt/SDD128G/shellclash/config.yaml`
- `/mnt/SDD128G/shellclash/rules.yaml`
- `/mnt/SDD128G/shellclash/daily_group_test.sh`
- `/mnt/SDD128G/shellclash/shellcrash-daily-group-test.cron`
- `/mnt/SDD128G/shellclash/install.sh`

## Provider 更新机制

provider `b` 保留订阅更新功能：

```yaml
proxy-providers:
  b:
    type: http
    path: "./providers/b.yaml"
    interval: 43200
    health-check:
      enable: false
```

- Mihomo 每 43200 秒（12 小时）自动刷新一次订阅。
- 节点缓存位于 `/etc/ShellCrash/providers/b.yaml`。
- 节点新增、删除或改名后，所有使用 `use: [b]` 的组会动态更新。
- 主配置不保存展开后的节点列表，因此订阅更新不会覆盖自定义分组和规则。
- `health-check.enable: false` 只关闭 provider 周期测速，不影响订阅更新。

## 最终策略组结构

### 🚀 节点选择

- 类型：`select`
- 通过 `use: [b]` 直接包含订阅的全部节点。
- 不再经过普通策略组 `b`。
- 实施完成时共有 30 个候选节点。
- 实施完成时选择：`新加坡-优化-GPT`。

### 🎯 本地直连

- 类型：`select`
- 候选项保持为 `DIRECT` 和 `🚀 节点选择`。
- 实施完成时选择：`DIRECT`。

### 🎮 Steam

- 类型：`url-test`
- 数据来源：provider `b`。
- 通过节点名称过滤亚洲地区节点。
- 不包含 `DIRECT`、`🚀 节点选择` 或其他策略组。
- `interval: 0`，不从核心启动时间开始自行进行周期测速。
- `tolerance: 100`，减少延迟差异较小时的频繁切换。
- 实施完成时共有 16 个亚洲候选节点。
- 首次测速选择：`香港WAP-优化`。

### 🤖 ChatGPT

- 类型：`url-test`
- 数据来源：provider `b`。
- 使用 `(?i)GPT` 过滤名称带 GPT 的节点。
- 不包含 `DIRECT`、`🚀 节点选择` 或其他策略组。
- `interval: 0`，由零点任务触发测速。
- `tolerance: 100`。
- 实施完成时共有 7 个候选节点。
- 首次测速选择：`英国-优化-GPT`。

### GLOBAL

- `GLOBAL` 是 Mihomo 的内置策略组，无法真正删除。
- 已显式设置 `hidden: true`。
- 当前 Web API 已返回 `hidden: true`。
- 系统保持 Rule 模式，不使用 GLOBAL 进行日常分流。

## 每日零点任务

cron 配置：

```cron
0 0 * * * root /etc/ShellCrash/task/daily_group_test.sh >/dev/null 2>&1
```

任务流程：

1. 尝试主动刷新 provider `b`。
2. 等待 provider 更新。
3. 触发 `🎮 Steam` 组测速。
4. 触发 `🤖 ChatGPT` 组测速。
5. 将简短结果写入 `/etc/ShellCrash/task/daily_group_test.log`。

脚本包含互斥锁，避免重复执行。如果主动刷新 provider 失败，会记录警告并继续使用缓存节点完成两个组的测速，不会让整个任务中断。

首次手动测试日志：

```text
2026-08-25 15:58:18 +0800 provider b refreshed
2026-08-25 15:58:30 +0800 Steam test completed
2026-08-25 15:58:38 +0800 ChatGPT test completed
```

选择 cron 而不是 `interval: 86400`，是因为后者从核心加载配置的时刻开始计时，不能保证每天自然日 00:00 执行。

## 自定义规则

原有规则已保留，并新增以下类别：

- ChatGPT/OpenAI 官方服务域名 → `🤖 ChatGPT`
- Steam 商店、社区、登录、内容与联机服务 → `🎮 Steam`
- 饥荒及饥荒联机版的 Klei 服务 → `🎮 Steam`
- 战舰世界和 Wargaming 公共服务 → `🎮 Steam`

这些自定义规则位于以下通用规则之前：

```text
RULE-SET,privateip,🎯 本地直连
RULE-SET,cn,🎯 本地直连
RULE-SET,cnip,🎯 本地直连
MATCH,🚀 节点选择
```

因此专用分流规则具有更高优先级。

## 验证结果

- CrashCore 配置语法检查通过。
- 新核心进程已加载 `/tmp/ShellCrash/config.yaml`。
- 普通策略组 `b` 已不存在。
- `🚀 节点选择` 已直接包含 provider 的全部节点。
- `🎯 本地直连` 候选项保持不变。
- Steam API 类型为 `URLTest`，候选项均为亚洲节点。
- ChatGPT API 类型为 `URLTest`，候选项名称均带 GPT。
- 两个专用组均不含 `DIRECT` 或其他策略组。
- Steam 与 ChatGPT 测速接口均返回 HTTP 200。
- provider 主动刷新测试成功。
- cron 文件权限为 `root:root 0644`。
- 测速脚本权限为 `root:root 0755`。
- cron 服务正在运行。
- 持久配置在 ShellCrash 重启后仍然生效。

## 备份与回滚

实施前备份位于：

```text
/etc/ShellCrash/backups/codex-20260825-155418
```

该目录包含实施前的持久配置、规则文件和运行时配置。若后续需要回滚，应恢复其中的 `config.yaml` 与 `rules.yaml`，再通过 ShellCrash 菜单重启核心。

provider 缓存通常无需回滚。

## 安全说明

- 本记录未包含订阅 URL、访问令牌或代理认证信息。
- 工作目录中的候选 `config.yaml` 保留了实际订阅配置，应限制其读取和传播。
