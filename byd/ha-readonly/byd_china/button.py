"""Manual read-only refresh for BYD vehicle data."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import BydDataUpdateCoordinator, BydGpsUpdateCoordinator
from .entity import BydVehicleEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    data = hass.data[DOMAIN][entry.entry_id]
    entities = [
        BydRefreshButton(coordinator, data["gps_coordinators"].get(vin), vin)
        for vin, coordinator in data["coordinators"].items()
    ]
    async_add_entities(entities)


class BydRefreshButton(BydVehicleEntity, ButtonEntity):
    """Request new telemetry and GPS using the existing login session."""

    _attr_has_entity_name = True
    _attr_name = "立即刷新状态与定位"
    _attr_icon = "mdi:refresh"

    def __init__(
        self,
        coordinator: BydDataUpdateCoordinator,
        gps_coordinator: BydGpsUpdateCoordinator | None,
        vin: str,
    ) -> None:
        super().__init__(coordinator)
        self._vin = vin
        self._vehicle = coordinator.vehicle
        self._gps_coordinator = gps_coordinator
        self._attr_unique_id = f"{vin}_button_refresh_status"

    async def async_press(self) -> None:
        await self.coordinator.async_force_refresh()
        if self._gps_coordinator is not None:
            await self._gps_coordinator.async_force_refresh()
