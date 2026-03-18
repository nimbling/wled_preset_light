from __future__ import annotations

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.selector import (
    EntitySelector,
    EntitySelectorConfig,
    TextSelector,
)

DOMAIN = "wled_preset_light"


class WledPresetLightConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}

        if user_input is not None:
            light_entity = user_input["light_entity"]
            preset_select_entity = user_input["preset_select_entity"]

            ent_reg = er.async_get(self.hass)
            if not ent_reg.async_get(light_entity):
                errors["light_entity"] = "entity_not_found"
            if not ent_reg.async_get(preset_select_entity):
                errors["preset_select_entity"] = "entity_not_found"

            if not errors:
                await self.async_set_unique_id(light_entity)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=user_input["name"],
                    data=user_input,
                )

        schema = vol.Schema({
            vol.Required("name"): TextSelector(),
            vol.Required("light_entity"): EntitySelector(
                EntitySelectorConfig(domain="light", integration="wled")
            ),
            vol.Required("preset_select_entity"): EntitySelector(
                EntitySelectorConfig(domain="select", integration="wled")
            ),
        })

        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            description_placeholders={
                "docs_url": "https://github.com/nimbling/wled_preset_light"
            },
            errors=errors,
        )