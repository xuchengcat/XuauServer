# Codex 开机自启动

服务器每次开机满 5 分钟后，以 `xuau` 用户检查当前 Codex 登录账号和默认模型是否可用，通过后创建 `codex_long` tmux 会话，在 `/mnt/SDD128G/codex` 中运行 `codex --yolo`。

## 文件位置

- `codex-long-start.sh`：启动与可用性检查脚本，直接从本目录执行。
- `systemd/codex-long.service`：服务配置的 Git 源文件。
- `systemd/codex-long.timer`：开机延时配置的 Git 源文件。
- `environment.example`：可选代理环境模板，不包含真实凭据。
- `/etc/systemd/system/codex-long.{service,timer}`：安装到系统中的配置副本。
- `/home/xuau/.config/codex-long/environment`：本机私有环境配置，不进入 Git。

本目录随父仓库 `xuchengcat/XuauServer` 管理，无需新建独立仓库。目标用户名、目录和 Codex 路径已按当前服务器固定；迁移服务器时需要修改脚本及 service。

## 启动行为

1. systemd 系统定时器使用 `OnBootSec=5min`，无需用户登录，也无需开启 linger。系统调度和依赖就绪可能使启动稍晚于 5 分钟。
2. 服务等待网络目标及目录挂载。代理服务若在启动中，会先等待其启动任务结束；代理真正可用由后续请求检查。
3. 如果 `codex_long` 已存在，直接成功退出，不向会话发送命令、不重启其中的进程。
4. 否则使用现有 `~/.codex` 登录和配置，在空临时目录中执行一次 `codex exec`，要求模型仅回复 `CODEX_READY`。探测使用只读沙箱，超时 120 秒，可能产生少量模型用量。临时输出在结束后删除，日志不输出认证信息或代理地址。
5. 探测失败后由 systemd 每隔 60 秒重试，直到成功。探测成功后创建会话，并在面板内重新载入私有代理环境，再执行 `/home/xuau/.local/bin/codex --yolo`。
6. 文件锁避免并发执行；创建前再次检查同名会话。工作目录不可访问或 Codex 不存在时也会重试。

这是开机启动任务，不持续监控 Codex 存活。手动退出 Codex 后不会自动重拉。重启会创建新的 Codex 对话，不自动恢复以前的对话。已有同名空会话也会跳过，需要人工处理。

## 安装

依赖：systemd、tmux、Bash、GNU coreutils、flock，以及已经登录的 Codex CLI。当前服务器启用了本地 ShellCrash 代理。

如需代理，先配置私有环境文件：

```bash
install -d -m 700 /home/xuau/.config/codex-long
install -m 600 /mnt/SDD128G/codex-autostart/environment.example \
  /home/xuau/.config/codex-long/environment
# 编辑上述文件，填入本机代理配置；不要覆盖已有的有效配置。
```

真实凭据仅保存在上述私有文件或 Codex 自有认证文件中，不要放入本目录。初次部署已从本机原有 Codex 启动配置迁移代理设置。

安装并启用：

```bash
chmod +x /mnt/SDD128G/codex-autostart/codex-long-start.sh
sudo install -m 644 /mnt/SDD128G/codex-autostart/systemd/codex-long.service /etc/systemd/system/
sudo install -m 644 /mnt/SDD128G/codex-autostart/systemd/codex-long.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now codex-long.timer
```

若当前开机已超过 5 分钟，首次启用定时器会立即触发检查；同名会话存在时直接跳过。之后每次重启在开机满 5 分钟时触发。更新仓库中的 systemd 配置后，需要重新安装副本并执行 `daemon-reload`；脚本修改直接生效。

## 查看和验证

```bash
# 只检查账号和模型，不创建或改动 tmux 会话
/mnt/SDD128G/codex-autostart/codex-long-start.sh --probe-only

systemctl status codex-long.timer codex-long.service
systemctl list-timers --all codex-long.timer
journalctl -u codex-long.service -b --no-pager
tmux attach -t codex_long

# 手动触发一次启动；已有同名会话时跳过
sudo systemctl start codex-long.service
```

服务是 `oneshot`，成功后显示 `inactive (dead)` 属于正常现象；检查日志和 tmux 会话确认结果。`KillMode=process` 使启动服务结束或停止时不会连带终止 tmux 服务及会话。

停用自启动和失败重试：

```bash
sudo systemctl disable --now codex-long.timer
sudo systemctl stop codex-long.service
```

停用不会结束已经存在的 tmux 会话。本配置不安排服务器重启；真实开机行为在下一次计划重启后通过日志核验。
