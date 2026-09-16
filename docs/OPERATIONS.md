# 部署与运维

## 1. 部署前检查

```bash
cd /mnt/SDD128G

# 确认关键磁盘确实已挂载
findmnt /mnt/HDD14T
findmnt /mnt/HDD6T
findmnt /mnt/camera1t

# 确认硬件设备
ls -l /dev/dri/renderD128 /dev/apex_0 /dev/net/tun

# 仅检查 Compose 语法和变量插值
docker compose config -q
docker compose config --services
```

缺少 Coral 时不能直接启动当前 Frigate 配置；缺少 Intel render 节点时 Jellyfin、PhotoPrism 和 Frigate 的硬件加速配置需要调整。并非所有机器都需要 `/mnt/HDD6T` 或 `/mnt/camera1t`，但引用它们的服务启动前必须修改对应挂载。

## 2. 环境文件

根 `.env` 当前供代理地址、Nextcloud、模型 API 和 MoviePilot 等变量使用。其他私有文件包括：

- `webdav/.env`：Dufs 监听和认证配置；模板为 `.env.example`。
- `moontvplus/init.env`：MoonTVPlus 初始化配置；模板为 `init.env.example`。
- `sgcc_elec/.env`：国家电网账户配置。
- `vpnupdate/.env`：订阅 URL 和更新参数；模板为 `.env.example`。

创建后应设置为仅所有者可读：

```bash
chmod 600 .env webdav/.env moontvplus/init.env sgcc_elec/.env vpnupdate/.env
```

不要通过 `docker compose config` 的完整输出分享排障信息，因为变量插值后可能包含真实密钥。

## 3. 启停与查看状态

```bash
# 启动单个服务及其 Compose 依赖
docker compose up -d frigate

# 更新指定服务，而不是无差别更新全部服务
docker compose pull jellyfin
docker compose up -d jellyfin

# 查看状态、日志和资源占用
docker compose ps
docker compose logs --tail=200 -f jellyfin
docker stats

# 停止但保留容器和数据
docker compose stop jellyfin

# 重建指定容器；不会删除 bind mount 中的数据
docker compose up -d --force-recreate jellyfin
```

不建议随意运行 `docker compose down -v`。当前主要使用 bind mount，但该命令仍可能删除 Compose 管理的命名卷和网络，未来增加卷后风险会更大。

## 4. 推荐启动顺序

1. 先确认磁盘、网络、代理、Docker 和设备节点。
2. 启动基础消息与入口：`mosquitto`、`nginx-proxy-manager`。
3. 启动智能家居：`homeassistant`、`sgcc_electricity`、`node-red`、`esphome`。
4. 启动下载链路：`transmission`、`prowlarr`、`moviepilot`。
5. 启动内容服务：`jellyfin`、`metatube`、`kavita`、`photoprism` 等。
6. 确认 Coral、摄像头和录像盘后启动 `frigate`。
7. 最后启动管理面：`homepage`、`glances`、`dockhand`、`openclaw`。

Compose 的 `depends_on` 只用于少数显式依赖，也不等价于业务就绪检查。服务重启后仍应查看日志和健康状态。

## 5. 更新策略

- `latest`、`stable` 等浮动标签更新前先备份服务配置和数据库。
- 一次只更新一个业务链路，记录更新前后的镜像 ID：`docker image inspect <image>`。
- 对 Nextcloud、Home Assistant、Frigate、PhotoPrism 等有数据迁移的应用，先阅读目标版本升级说明。
- 数据库迁移开始后，不要简单回退旧镜像读取新数据库；必须使用升级前备份恢复。
- 根 Compose 和独立 Compose 的镜像版本可能不同，更新时先确认实际运行容器来自哪一份定义。

## 6. 配置验证

常用的低风险检查：

```bash
# Compose 解析
docker compose config -q

# Home Assistant 配置（容器已运行时）
docker exec homeassistant python -m homeassistant --script check_config --config /config

# Mosquitto 是否监听及容器日志
docker compose logs --tail=100 mosquitto

# 外部挂载是否仍然存在
findmnt -T /mnt/HDD14T/Media_Data_HDD
findmnt -T /mnt/camera1t/frigate
```

测试反向代理时应同时检查内网 upstream 和 HTTPS 域名，避免把应用故障误判成代理故障。

## 7. 备份

仓库 Git 历史只能恢复已跟踪的文本配置，不能替代运行数据备份。完整备份工具：

```bash
sudo /mnt/SDD128G/server-backup/backup.sh --check
sudo /mnt/SDD128G/server-backup/backup.sh
```

特别需要一致性保护的数据包括：

- Nextcloud 数据目录与数据库；两者必须来自同一时间点。
- Frigate、Home Assistant、PhotoPrism、Nginx Proxy Manager、Portainer 等 SQLite 数据库。
- Node-RED 的 `flows.json` 与 `flows_cred.json`。
- Mosquitto 密码文件和持久化数据。
- ZeroTier identity、NPM 证书私钥和服务环境文件。

文件级 tar 备份运行中的数据库可能得到逻辑不一致的副本。重要变更前应使用应用原生导出、暂时停止对应服务，或使用支持一致性快照的文件系统。

## 8. 故障排查顺序

1. `findmnt`：确认外部磁盘没有掉盘。
2. `docker compose config -q`：确认 Compose 与环境变量可解析。
3. `docker compose ps`：查看退出码、健康状态和端口。
4. `docker compose logs --tail=200 <service>`：查看首次错误而不是只看后续重试。
5. `df -h`、`df -i`、`free -h`：检查空间、inode 和内存。
6. `ls -l`：检查 bind mount、UID/GID 和设备权限。
7. 从容器内部测试依赖的服务名、端口和 DNS。

如果某个服务持续重启，先停止它并保存日志；不要反复删除数据库或配置目录尝试“重置”。
