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

from waste_management import WMClient

CONF_ACCOUNT = "account"

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

# TODO adjust the data schema to the data that you need
STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required("username"): str,
        vol.Required("password"): str,
    }
)


class PlaceholderHub:
    """Placeholder class to make tests pass.

    TODO Remove this placeholder class and replace with things from your PyPI package.
    """

    def __init__(self, host: str) -> None:
        """Initialize."""
        self.host = host

    async def authenticate(self, username: str, password: str) -> bool:
        """Test if we can authenticate with the host."""
        return True


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """

    hub = WMClient(data["username"], data["password"])

    try:
        await hass.async_add_executor_job(hub.authenticate)
        await hass.async_add_executor_job(hub.okta_authorize)
    except Exception:
        raise InvalidAuth

    return hub


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Waste Management Pickup."""

    def __init__(self):

        self.data: dict = {}

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
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            return await self.async_step_accounts()
        #    return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_accounts(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        if user_input is None:
            account_data = await self.hass.async_add_executor_job(
                self._wmclient.get_accounts
            )

            self._accounts = {x.id: x.name for x in account_data}
            return self.async_show_form(
                step_id="accounts",
                data_schema=vol.Schema(
                    {vol.Required("account"): vol.In(self._accounts)}
                ),
            )
        else:
            self.data[CONF_ACCOUNT] = user_input[CONF_ACCOUNT]
            return await self.async_step_services()

    async def async_step_services(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        if user_input is None:
            service_data = await self.hass.async_add_executor_job(
                self._wmclient.get_services, self.data["account"]
            )
            self._services = {x.id: x.name for x in service_data}
            return self.async_show_form(
                step_id="services",
                data_schema=vol.Schema(
                    {
                        vol.Required(
                            "services", default=list(self._services)
                        ): cv.multi_select(self._services)
                    }
                ),
            )


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
