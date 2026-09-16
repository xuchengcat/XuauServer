# XuauServer

XuauServer 是一套运行在 Ubuntu 24.04 LTS x86-64 主机上的个人 Homelab 配置。项目以根目录的 Docker Compose 为主要编排入口，覆盖影音、智能家居、监控、存储、网络和运维服务；仓库中还包含少量独立 Compose、宿主机脚本、路由配置及灾难恢复工具。

> 这不是一套可在任意机器上直接启动的通用模板。Compose 使用了当前主机的绝对路径、设备节点、局域网地址和外部磁盘，部署前必须按实际环境调整。

## 文档

- [工程结构](docs/PROJECT_STRUCTURE.md)：目录职责、数据分层、服务之间的关系。
- [服务清单](docs/SERVICES.md)：每个服务的用途、入口、依赖和部署状态。
- [部署与运维](docs/OPERATIONS.md)：启动、更新、备份、恢复和常见检查。
- [安全与注意事项](docs/SECURITY.md)：凭据、网络暴露、权限、数据库和硬件相关风险。

## 快速开始

主服务栈由根目录 [`docker-compose.yml`](docker-compose.yml) 管理：

```bash
cd /mnt/SDD128G
docker compose config -q
docker compose up -d
docker compose ps
```

部署前至少需要：

1. 安装 Docker Engine 和 Docker Compose 插件。
2. 确认 `/mnt/SDD128G`、`/mnt/HDD14T`、`/mnt/HDD6T`、`/mnt/camera1t` 等挂载点存在且没有落到根分区的空目录。
3. 根据本机情况准备根目录 `.env`，以及 `webdav/`、`sgcc_elec/`、`moontvplus/` 等服务的私有环境文件。
4. 确认运行用户 UID/GID `1000:1000`、Intel `/dev/dri`、Coral `/dev/apex_0` 和 `/dev/net/tun` 等权限与设备节点。
5. 阅读[安全与注意事项](docs/SECURITY.md)，轮换仓库历史配置中曾出现的明文口令或令牌。

建议按服务分批启动，而不是在新主机上第一次就启动全部服务：

```bash
docker compose up -d mosquitto homeassistant node-red esphome
docker compose up -d transmission prowlarr moviepilot jellyfin
docker compose up -d nginx-proxy-manager homepage glances dockhand
```

## 服务概览

| 分类 | 服务 |
| --- | --- |
| 影音与内容 | Jellyfin、Kavita、MoonTVPlus、XiaoMusic、LyricAPI、MetaTube、PhotoPrism |
| 下载与整理 | Transmission、Prowlarr、MoviePilot、WebDAV |
| 智能家居 | Home Assistant、Node-RED、ESPHome、Mosquitto、SGCC Electricity |
| 视频监控 | Frigate；Shinobi 作为独立备用方案保留 |
| 云与归档 | Nextcloud、CloudBak |
| 网络与入口 | Nginx Proxy Manager、ZeroTier、iperf3、SSHwifty、KMS |
| 运维管理 | Homepage、Glances、Dockhand、OpenClaw |
| 宿主机工具 | server-backup、routerconfig、ShellCrash、vpnupdate、UpdateServerHost、HDD_Temp |

完整说明见[服务清单](docs/SERVICES.md)。

## 目录速览

```text
.
├── docker-compose.yml       # 主要服务栈，当前统一入口
├── .env                     # 主栈私有变量，不应提交
├── docs/                    # 工程、服务、运维和安全文档
├── homeassistant/           # Home Assistant 配置
├── frigate/                 # Frigate 配置及本地运行状态
├── jellyfin/                # Jellyfin 配置、插件和缓存目录
├── nextcloud/               # Nextcloud 程序、配置及本地数据目录
├── moviepilot/ prowlarr/    # 媒体自动化运行数据（已忽略）
├── homepage/                # 服务导航与 Glances 配置
├── openclaw/                # OpenClaw 本地镜像与审查过的技能
├── server-backup/           # 系统备份及灾难恢复脚本
├── routerconfig/            # 宿主机网络、PPPoE、防火墙配置
└── <service>/               # 其他服务的持久化配置或独立 Compose
```

仓库中既有可版本化配置，也有数据库、缓存、证书、运行状态等本地数据。`.gitignore` 只能减少误提交，不能替代备份和密钥管理。

## 备份与恢复

系统和服务数据备份由 [`server-backup/backup.sh`](server-backup/backup.sh) 管理，详细说明见 [`server-backup/README.md`](server-backup/README.md)，主硬盘恢复步骤见 [`server-backup/RESTORE.md`](server-backup/RESTORE.md)。

```bash
sudo /mnt/SDD128G/server-backup/backup.sh --check
sudo /mnt/SDD128G/server-backup/backup.sh
```

文件级归档不能保证运行中 SQLite、MariaDB 等数据库的事务一致性；关键服务仍需应用级导出、暂停容器或文件系统快照。
