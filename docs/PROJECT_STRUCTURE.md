# 工程结构

## 1. 编排边界

项目存在三类运行单元：

1. **主服务栈**：根目录 `docker-compose.yml`，是当前推荐的统一入口，共定义 28 个服务。
2. **独立或历史 Compose**：`bark/`、`iperf/`、`kms/`、`lyricapi/`、`nginx_proxy_manager/`、`nodered/`、`photoprism/`、`portainer/`、`transmission/`、`zerotier/` 和 `shinobi/` 下的 Compose 文件。部分服务已同时合并进主栈，不应重复启动。
3. **宿主机工具**：`server-backup/`、`routerconfig/`、`shellclash/`、`vpnupdate/`、`UpdateServerHost/`、`HDD_Temp/` 和 `codex/`，依赖 systemd、cron、Python 或宿主机命令，不由根 Compose 管理。

根 Compose 未显式指定网络的服务会加入项目默认 bridge 网络，因此能使用 Compose 服务名互相访问，例如 Frigate 连接 `mosquitto:1883`。使用 `network_mode: host` 的服务直接共享宿主机网络命名空间，不参与该服务名解析方式。

文件底部声明了 `my_docker` 网络，但当前没有服务显式加入它；实际主要使用 Compose 自动创建的默认网络。

## 2. 目录职责

### 主栈服务目录

| 目录 | 内容 | 数据性质 |
| --- | --- | --- |
| `jellyfin/` | Jellyfin 配置、插件、缓存和 MetaTube socket | 配置 + 可再生成缓存 |
| `webdav/` | Dufs 环境变量模板/私有配置 | 配置，含认证信息 |
| `kavita/` | Kavita 数据库和设置 | 运行数据，已忽略 |
| `moontvplus/` | 初始化环境文件及应用数据 | 私有配置 + 运行数据 |
| `xiaomusic/` | XiaoMusic 设置、认证和插件配置 | 配置，部分敏感 |
| `lyricapi/` | 独立 Compose；主栈也定义服务 | 部署配置 |
| `nextcloud/` | Nextcloud 程序树、配置、扩展和本地数据目录 | 程序 + 配置 + 运行数据 |
| `openclaw/` | 本地 Dockerfile、运行配置、工作区和媒体技能 | 镜像配方 + 私有运行数据 |
| `photoprism/` | PhotoPrism 存储及旧独立 Compose | 数据库/缓存 + 部署配置 |
| `transmission/` | 下载器配置、watch 目录和 Web UI | 配置 + 运行状态 |
| `moviepilot/` | MoviePilot 配置、数据库和浏览器核心 | 运行数据，已忽略 |
| `prowlarr/` | Prowlarr 配置、数据库和日志 | 运行数据，已忽略 |
| `homeassistant/` | HA YAML、自动化、脚本、仪表盘和运行状态 | 配置 + 运行数据 |
| `sgcc_elec/` | 国家电网采集环境变量、缓存和 SQLite 数据库 | 私有配置 + 数据库 |
| `mqtt/` | Mosquitto 配置、密码文件和持久化消息 | 配置 + 私有数据 |
| `nodered/` | 流程、设置、Node 依赖和凭据 | 配置 + 私有运行数据 |
| `esp_home/` | ESPHome YAML、自定义组件、构建缓存 | 源配置 + 构建产物 |
| `frigate/` | NVR 配置、SQLite、模型缓存和运行状态 | 配置 + 数据库 + 缓存 |
| `homepage/` | 导航页、图标、Docker 连接和 Glances 配置 | 配置 |
| `nginx_proxy_manager/` | 代理数据库、Nginx 片段、证书和日志轮转 | 配置 + 私钥/证书 + 数据库 |
| `dockhand/` | Docker 管理工具数据库 | 运行数据，已忽略 |
| `zerotier/` | 节点身份、网络成员配置和运行状态 | 网络身份，敏感 |

`cloudbak`、`iperf3`、`kms-server`、`sshwifty` 和 `glances` 等服务没有专属或仅有很少的持久化目录；其定义主要位于根 Compose 中。

### 独立、备用和宿主机目录

| 目录/文件 | 作用 | 状态 |
| --- | --- | --- |
| `bark/` | 自建 Bark iOS 推送服务 | 独立 Compose；根 Compose 中已注释，当前注释称改用托管实例 |
| `shinobi/` | Shinobi NVR 源码、镜像和 MySQL 5.7 编排 | 独立备用方案；根 Compose 中已注释 |
| `portainer/` | Portainer Docker 管理界面 | 独立 Compose；主栈当前使用 Dockhand |
| `homebridge/` | HomeKit 桥接配置及启动脚本 | 不在根 Compose，需单独运行或另行编排 |
| `server-backup/` | 主系统、服务目录和外部数据的归档/恢复 | 宿主机 root 脚本 |
| `routerconfig/` | Netplan、PPPoE、DHCPv6、转发及防火墙配置 | 宿主机网络配置 |
| `shellclash/` | ShellCrash/Mihomo 配置和定时策略组测速 | 宿主机网络工具 |
| `vpnupdate/` | 下载订阅并原子更新 ShellCrash 配置 | Python + shell，通常由 root cron 运行 |
| `UpdateServerHost/` | 检测域名连通性并查询 ZeroTier 成员地址 | systemd 长驻脚本 |
| `HDD_Temp/` | 读取 SMART 温度并写入 Home Assistant | Python 定时任务 |
| `tpu/` | Coral PCIe/M.2 TPU 的 Gasket DKMS 驱动包和源码 | 宿主机驱动材料 |
| `codex/` | 本机 Codex 启动/更新脚本及调研文档 | 本地开发工具，已忽略 |
| `maintenance-backups/` | 运维操作前生成的本地快照 | 临时备份，已忽略 |
| `DATABASE_CONSOLIDATION_PLAN.md` | 数据库整合草案 | 本地未跟踪文档，不属于当前正式文档 |

## 3. 存储布局

当前配置依赖下列固定路径：

| 路径 | 主要用途 |
| --- | --- |
| `/mnt/SDD128G` | 本仓库、服务配置、数据库、缓存和部分应用数据 |
| `/mnt/HDD14T/Media_Data_HDD` | 电影、剧集、音乐、漫画、下载等媒体数据 |
| `/mnt/HDD14T/Pictures` | PhotoPrism 原图和导入目录 |
| `/mnt/HDD14T/nextcloud_data` | Nextcloud 用户数据 |
| `/mnt/HDD14T/mariadb_data` | 当前 Compose 为 Nextcloud 挂载的数据库路径，需特别核对，见安全文档 |
| `/mnt/HDD14T/wechat` | CloudBak 微信归档 |
| `/mnt/HDD6T/downloads_long` | Transmission 长期下载目录 |
| `/mnt/HDD6T/commonbkp` | 系统完整备份集 |
| `/mnt/camera1t/frigate` | Frigate 录像 |
| `/mnt/camera1t/videos`、`database` | Shinobi 录像和数据库（仅独立方案） |

启动容器前应使用 `findmnt` 检查外部磁盘。挂载失败时，同名目录可能仍存在于根分区；继续运行会把大量媒体、录像或数据库写到系统盘。

## 4. 主要依赖关系

```text
摄像头 ──RTSP──> Frigate ──MQTT──> Mosquitto <──> Home Assistant
                         └──录像──> /mnt/camera1t

Prowlarr ──索引器──> MoviePilot ──任务──> Transmission
                         └──整理──> /mnt/HDD14T/Media_Data_HDD ──> Jellyfin
                                                        ├──> WebDAV
                                                        └──> LyricAPI/XiaoMusic

外部访问 ──> Nginx Proxy Manager ──> 各 Web 服务
导航与监控 ──> Homepage ──> Docker API / Glances / 服务 API

OpenClaw ──> Nextcloud WebDAV / MoviePilot API / 外部模型 API
SGCC Electricity ──SQLite──> Home Assistant SQL 传感器
```

## 5. 版本控制边界

- `.gitignore` 排除了大量数据库、缓存、证书、运行日志和私有环境文件，但仓库中仍有历史上已跟踪的敏感配置。
- 不要用 `git clean`、重建目录或空目录覆盖的方式处理运行数据。
- 修改服务前先确认文件是“声明式配置”还是“应用正在写入的数据”。SQLite、WAL、Node-RED 凭据、Nginx Proxy Manager 数据库等不适合在服务运行时直接编辑。
- `latest` 标签会使重建结果随时间变化；重要服务更新前应记录镜像 digest 或改用明确版本。
