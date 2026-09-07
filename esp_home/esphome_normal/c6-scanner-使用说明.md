# nanoESP32-C6 手机热点与 BLE 检测

此目录包含可由 ESPHome 编译的配置和本地 Wi-Fi 扫描组件。目标为 ESPHome 2026.8.x；使用电脑现有 Docker ESPHome，不在宿主机安装。

设备独立运行，无须连接路由器、手机热点或 Home Assistant。热点扫描不需要热点密码。不要往此配置添加 `wifi:`、`api:`、`captive_portal:`、`espnow:`；本地组件独占 Wi-Fi 驱动，ESPHome 自带的连接管理会与其冲突。

## 手机设置

1. 手机热点使用 **2.4 GHz**，设置一个独特且可广播的热点名称。将 `c6.yaml` 中的 `phone_hotspot_ssid` 改成这个名称。SSID 相同的其他热点也会被认作目标，因此这是广播匹配，不是身份认证。此配置没有连接热点，手机若启用了“无设备连接时自动关闭热点”，需关闭该功能。
2. 手机蓝牙须发送 **iBeacon 广播**。只打开蓝牙或填写系统设置里显示的蓝牙 MAC，不能保证检测成功。
3. 在手机的 iBeacon 发射应用中设置与 YAML 相同的 UUID、Major、Minor，并开始广播。这里的 UUID 可以由你自行设置，不是系统蓝牙 MAC。
4. Android 若已有 Home Assistant Companion，可在“设置 → Companion App → 管理传感器 → BLE Transmitter”中启用发射，并复制其中的标识到 YAML。也可用支持 iBeacon 发射的应用。允许所需蓝牙权限，检查后台及锁屏后是否仍广播；发射间隔可从约 1 秒开始。
5. iPhone 的普通 iBeacon 发射应用需要在前台运行，不能将此方案当成可靠的锁屏后台手机在场检测。如果需要锁屏后检测，先以手机热点为主，或使用独立 BLE 信标。

iPhone 12 及以后的机型可在个人热点中打开“最大兼容性”使用 2.4 GHz。首次测试可保持个人热点设置页打开。

## 板子与串口

板子有两个 USB-C 接口，请用 **CH343 USB** 接口。板载 CH343P 接至 ESP32-C6 的 UART0，因此配置明确指定 `hardware_uart: UART0`，115200 波特率。默认 UART0 TX/RX 是 GPIO16/GPIO17，无须额外接线。电脑串口终端使用 115200、8N1、无流控。

配置按 4 MB Flash 的布局编译；若实际模组容量更大，此布局只使用前 4 MB。不要将 `variant: esp32c6` 改为其他 ESP32 型号。

## 安装、编译、烧录

保留以下目录结构；只复制 YAML 会找不到本地组件：

```text
esphome_normal/
  c6.yaml
  components/
    hotspot_presence/
      __init__.py
      binary_sensor.py
      hotspot_presence.h
```

使用现有 Docker 容器 `esphome`（已确认版本 2026.8.1）。其 `/config` 映射到宿主机 `/mnt/SDD128G/esp_home/esphome_normal`，已有 `c6.yaml`。已合入 `c6.yaml`，原联网配置备份已删除。固件安装后将作为独立 USB 串口扫描仪运行，原 API、OTA、联网功能不再启用。

可通过 ESPHome Device Builder 的“验证”和“安装”操作完成配置检查及编译烧录。容器内验证命令为：

```bash
docker exec esphome esphome config /config/c6.yaml
```

首次 USB 烧录可使用 Device Builder 下载固件并经浏览器串口安装；本方案没有配置 OTA。

## 输出与时间参数

每 5 秒输出一次，例如：

```text
[I][presence:...]: WIFI=1 BLE=1
[I][presence:...]: WIFI=0 BLE=1
[I][presence:...]: WIFI=unknown BLE=0
```

- `1`：最近检测到匹配广播。
- `0`：未检测到，或检测到后超过消失门限；不代表手机必定不在附近。
- `WIFI=unknown`：首次扫描尚未成功、最近成功结果超过 45 秒，或扫描组件已故障。
- BLE 原生组件初始状态为 `0`；它并不提供完整的扫描器健康诊断。不要把 `BLE=0` 解释为已证实手机离开。

Wi-Fi 每 15 秒异步扫描一次，检测到即置为 1；之前检测到的热点需连续三次成功扫描都没找到，才置为 0，通常约 30–45 秒加扫描时间。启动后第一次成功扫描没找到热点，则直接建立初始 0 状态。扫描失败不计入三次缺失。

BLE 接收匹配 iBeacon 后置为 1，距最后一次匹配广播 45 秒后置为 0。Wi-Fi 与 BLE 共用射频，已开启软件共存并使用较低 BLE 扫描占空比；实际延迟和漏扫率仍需在你的手机与现场测试。

串口输出包含 ESPHome 日志前缀和启动信息。电脑程序可只解析包含 `WIFI=` 与 `BLE=` 的状态行，不应将整个串口流当成纯 JSON。

## 验收步骤

1. 开热点与 iBeacon，确认两项均变为 1。
2. 只关热点，等待约一分钟，确认 WIFI 变为 0、BLE 保持 1。
3. 恢复热点、停止 iBeacon，等待约一分钟，确认 WIFI 恢复为 1、BLE 变为 0。
4. 锁屏并等待几分钟，检查手机是否自动停止热点或 BLE 广播。
5. 重启板子，确认扫描恢复；若有 `Scan timed out` 日志，先重新上电并排查射频或驱动问题。

## 依据

- [板卡资料与原理图](https://github.com/wuxx/nanoESP32-C6)
- [ESPHome UART 日志](https://esphome.io/components/logger/)
- [ESPHome BLE 存在检测](https://esphome.io/components/binary_sensor/ble_presence/)
- [ESP-IDF Wi-Fi 扫描 API](https://docs.espressif.com/projects/esp-idf/en/stable/esp32c6/api-reference/network/esp_wifi.html)
- [Android Companion BLE Transmitter](https://companion.home-assistant.io/docs/core/sensors/#ble-transmitter-sensor)
- [Apple：iOS 设备作为 iBeacon](https://developer.apple.com/documentation/corelocation/turning-an-ios-device-into-an-ibeacon-device)
- [Apple：热点最大兼容性](https://support.apple.com/en-ph/guide/security/secfd166f620/web)

## 验证状态

已于 2026-09-06 在现有 Docker 容器 `esphome` 中，使用 ESPHome 2026.8.1 完成配置验证和完整编译。结果为 `Successfully compiled program`。尚未烧录或进行真实手机、开发板串口及射频测试。

首次 USB 烧录固件位于 `.esphome/build/c6/build/firmware.factory.bin`，其中使用的仍是配置顶部的示例目标标识。改好目标后应重新编译，再安装。

## Home Assistant 清理

2026-09-07 已从本机 Home Assistant 移除旧的 `esp32c6` ESPHome 集成、设备及灯实体 `light.esp32c6_esp32_light`，并重启确认页面可访问。设备注册数据位于 Git 忽略的 `.storage` 运行状态目录，此操作仅在本机生效，不随仓库同步；其他实例如有旧设备，需在其 Home Assistant 中单独删除。清理时生成的备份已删除。
