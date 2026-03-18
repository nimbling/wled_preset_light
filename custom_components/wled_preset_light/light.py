from __future__ import annotations

import logging
from typing import Any

import aiohttp

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_EFFECT,
    ATTR_FLASH,
    ATTR_HS_COLOR,
    ATTR_RGB_COLOR,
    ATTR_RGBW_COLOR,
    ATTR_TRANSITION,
    ATTR_WHITE,
    ATTR_XY_COLOR,
    ColorMode,
    LightEntity,
    LightEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_state_change_event

_LOGGER = logging.getLogger(__name__)
DOMAIN = "wled_preset_light"

PASSTHROUGH_ATTRS = (
    ATTR_BRIGHTNESS,
    "color_temp",
    ATTR_HS_COLOR,
    ATTR_RGB_COLOR,
    ATTR_RGBW_COLOR,
    ATTR_XY_COLOR,
    ATTR_WHITE,
    ATTR_FLASH,
    ATTR_TRANSITION,
)


def _get_wled_url(hass: HomeAssistant, light_entity_id: str) -> str | None:
    ent_reg = er.async_get(hass)
    dev_reg = dr.async_get(hass)
    entry = ent_reg.async_get(light_entity_id)
    if not entry or not entry.device_id:
        return None
    device = dev_reg.async_get(entry.device_id)
    if not device:
        return None
    for config_entry_id in device.config_entries:
        config_entry = hass.config_entries.async_get_entry(config_entry_id)
        if config_entry and config_entry.domain == "wled":
            host = config_entry.data.get("host")
            if host:
                return f"http://{host}"
    return None


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    light_entity = entry.data["light_entity"]
    wled_url = _get_wled_url(hass, light_entity)
    if not wled_url:
        _LOGGER.error("Could not resolve WLED host for %s", light_entity)
        return

    async_add_entities([
        WledPresetLight(
            hass=hass,
            entry=entry,
            light_entity=light_entity,
            preset_select_entity=entry.data["preset_select_entity"],
            wled_url=wled_url,
        )
    ])


class WledPresetLight(LightEntity):
    _attr_should_poll = False
    _attr_has_entity_name = True

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        light_entity: str,
        preset_select_entity: str,
        wled_url: str,
    ) -> None:
        self._hass = hass
        self._entry = entry
        self._light_entity = light_entity
        self._preset_select_entity = preset_select_entity
        self._wled_url = wled_url
        self._led_count: int = 1
        self._attr_unique_id = entry.entry_id
        self._attr_name = entry.data["name"]

    async def async_added_to_hass(self) -> None:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self._wled_url}/json/info",
                    timeout=aiohttp.ClientTimeout(total=5),
                ) as resp:
                    info = await resp.json()
                    self._led_count = info["leds"]["count"]
                    _LOGGER.debug("%s: LED count = %d", self._attr_name, self._led_count)
        except Exception as e:
            _LOGGER.warning("%s: Could not fetch LED count: %s", self._attr_name, e)

        @callback
        def _state_changed(event):
            self.async_write_ha_state()

        self.async_on_remove(
            async_track_state_change_event(
                self._hass,
                [self._light_entity, self._preset_select_entity],
                _state_changed,
            )
        )

    def _light_state(self):
        return self._hass.states.get(self._light_entity)

    @property
    def is_on(self) -> bool:
        state = self._light_state()
        return state is not None and state.state == "on"

    @property
    def brightness(self) -> int | None:
        state = self._light_state()
        return state.attributes.get(ATTR_BRIGHTNESS) if state else None

    @property
    def color_mode(self) -> ColorMode | str | None:
        state = self._light_state()
        return state.attributes.get("color_mode") if state else ColorMode.UNKNOWN

    @property
    def supported_color_modes(self) -> set[ColorMode | str] | None:
        state = self._light_state()
        if state:
            modes = state.attributes.get("supported_color_modes")
            if modes:
                return set(modes)
        return {ColorMode.UNKNOWN}

    @property
    def supported_features(self) -> LightEntityFeature:
        state = self._light_state()
        base = LightEntityFeature.EFFECT
        if state:
            base |= LightEntityFeature(state.attributes.get("supported_features", 0))
        return base

    @property
    def rgb_color(self) -> tuple[int, int, int] | None:
        state = self._light_state()
        if state:
            rgb = state.attributes.get("rgb_color")
            if rgb:
                return tuple(rgb)
        return None

    @property
    def rgbw_color(self) -> tuple[int, int, int, int] | None:
        state = self._light_state()
        if state:
            rgbw = state.attributes.get("rgbw_color")
            if rgbw:
                return tuple(rgbw)
        return None

    @property
    def hs_color(self) -> tuple[float, float] | None:
        state = self._light_state()
        if state:
            hs = state.attributes.get("hs_color")
            if hs:
                return tuple(hs)
        return None

    @property
    def xy_color(self) -> tuple[float, float] | None:
        state = self._light_state()
        if state:
            xy = state.attributes.get("xy_color")
            if xy:
                return tuple(xy)
        return None

    @property
    def color_temp(self) -> int | None:
        state = self._light_state()
        return state.attributes.get("color_temp") if state else None

    @property
    def min_mireds(self) -> int:
        state = self._light_state()
        return state.attributes.get("min_mireds", 153) if state else 153

    @property
    def max_mireds(self) -> int:
        state = self._light_state()
        return state.attributes.get("max_mireds", 500) if state else 500

    @property
    def effect(self) -> str | None:
        state = self._hass.states.get(self._preset_select_entity)
        if state and state.state not in ("unknown", "unavailable"):
            return state.state
        return None

    @property
    def effect_list(self) -> list[str] | None:
        state = self._hass.states.get(self._preset_select_entity)
        if state:
            return state.attributes.get("options")
        return None

    async def async_turn_on(self, **kwargs: Any) -> None:
        if ATTR_EFFECT in kwargs:
            await self._hass.services.async_call(
                "select",
                "select_option",
                {
                    "entity_id": self._preset_select_entity,
                    "option": kwargs[ATTR_EFFECT],
                },
            )
        elif ATTR_RGB_COLOR in kwargs or ATTR_HS_COLOR in kwargs:
            try:
                if ATTR_RGB_COLOR in kwargs:
                    r, g, b = kwargs[ATTR_RGB_COLOR]
                else:
                    import colorsys
                    h, s = kwargs[ATTR_HS_COLOR]
                    r, g, b = (round(c * 255) for c in colorsys.hsv_to_rgb(h / 360, s / 100, 1))

                brightness = kwargs.get(ATTR_BRIGHTNESS, self.brightness or 255)
                payload = (
                    f'{{"on":true,"bri":{brightness},"ps":-1,'
                    f'"seg":[{{"id":0,"fx":0,'
                    f'"col":[[{r},{g},{b},0],[0,0,0,0],[0,0,0,0]],'
                    f'"pal":0,"bri":255,"start":0,"stop":{self._led_count}}}]}}'
                )
                async with aiohttp.ClientSession() as session:
                    await session.post(
                        f"{self._wled_url}/json/state",
                        data=payload,
                        headers={"Content-Type": "application/json"},
                    )
            except Exception as e:
                _LOGGER.error("%s: error applying color: %s", self._attr_name, e)
        else:
            service_data: dict[str, Any] = {"entity_id": self._light_entity}
            for attr in PASSTHROUGH_ATTRS:
                if attr in kwargs:
                    service_data[attr] = kwargs[attr]
            await self._hass.services.async_call("light", "turn_on", service_data)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._hass.services.async_call(
            "light", "turn_off", {"entity_id": self._light_entity}
        )

    async def async_update(self) -> None:
        pass
