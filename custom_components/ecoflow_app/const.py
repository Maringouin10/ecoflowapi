"""Constants for the EcoFlow App integration."""

from __future__ import annotations

DOMAIN = "ecoflow_app"
MANUFACTURER = "EcoFlow"

CONF_EMAIL = "email"
CONF_PASSWORD = "password"
CONF_DEVICES = "devices"

# --- EcoFlow cloud (same endpoints the mobile app / web portal use) ---------
API_BASE_URLS = (
    "https://api-e.ecoflow.com",  # EU
    "https://api.ecoflow.com",  # global
)
MQTT_HOST = "mqtt-e.ecoflow.com"
MQTT_PORT_WSS = 8084
MQTT_WSS_PATH = "/mqtt"

# --- Timings (seconds) ------------------------------------------------------
# The app asks for the latest values regularly while it is open; doing the
# same keeps the devices pushing.
QUOTAS_KEEPALIVE_S = 30
GET_ALL_KEEPALIVE_S = 300
# A device that has said nothing for this long is shown as unavailable.
STALE_AFTER_S = 600
# Credentials handed out by the portal are long-lived, but refreshing them
# daily avoids a silent expiry.
CREDENTIAL_MAX_AGE_S = 24 * 3600
RECONNECT_MIN_DELAY_S = 5
RECONNECT_MAX_DELAY_S = 300

# Energy integration: a gap longer than this between two power readings is
# not integrated (the device was offline, nothing is known about that span).
ENERGY_MAX_GAP_S = 300

PLATFORMS = ["sensor", "binary_sensor"]

SIGNAL_NEW_KEYS = f"{DOMAIN}_new_keys_{{entry_id}}"
STORAGE_VERSION = 1
STORAGE_KEY = f"{DOMAIN}.seen_keys"
