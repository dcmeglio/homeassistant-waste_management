from datetime import timedelta
import datetime

import homeassistant
from .const import CONF_ACCOUNT, CONF_SERVICES
from homeassistant.components.sensor import SensorEntity
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
import homeassistant.helpers.event
from homeassistant.core import HomeAssistant

from waste_management import WMClient


SCAN_INTERVAL = timedelta(hours=12)


async def async_setup_entry(hass: HomeAssistant, config, add_entities):
    config_data = config.data
    entities = []
    client = WMClient(config_data[CONF_USERNAME], config_data[CONF_PASSWORD])
    await hass.async_add_executor_job(client.authenticate)
    await hass.async_add_executor_job(client.okta_authorize)
    wm_services = await hass.async_add_executor_job(
        client.get_services, config_data[CONF_ACCOUNT]
    )
    for svc_id in config_data[CONF_SERVICES]:
        name = next(x.name for x in wm_services if x.id == svc_id)
        entities.append(
            WasteManagementSensorEntity(
                hass,
                name,
                config_data[CONF_USERNAME],
                config_data[CONF_PASSWORD],
                config_data[CONF_ACCOUNT],
                svc_id,
            )
        )
    add_entities(entities, True)


class WasteManagementSensorEntity(SensorEntity):
    def __init__(self, hass, name, username, password, account_id, service_id):

        self._attr_has_entity_name = True
        self.hass: HomeAssistant = hass
        self.username = username
        self.password = password
        self.account_id = account_id
        self.service_id = service_id

        self._attr_name = name
        self._attr_unique_id = f"{account_id}_{service_id}"
        self._attr_icon = "mdi:trash-can"
        self._attr_device_class = "timestamp"

        homeassistant.helpers.event.async_track_utc_time_change(
            hass, self.timer_callback, hour=0, minute=1
        )

    async def timer_callback(self, datetime):
        self.async_update()

    async def async_update(self) -> None:
        client = WMClient(self.username, self.password)
        await self.hass.async_add_executor_job(client.authenticate)

        await self.hass.async_add_executor_job(client.okta_authorize)

        pickup = await self.hass.async_add_executor_job(
            client.get_service_pickup, self.account_id, self.service_id
        )

        today = datetime.date.today()
        proposed_pickup = pickup[0].astimezone()
        if proposed_pickup.date() < today:
            proposed_pickup = pickup[1].astimestamp()
        self._attr_native_value = proposed_pickup
