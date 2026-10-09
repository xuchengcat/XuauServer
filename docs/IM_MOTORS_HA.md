# 智己汽车 Home Assistant 接入

正式工程：https://github.com/xuchengcat/im-motors-ha ，HACS 自定义仓库类型选择 Integration。
本机 HA 为 Docker 部署，配置目录 `/mnt/SDD128G/homeassistant/config`，容器内 `/config`。

已安装智己只读集成，短信登录后每60分钟查询车辆车况。v0.4.2 增加“立即重新查询车况”按钮，跳过本地车况缓存，更新传感器与后续自动查询计时。云端返回仍可能是休眠前快照。
v0.4.3 增加“车辆位置” GPS device_tracker 与智己页面地图。位置来自相同的车况快照，随自动查询或手动按钮更新。当前观测格式 1 依据 App 3.2.4 高德 autonavi 调用链按 GCJ-02 解释，在本地转换成 WGS-84；这是调用链推断，其他格式暂不支持。缺失或异常坐标显示 unavailable，诊断不输出经纬度。
车况更新时间尚未确认为定位独立采样时间，休眠车辆可能显示旧位置。

按钮保留账号认证、VIN 核对与持久故障停止；不会删除故障标记自动重试。

车辆仪表盘包含 BYD 原视图和“智己 LS6”标签页，智己页面路径为 `/dashboard-vehicle/im-motors`。
公开模板为 `homeassistant/vehicle-dashboard.example.json`，通过 HA WebSocket `lovelace/config/save` 保存。BYD 实体使用 `byd_vehicle` 占位，导入时替换为本机前缀；智己实体也需与实际注册 ID 核对。

- 代码由 HACS 管理于 `/config/custom_components/im_motors/`。
- 私有账号文件由集成保存在 `/config/.storage/im_motors/`，备份须包含匹配密钥及完整加密目录。
- 本地开发工程：`/mnt/SDD128G/codex/im-motors-ha/`。
- 本地研究笔记入口：`/mnt/SDD128G/codex/im-motors-development/README.md`。
- 研究材料从本人 Nextcloud Documents 归档恢复，8,459项文件通过原清单 SHA-256 校验。
- 原始截图、车辆日志、账号存储和维护备份保留本地，不纳入公开服务器仓库。

智己代码和服务器配置分属独立 Git 仓库，后续分别提交；不要把忽略的 `codex/` 开发材料整包添加到本仓库。
