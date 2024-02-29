"""Config flow for Illuminance integration."""
from __future__ import annotations

from abc import abstractmethod
from datetime import timedelta
from typing import Any, cast

import voluptuous as vol

from homeassistant.config_entries import (
    SOURCE_IMPORT,
    ConfigEntry,
    ConfigFlow,
    OptionsFlowWithConfigEntry,
)
from homeassistant.const import (
    CONF_ENTITY_ID,
    CONF_MODE,
    CONF_NAME,
    CONF_SCAN_INTERVAL,
    CONF_UNIQUE_ID,
)
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowHandler, FlowResult
from homeassistant.helpers.selector import (
    EntitySelector,
    EntitySelectorConfig,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectSelector,
    SelectSelectorConfig,
    TextSelector,
)

from .const import (
    CONF_FALLBACK,
    DEFAULT_FALLBACK,
    DEFAULT_NAME,
    DEFAULT_SCAN_INTERVAL_MIN,
    DOMAIN,
    MIN_SCAN_INTERVAL_MIN,
)
from .sensor import MODES


class IlluminanceFlow(FlowHandler):
    """Illuminance flow mixin."""

    @property
    @abstractmethod
    def options(self) -> dict[str, Any]:
        """Return mutable copy of options."""

    async def async_step_options(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Get sensor options."""
        if user_input is not None:
            self.options.update(user_input)
            return await self.async_step_done()

        schema = {
            vol.Required(
                CONF_MODE, default=self.options.get(CONF_MODE, MODES[0])
            ): SelectSelector(
                SelectSelectorConfig(options=MODES, translation_key="mode")
            ),
            vol.Required(
                CONF_ENTITY_ID, default=self.options.get(CONF_ENTITY_ID, vol.UNDEFINED)
            ): EntitySelector(EntitySelectorConfig(domain=["sensor", "weather"])),
            vol.Required(
                CONF_SCAN_INTERVAL,
                default=self.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL_MIN),
            ): NumberSelector(
                NumberSelectorConfig(
                    min=MIN_SCAN_INTERVAL_MIN, step=0.5, mode=NumberSelectorMode.BOX
                )
            ),
            vol.Required(
                CONF_FALLBACK, default=self.options.get(CONF_FALLBACK, DEFAULT_FALLBACK)
            ): NumberSelector(
                NumberSelectorConfig(
                    min=1, max=10, step="any", mode=NumberSelectorMode.BOX
                )
            ),
        }
        return self.async_show_form(step_id="options", data_schema=vol.Schema(schema))

    @abstractmethod
    async def async_step_done(self, _: dict[str, Any] | None = None) -> FlowResult:
        """Finish the flow."""


class IlluminanceConfigFlow(ConfigFlow, IlluminanceFlow, domain=DOMAIN):
    """Sun2 config flow."""

    VERSION = 1

    _name: str = DEFAULT_NAME

    def __init__(self) -> None:
        """Initialize config flow."""
        self._options: dict[str, Any] = {}

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> IlluminanceOptionsFlow:
        """Get the options flow for this handler."""
        flow = IlluminanceOptionsFlow(config_entry)
        flow.init_step = "options"
        return flow

    @classmethod
    @callback
    def async_supports_options_flow(cls, config_entry: ConfigEntry) -> bool:
        """Return options flow support for this handler."""
        if config_entry.source == SOURCE_IMPORT:
            return False
        return True

    @property
    def options(self) -> dict[str, Any]:
        """Return mutable copy of options."""
        return self._options

    async def async_step_import(self, data: dict[str, Any]) -> FlowResult:
        """Import config entry from configuration."""
        title = data.pop(CONF_NAME)
        # Convert from timedelta to float in minutes.
        data[CONF_SCAN_INTERVAL] = (
            cast(timedelta, data[CONF_SCAN_INTERVAL]).total_seconds() / 60
        )
        if existing_entry := await self.async_set_unique_id(data.pop(CONF_UNIQUE_ID)):
            self.hass.config_entries.async_update_entry(
                existing_entry, title=title, options=data
            )
            return self.async_abort(reason="already_configured")

        return self.async_create_entry(title=title, data={}, options=data)

    async def async_step_user(self, _: dict[str, Any] | None = None) -> FlowResult:
        """Start user config flow."""
        return await self.async_step_name()

    async def async_step_name(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Get name."""
        if user_input is not None:
            self._name = user_input[CONF_NAME]
            return await self.async_step_options()

        schema = {vol.Required(CONF_NAME, default=self._name): TextSelector()}
        return self.async_show_form(
            step_id="name", data_schema=vol.Schema(schema), last_step=False
        )

    async def async_step_done(self, _: dict[str, Any] | None = None) -> FlowResult:
        """Finish the flow."""
        return self.async_create_entry(title=self._name, data={}, options=self.options)


class IlluminanceOptionsFlow(OptionsFlowWithConfigEntry, IlluminanceFlow):
    """Sun2 integration options flow."""

    async def async_step_done(self, _: dict[str, Any] | None = None) -> FlowResult:
        """Finish the flow."""
        return self.async_create_entry(title="", data=self.options or {})
