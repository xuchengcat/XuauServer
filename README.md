# XuauServer

个人 Homelab 服务器配置备份仓库，基于 Docker Compose 管理的家庭自动化与媒体服务集合。

## 服务列表

| 服务 | 说明 |
|------|------|
| **homeassistant** | Home Assistant 家庭自动化平台 |
| **homebridge** | HomeKit 桥接，接入不支持苹果的设备 |
| **nodered** | 可视化自动化流程编排 |
| **nextcloud** | 私有云存储与协作平台 |
| **nginx_proxy_manager** | 反向代理与 SSL 证书管理 |
| **portainer** | Docker 容器可视化管理 |
| **jellyfin** | 开源媒体服务器 |
| **frigate** | 基于 NVR 的 AI 摄像头监控 |
| **photoprism** | AI 驱动的照片管理 |
| **shinobi** | 视频监控系统 |
| **bark** | iOS 自定义推送通知服务 |
| **esp_home** | ESP 设备固件管理平台 |
| **transmission** | BT 下载客户端 |
| **zerotier** | 虚拟局域网组网 |
| **mqtt** | MQTT 消息代理（Mosquitto） |
| **homepage** | 服务导航首页 |
| **sgcc_elec** | 国家电网电量监控 |
| **xiaomusic** | 小爱音箱自定义音乐 |
| **vpnupdate** | VPN 配置自动更新 |
| **routerconfig** | 路由器配置备份 |
| **tpu** | TPU 加速相关配置 |
| **kms** | KMS 激活服务 |
| **lyricapi** | 歌词 API 服务 |
| **iptv-allinone** | IPTV 聚合服务 |

## 仓库说明

本仓库仅包含各服务的配置文件，不含：

- 运行时数据、数据库、缓存
- 媒体文件、照片、监控录像
- 依赖包（`node_modules` 等）
- 证书、私钥等敏感凭据

## 使用方式

```bash
git clone https://github.com/xuchengcat/XuauServer.git
cd XuauServer/<service>
docker compose up -d
```

## 环境

- 主机：Ubuntu 24.04 LTS x86-64
- 容器：Docker + Docker Compose
