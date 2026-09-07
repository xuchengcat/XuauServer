#pragma once

#include <atomic>
#include <cstring>
#include <string>
#include <vector>
#include "esp_event.h"
#include "esp_netif.h"
#include "esp_wifi.h"
#include "esphome/core/component.h"
#include "esphome/core/hal.h"
#include "esphome/core/log.h"
#include "esphome/components/binary_sensor/binary_sensor.h"

namespace esphome::hotspot_presence {

// No wifi: component: this scanner owns the ESP-IDF Wi-Fi driver.
class HotspotPresence : public binary_sensor::BinarySensor, public PollingComponent {
 public:
  void set_ssid(const std::string &ssid) { ssid_ = ssid; }
  float get_setup_priority() const override { return setup_priority::AFTER_WIFI; }
  bool scan_ok() const {
    return !is_failed() && has_state() && millis() - last_success_ < 45000;
  }

  void setup() override {
    if (!check_(esp_netif_init(), "netif init")) return;
    auto err = esp_event_loop_create_default();
    if (err != ESP_OK && err != ESP_ERR_INVALID_STATE) {
      check_(err, "event loop");
      return;
    }
    wifi_init_config_t init = WIFI_INIT_CONFIG_DEFAULT();
    if (!check_(esp_wifi_init(&init), "wifi init")) return;
    if (!check_(esp_wifi_set_storage(WIFI_STORAGE_RAM), "storage")) return;
    if (!check_(esp_wifi_set_mode(WIFI_MODE_STA), "mode")) return;
    if (!check_(esp_event_handler_instance_register(
            WIFI_EVENT, WIFI_EVENT_SCAN_DONE, &HotspotPresence::on_scan_, this,
            &handler_), "scan handler")) return;
    if (!check_(esp_wifi_start(), "wifi start")) return;
    if (!check_(esp_wifi_set_ps(WIFI_PS_NONE), "power save")) return;
    ready_ = true;
    update();
  }

  void update() override {
    if (!ready_ || busy_ || is_failed()) return;
    wifi_scan_config_t config{};
    config.show_hidden = false;
    config.scan_type = WIFI_SCAN_TYPE_ACTIVE;
    config.scan_time.active.min = 0;
    config.scan_time.active.max = 120;
    result_.store(-1);
    busy_ = true;
    started_ = millis();
    auto err = esp_wifi_scan_start(&config, false);  // asynchronous
    if (err != ESP_OK) {
      busy_ = false;
      ESP_LOGW("hotspot", "Scan start failed: %s", esp_err_to_name(err));
    }
  }

  void loop() override {
    if (!ready_ || is_failed()) return;
    int result = result_.exchange(-1);
    if (result >= 0) {
      busy_ = false;
      if (result != 0) {
        esp_wifi_clear_ap_list();
        ESP_LOGW("hotspot", "Scan failed, status=%d", result);
        return;  // A failed scan must not count as absence.
      }
      uint16_t count = 0;
      auto err = esp_wifi_scan_get_ap_num(&count);
      if (err != ESP_OK) {
        esp_wifi_clear_ap_list();
        ESP_LOGW("hotspot", "Cannot read scan count: %s", esp_err_to_name(err));
        return;
      }
      std::vector<wifi_ap_record_t> records(count);
      if (count > 0) {
        err = esp_wifi_scan_get_ap_records(&count, records.data());
        if (err != ESP_OK) {
          esp_wifi_clear_ap_list();
          ESP_LOGW("hotspot", "Cannot read scan records: %s", esp_err_to_name(err));
          return;
        }
      } else {
        esp_wifi_clear_ap_list();
      }
      bool found = false;
      for (uint16_t i = 0; i < count; i++) {
        if (ssid_ == reinterpret_cast<const char *>(records[i].ssid)) {
          found = true;
          break;
        }
      }
      last_success_ = millis();
      if (found) {
        misses_ = 0;
        publish_state(true);
      } else {
        if (misses_ < 3) misses_++;
        // First successful scan establishes an initial state. Once seen,
        // require three successful misses to change present -> absent.
        if (!has_state() || misses_ >= 3) publish_state(false);
      }
    }
    if (busy_ && millis() - started_ > 20000) {
      esp_wifi_scan_stop();
      ESP_LOGE("hotspot", "Scan timed out; restart device to recover");
      mark_failed();
    }
  }

 protected:
  static void on_scan_(void *arg, esp_event_base_t, int32_t, void *data) {
    auto *self = static_cast<HotspotPresence *>(arg);
    auto *event = static_cast<wifi_event_sta_scan_done_t *>(data);
    self->result_.store(static_cast<int>(event->status));
  }
  bool check_(esp_err_t err, const char *operation) {
    if (err == ESP_OK) return true;
    ESP_LOGE("hotspot", "%s failed: %s", operation, esp_err_to_name(err));
    mark_failed();
    return false;
  }
  std::string ssid_;
  esp_event_handler_instance_t handler_{};
  std::atomic<int> result_{-1};
  uint32_t started_{0};
  uint32_t last_success_{0};
  uint8_t misses_{0};
  bool ready_{false};
  bool busy_{false};
};
}  // namespace esphome::hotspot_presence
