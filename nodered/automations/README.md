# 车辆晚间充电提醒

运行流程“车辆 · 晚间充电提醒”已部署启用。北京时间每天22:00读取 HA 缓存，仅在家、电量严格小于40%、充电枪为“未连接”时通知。未知或无效状态跳过；“只检查（不推送）”入口不发送通知。

本车 chargeState 最终映射为：1 正在充电、2 充电完成、9 等待预约，均已连接；15 未插枪；0或未知不能确认连接状态。流程读取 HA 已映射文字，不额外调用车辆云端。

BYD 提醒使用 `han-bark-server.onrender.com`，服务器温度等其他通知使用 `xuau-bark-server.onrender.com`。私有设备密钥通过 BARK_TOKEN 配置；BYD 的 BARK_SERVER/BARK_TOKEN 为流程环境变量，服务器通知也从环境读取 BARK_TOKEN。

- `byd-night-charge-reminder.json`：本流程公开模板。
- `../flows.example.json`：当前全量流程的脱敏模板。
- 模板使用 `byd_vehicle` 实体前缀占位，导入时替换为本机真实实体 ID。
- 模板中的 `REPLACE_WITH_PRIVATE_BARK_TOKEN` 必须替换为私有密钥。
- 运行文件 `data/flows.json`、加密凭据及 `.config.runtime.json`、编辑器用户状态、`automation-backup-*` 保持本地，不再提交 Git。

导出模板不会覆盖运行中的实际配置。故障检查结果保存在 `last_check`、`last_delivery`、`last_error`，不输出推送密钥。
