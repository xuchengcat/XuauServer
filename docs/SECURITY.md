# 安全与注意事项

## 1. 需要优先处理的事项

检查仓库时发现，若干已跟踪配置或脚本中存在明文密码、长期令牌、API key、摄像头地址或服务访问密钥。即使现在加入 `.gitignore`，已经提交过的内容仍可能存在于 Git 历史和远端副本中。

建议按以下顺序处理：

1. 立即轮换受影响的 Home Assistant、ZeroTier、Frigate Plus、摄像头、MQTT、Transmission、PhotoPrism、Homepage 小组件、代理和其他服务凭据。
2. 把值迁移到未跟踪的 `.env`、Docker secrets 或权限为 `0600` 的独立配置中；仓库只保留 `.example` 模板。
3. 使用 secret scanner 检查当前树和 Git 历史，例如 Gitleaks 或 TruffleHog。
4. 如果仓库曾推送到远端，在轮换后再评估是否重写历史；重写历史不能替代凭据轮换。
5. 检查日志、备份、维护快照和容器 inspect 输出，因为它们也可能保存旧凭据。

本文档不列出任何实际凭据值。

## 2. 网络暴露

以下入口风险较高，应只允许可信 LAN、ZeroTier 或经强认证的反向代理访问：

- Frigate `5000`：配置注释明确为未认证内部接口。
- Docker 管理面：Dockhand、Portainer、Homepage 的 Docker socket，以及 Glances。
- SSHwifty：能够发起 SSH/Telnet 连接。
- Node-RED、ESPHome、Home Assistant 和 Nginx Proxy Manager 管理界面。
- iperf3、KMS、MQTT、RTSP/WebRTC 端口。
- XiaoMusic 当前设置为禁用 HTTP 认证。

不要只依赖“没有在 Compose 中映射端口”判断安全性：同一 Compose 网络内的其他容器仍能访问服务，反向代理也可能将其公开。

## 3. 高权限容器

- `homeassistant` 和 `glances` 使用 `privileged: true`。
- `dockhand` 挂载可写 Docker socket 和整个 `/mnt/SDD128G`。
- `portainer`、`homepage`、`glances` 也挂载 Docker/Podman socket；即使标记只读，Docker API 访问仍是高敏感能力。
- `zerotier` 使用 host 网络、TUN、`NET_ADMIN` 和 `SYS_ADMIN`。
- `openclaw` 挂载宿主机的 Codex 用户目录，其中可能含登录状态、配置和会话。

这些服务一旦被攻破，影响范围可能达到整个主机。应限制访问来源、启用独立强密码/MFA（若支持）、及时更新并减少不必要的挂载。

## 4. 存储与权限

- 多数服务假设 UID/GID 为 `1000:1000`。迁移主机时先核对 `id`，不要用全局 `chmod -R 777` 解决权限问题。
- WebDAV、Transmission、MoviePilot、PhotoPrism 等对媒体目录具有写权限，路径配置错误可能造成移动、覆盖或删除。
- 外部盘未挂载时容器可能向根盘同名目录写数据。启动前使用 `findmnt -T <具体路径>`，仅检查目录是否存在并不够。
- 数据目录中可能包含个人照片、监控录像、家庭自动化状态和账号信息；备份介质也应加密和限制访问。

## 5. 数据库一致性

根 Compose 中的 Nextcloud 服务把 `/mnt/HDD14T/mariadb_data` 挂到 Nextcloud 容器的 `/var/lib/mysql`，但同一 Compose 没有 MariaDB 服务。官方 `nextcloud:apache` 镜像本身不运行 MariaDB。必须核对实际 Nextcloud 数据库连接方式；不要把这个目录挂载视作有效的数据库服务或可靠备份。

此外：

- SQLite 的 `*.db`、`-wal`、`-shm` 应作为同一组处理。
- 不要在服务运行时复制单个 SQLite 主文件并假定可恢复。
- Nextcloud 文件目录和数据库必须使用一致的恢复点。
- 更新应用产生 schema migration 后，旧镜像可能无法安全读取新数据库。

## 6. 硬件与宿主机依赖

- Jellyfin、PhotoPrism 和 Frigate 依赖 Intel `/dev/dri`；设备 group ID 在不同机器上可能不是 `226`。
- Frigate 依赖 Coral `/dev/apex_0` 和 Gasket 驱动；驱动升级、内核升级或 Secure Boot 都可能导致设备消失。
- ZeroTier 依赖 `/dev/net/tun`。
- Home Assistant 使用 host 网络、DBus 和特权模式；蓝牙、mDNS 等发现行为与普通 bridge 容器不同。
- 路由、PPPoE、防火墙和 ShellCrash 配置会直接影响远程连接。修改这些配置前应保留本地控制台或带外恢复路径。

## 7. 镜像和供应链

- 多个服务使用 `latest`、`stable` 或第三方镜像；重新拉取可能引入不可预期变更。
- 重要服务建议固定经过验证的版本，进一步可固定 digest。
- 本地 `openclaw` 镜像应在 Dockerfile 或依赖变更后重新审查和构建。
- 不要从不可信来源执行安装脚本、Compose 或固件；TPU DKMS 包会在宿主机内核中运行，风险高于普通容器。

## 8. 独立 Compose 冲突

根 Compose 已包含多个也存在于子目录 Compose 的服务。重复启动会造成：

- 固定 `container_name` 冲突；
- 主机端口冲突；
- 两个实例同时写同一数据库/配置目录；
- 不同镜像版本对同一数据执行不兼容迁移。

操作前用以下命令确认实际归属：

```bash
docker compose -f /mnt/SDD128G/docker-compose.yml ps
docker ps --format 'table {{.Names}}\t{{.Image}}\t{{.Ports}}'
```

当前约定以根 Compose 为主，不应把子目录 Compose 当成额外副本直接启动。
