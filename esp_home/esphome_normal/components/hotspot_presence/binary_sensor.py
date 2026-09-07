import esphome.codegen as cg
import esphome.config_validation as cv
from esphome.components import binary_sensor
from esphome.const import CONF_ID, CONF_SSID

DEPENDENCIES = ["esp32"]
CONFLICTS_WITH = ["wifi", "espnow"]
ns = cg.esphome_ns.namespace("hotspot_presence")
HotspotPresence = ns.class_("HotspotPresence", binary_sensor.BinarySensor, cg.PollingComponent)

CONFIG_SCHEMA = cv.All(
    binary_sensor.binary_sensor_schema(HotspotPresence)
    .extend({cv.Required(CONF_SSID): cv.ssid})
    .extend(cv.polling_component_schema("15s")),
    cv.only_on_esp32,
)

async def to_code(config):
    var = await binary_sensor.new_binary_sensor(config)
    await cg.register_component(var, config)
    cg.add(var.set_ssid(config[CONF_SSID]))
