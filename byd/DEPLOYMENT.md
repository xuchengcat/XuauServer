# 国区比亚迪车况接入 Home Assistant

当前使用用户提供的 `byd_china.rar`（[Hassbian 讨论帖](https://bbs.hassbian.com/thread-32194-1-1.html)中的授权账号适配版）。原包存放在 `byd/byd_china.rar`；只读改版位于 `byd/ha-readonly/byd_china/`，已安装至 `homeassistant/config/custom_components/byd_china/`。替换前的组件和 HA 配置条目备份在 `byd/ha-backup-20260930T054420Z/`，该目录被 Git 忽略，因为备份的配置条目可能含有其他服务凭据。

授权账号已验证能返回一辆共享车辆的实时车况和定位。改版加载传感器、二值传感器、定位跟踪器以及“立即刷新状态与定位”按钮；不加载门锁、空调等远控或轮询调节实体，也不调用历史数据接口。无须控制密码。HA 中已有授权账号配置条目，凭据来自私有的 `byd/.env`，车况和定位刷新周期均为 3600 秒。调试数据转储关闭。

集成在 HA 进程内复用登录后的客户端；HA 重启、会话失效或重新配置时可能再次登录。比亚迪服务端是否会让手机 App 下线，应以实际使用观察为准。旧的 `byd_status` Docker 容器每轮都会重新登录，需保持停止，不要执行 `docker compose up -d byd`。

已在 HA 生成电量、四轮胎压、GPS 经纬度、定位跟踪器和手动刷新按钮。`battery_level`、`*_tire_pressure`、`gps_*`、`location` 可在 HA 实体列表中搜索。停车后的数据是否新鲜需与比亚迪 App 对照；HA 的查询时间并不保证车辆刚上传了数据。

充电状态仍通过只读传感器显示。用户要求“立即开始／停止充电”，但此国区版本没有实现相应控制，授权账号在 App 中也尚未验证可执行这两项操作。海外 pyBYD 的实测显示，停止充电请求可能返回成功而车辆继续充电，因此暂未暴露这类会误报成功的按钮。若以后通过 App 或充电桩确认可用命令，应单独验证后再加入。

更新代码前先备份现有组件和 `.storage/core.config_entries`。HACS 对原组件的更新可能覆盖此改版。HA 配置条目保存在 `.storage`，不要将它提交 Git。

2026-10-07 新增“充电枪连接状态”文本传感器：暂按 `chargeState=1/15` 映射“已连接”，`0` 映射“未连接”，缺失、`-1` 或其他值显示未知。不用 `chargingState` 回退判断。实体属性保留 `chargeState`、`chargingState` 和车辆上报时间 `vehicle_timestamp`，供用户对照插枪、拔枪、等待预约和实际充电状态。此映射尚待用户实测确认，值 15 可能在拔枪后保持不变。它复用现有车况轮询与手动刷新，不增加接口请求。

2026-10-07 新增 HA 侧边栏“车辆”仪表盘，路径 `/dashboard-vehicle/overview`。使用原生 Sections 布局和卡片，分为车辆概览、车辆定位、充电状态、四轮胎压、车门与车窗、车辆系统。页面展示车辆车况/GPS 上报时间，超过两小时提示“数据较旧”；手动刷新调用现有刷新按钮。充电枪连接仍为暂定映射。配置通过 HA WebSocket API 保存，导出副本在 本机 `byd/vehicle-dashboard.json`（私有，不入 Git）；公开模板为 `homeassistant/vehicle-dashboard.example.json`。


## 2026-10-09 同步运行代码与最终映射

已将运行中组件的 sensor.py、realtime.py 与中英文翻译同步至本源码目录。
本车最终确认：chargeState=1 正在充电、2 充电完成、9 已插枪未充电，均为已连接；15 未插枪/未连接；0 未充电但连接状态未知。
该映射依据本车用户确认，不声明适用于所有车型。预约提示单独展示，不用于判断插枪。

现有“车辆”仪表盘另有智己 LS6 标签页和立即重新查询按钮，安装来源为 https://github.com/xuchengcat/im-motors-ha 。
公开仪表盘模板不含真实车牌实体前缀，使用 `byd_vehicle` 占位，部署时替换为本机实体前缀。
