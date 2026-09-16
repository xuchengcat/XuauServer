# 服务清单

## 1. 根 Compose：影音与内容

| Compose 服务 | 用途 | 对外入口/网络 | 关键依赖与注意事项 |
| --- | --- | --- | --- |
| `jellyfin` | 电影、剧集、音乐等媒体库与串流 | `8096/tcp` | 读取 HDD14T 多个媒体目录；通过 `/dev/dri/renderD128` 使用 Intel QSV；容器名为 `jellyfin_qsv` |
| `webdav` | 通过 Dufs 提供媒体目录浏览、上传和 WebDAV | 端口由 `webdav/.env` 决定 | 以 `1000:1000` 运行，整个媒体目录可写；认证配置必须私有化 |
| `kavita` | 漫画/电子书阅读服务 | 默认仅由反向代理访问 | 漫画目录只读；数据库位于 `kavita/config`；使用主机代理变量 |
| `moontv` | 聚合影视 Web 应用 | 默认仅由反向代理访问 | 初始化变量在 `moontvplus/init.env`，应用数据位于 `moontvplus/data` |
| `xiaomusic` | 小爱音箱自定义音乐播放 | `18090/tcp` | 音乐目录可读；当前关闭 HTTP 认证，必须限制网络暴露 |
| `lyricapi` | 扫描本地音乐并提供歌词 API | 主栈不直接映射端口 | 音乐目录只读；独立 Compose 会暴露 `28883`，不要与主栈重复启动 |
| `metatube` | 为 Jellyfin 提供媒体元数据 | `8082 -> 8080` | 使用代理访问外部元数据；与 Jellyfin 共享本地 socket 目录 |
| `photoprism` | 照片索引、搜索、人脸识别和 WebDAV | 默认仅由反向代理访问 | 原图目录可写，数据库/缓存位于 SSD；使用 Intel QSV；SQLite 模式 |

## 2. 根 Compose：下载与媒体自动化

| Compose 服务 | 用途 | 对外入口/网络 | 关键依赖与注意事项 |
| --- | --- | --- | --- |
| `transmission` | BT 下载 | `network_mode: host`，通常为 `9091` | 使用固定 4.0.5 镜像；下载目录横跨 HDD14T/HDD6T；认证不应硬编码 |
| `prowlarr` | 管理并聚合 BT/PT 索引器 | `9696/tcp` | 为 MoviePilot 提供索引器；配置目录含 API key 和数据库 |
| `moviepilot` | 影视搜索、订阅、下载编排和媒体整理 | `3000`、`3001` | 连接 Prowlarr、Transmission 和媒体目录；停止宽限 120 秒；API token 来自根 `.env` |

典型链路是 Prowlarr 提供索引器，MoviePilot 选择资源并向 Transmission 派发任务，完成后整理至媒体库，最后由 Jellyfin 扫描展示。三者必须对同一宿主机文件使用一致或可映射的路径。

## 3. 根 Compose：智能家居与监控

| Compose 服务 | 用途 | 对外入口/网络 | 关键依赖与注意事项 |
| --- | --- | --- | --- |
| `homeassistant` | 家庭自动化中枢 | `network_mode: host`，通常为 `8123` | `privileged: true` 且挂载 DBus；读取 SGCC SQLite；配置中有 SSH 自动化 |
| `sgcc_electricity` | 抓取国家电网账户电量并写入 SQLite | `network_mode: host` | 账号/验证码配置在私有 `.env`；数据目录被 HA 挂载读取 |
| `mosquitto` | MQTT 消息代理 | `1883/tcp`、`9001/tcp` | 禁止匿名访问；密码文件不应入库；Frigate 等服务依赖它 |
| `node-red` | 可视化自动化流程编排 | `1880/tcp` | 流程凭据文件已忽略；修改前备份 `flows.json` 和凭据文件 |
| `esphome` | ESP 固件配置、编译和 OTA 管理 | `network_mode: host`，通常为 `6052` | 构建缓存很大；host 网络用于发现设备；仓库含自定义组件 |
| `frigate` | 摄像头录像、检测、音频事件与检索 | `5000`、`8554`、`8555/tcp` | 依赖 Mosquitto、Coral `/dev/apex_0`、Intel QSV 和 camera1t；`5000` 是未认证内部接口，不应公网暴露 |

`shinobi/` 是另一套独立 NVR 方案，使用自建镜像和 MySQL 5.7，根 Compose 中的定义已注释。除非明确迁移，不要让 Shinobi 与 Frigate 同时占用同一摄像头、录像盘或硬件加速资源。

## 4. 根 Compose：云、网络与管理

| Compose 服务 | 用途 | 对外入口/网络 | 关键依赖与注意事项 |
| --- | --- | --- | --- |
| `nextcloud` | 私有文件云和 WebDAV | 默认仅由 NPM 代理 | 程序目录在 SSD，用户数据在 HDD14T；当前数据库挂载方式需要核对 |
| `cloudbak` | 微信数据归档 | `9527/tcp` | 数据写入 `/mnt/HDD14T/wechat` |
| `nginx-proxy-manager` | HTTP/HTTPS 反向代理与证书管理 | `81 -> 80`、`444 -> 443` | 管理端口 81 未映射；证书、私钥和 SQLite 数据库必须备份且保密 |
| `zerotier` | 虚拟局域网 | `network_mode: host` | 需要 TUN、`NET_ADMIN`、`SYS_ADMIN`；身份 secret 不能提交或复制到多台在线节点 |
| `iperf3` | LAN TCP/UDP 带宽测试 | `5201/tcp+udp` | 无认证，只应在可信网络开放 |
| `kms-server` | 局域网 KMS 服务 | `1688/tcp` | 仅在符合许可和组织政策的环境使用 |
| `sshwifty` | 浏览器 SSH/Telnet 客户端 | 默认仅由反向代理访问 | 一旦暴露即可触达内网主机，应强认证并限制来源 |
| `homepage` | 服务导航和状态聚合 | 默认仅由反向代理访问 | 只读挂载 Docker socket，但配置中包含服务 API 凭据 |
| `glances` | 主机、磁盘、容器指标和 Web API | `network_mode: host` | `privileged: true`，可读取 Docker socket 和多个磁盘挂载 |
| `dockhand` | Docker Compose/容器可视化管理 | 默认仅由反向代理访问 | Docker socket 可等价取得主机 root；还挂载整个 `/mnt/SDD128G` |
| `openclaw` | 本地 AI 助手网关及媒体自动化技能 | `18789/tcp` | 本地构建镜像；挂载宿主机 Codex 目录；使用模型、Nextcloud 和 MoviePilot 凭据 |

## 5. 独立服务与工具

| 名称 | 用途 | 如何运行/状态 |
| --- | --- | --- |
| Bark | iOS 推送服务 | `bark/docker-compose.yaml`；当前主栈注释说明已改用外部托管实例 |
| Portainer | Docker 管理 UI | `portainer/docker-compose.yml`；与 Dockhand 功能重叠，Docker socket 权限很高 |
| Homebridge | 把非原生设备接入 Apple HomeKit | 目录含 `startup.sh`、插件清单和配置，但无当前 Compose 定义 |
| Shinobi | 备用视频监控 | 先启动 SQL Compose，再启动主 Compose；配置含旧式默认口令，启用前必须更换 |
| ShellCrash | Mihomo/Clash 代理和规则分流 | 使用 `shellclash/install.sh` 将配置部署至 `/etc/ShellCrash` |
| VPN Update | 更新 ShellCrash 订阅节点 | `vpnupdate/refresh_config.sh --dry-run` 验证，正式运行通常需要 root |
| Router config | PPPoE、Netplan、IPv6、DHCP 与防火墙 | 直接影响宿主机网络，只应在控制台可恢复时应用 |
| UpdateServerHost | 连通性检测及 ZeroTier 地址查询 | `UpdateServerHost/dns-update.service`；脚本当前只记录查询结果，SmartDNS 写入行已注释 |
| HDD Temp | 将 SMART 硬盘温度写入 HA helper | 需要 `smartctl`、Python `requests` 和访问 HA API 的令牌 |
| Server Backup | 系统与服务文件级归档 | root 执行 `backup.sh`，目标为 HDD6T；恢复见同目录 `RESTORE.md` |
| TPU | Coral Gasket DKMS 驱动 | 宿主机安装材料，为 Frigate 的 `/dev/apex_0` 提供支持 |
| FormatMusic | 音乐文件格式/目录整理 | 手工脚本；先在副本或小目录验证，避免批量误改媒体库 |
| Codex helpers | 为本机 Codex 注入代理并启动或更新 | 本地开发辅助，含私有网络配置，不属于服务器运行时 |

## 6. 重复编排提示

以下服务既存在于根 Compose，也有目录内独立 Compose：`iperf3`、`kms-server`、`lyricapi`、`nginx-proxy-manager`、`node-red`、`photoprism`、`transmission`、`zerotier`。两套定义在端口、镜像版本或配置上可能不同。

当前约定是以根 Compose 为准。只有在停止并移除主栈中的同名容器后，才应使用独立 Compose；否则会遇到容器名、端口或数据目录冲突。
