"""Config flow for Waste Management Pickup integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.httpx_client import get_async_client

from waste_management import WMClient


from .const import CONF_ACCOUNT, CONF_SERVICES, DOMAIN

_LOGGER = logging.getLogger(__name__)

# TODO adjust the data schema to the data that you need
STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required("username"): str,
        vol.Required("password"): str,
    }
)


class WasteManagementData:
    def __init__(self):
        self.accounts = None
        self.services = None


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """

    hub = WMClient(data["username"], data["password"], get_async_client(hass))

    try:
        await hub.async_authenticate()
        await hub.async_okta_authorize()
    except Exception as ex:
        raise InvalidAuth from ex

    return hub


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Waste Management Pickup."""

    def __init__(self):

        self.data: dict = {}
        self.wmData = WasteManagementData()

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_DATA_SCHEMA
            )

        errors = {}

        try:
            self._wmclient: WMClient = await validate_input(self.hass, user_input)
            self.data[CONF_USERNAME] = user_input[CONF_USERNAME]
            self.data[CONF_PASSWORD] = user_input[CONF_PASSWORD]
        except InvalidAuth:
            errors["base"] = "invalid_auth"
        except Exception as ex:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception %s", ex)
            errors["base"] = "unknown"
        else:
            return await self.async_step_accounts()

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_accounts(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        if user_input is None:
            errors = {}
            try:
                self.wmData.accounts = await self._wmclient.async_get_accounts()
            except Exception as ex:
                _LOGGER.exception("Unexpected exception %s", ex)
                errors["base"] = "unknown"

            self._accounts = {x.id: x.name for x in self.wmData.accounts}
            return self.async_show_form(
                step_id="accounts",
                data_schema=vol.Schema(
                    {vol.Required(CONF_ACCOUNT): vol.In(self._accounts)}
                ),
                errors=errors,
            )
        else:
            self.data[CONF_ACCOUNT] = user_input[CONF_ACCOUNT]
            return await self.async_step_services()

    async def async_step_services(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        if user_input is None:
            errors = {}
            try:
                self.wmData.services = await self._wmclient.async_get_services(
                    self.data[CONF_ACCOUNT]
                )
            except Exception as ex:
                _LOGGER.exception("Unexpected exception %s", ex)
                errors["base"] = "unknown"
            self._services = {x.id: x.name for x in self.wmData.services}
            return self.async_show_form(
                step_id="services",
                data_schema=vol.Schema(
                    {
                        vol.Required(
                            CONF_SERVICES, default=list(self._services)
                        ): cv.multi_select(self._services)
                    }
                ),
                errors=errors,
            )
        else:
            self.data[CONF_SERVICES] = user_input[CONF_SERVICES]

            title = next(
                x.name for x in self.wmData.accounts if x.id == self.data[CONF_ACCOUNT]
            )
            return self.async_create_entry(title=title, data=self.data)


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
