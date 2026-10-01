"""Device models supported by the integration and how they are recognised.

Every supported battery speaks one of three dialects on the app's MQTT
connection, and the dialect is what decides how a frame is parsed:

* ``json``  - Delta 2 / River 2 generation. JSON ``{"params": {"pd.soc": ..}}``.
* ``gen3``  - Delta 3 / River 3 generation (and Delta 3 Ultra). Protobuf,
              status frame ``cmd_func=254 cmd_id=21``.
* ``dpu``   - Delta Pro Ultra. Protobuf heartbeats on ``cmd_func=2``.

Parsing is driven by the frame itself (JSON vs. protobuf, cmd_func/cmd_id),
so a model that is not recognised from its name still produces data. The
model only matters for the device name in Home Assistant and for a few unit
conventions of the JSON generation.
"""

from __future__ import annotations

from dataclasses import dataclass

DIALECT_JSON = "json"
DIALECT_GEN3 = "gen3"
DIALECT_DPU = "dpu"


@dataclass(frozen=True)
class DeviceModel:
    """A supported EcoFlow model."""

    key: str
    name: str
    dialect: str
    # Serial-number prefixes known for this model (first four characters).
    prefixes: tuple[str, ...] = ()
    # Lower-case substrings of the product name reported by the cloud. The
    # most specific names must come first in MODELS.
    keywords: tuple[str, ...] = ()
    # JSON generation only: divisor that turns ``mppt.inVol`` into volts.
    solar_voltage_divisor: float = 10.0
    # Highest number of extra batteries the model accepts.
    max_extra_batteries: int = 0


MODELS: tuple[DeviceModel, ...] = (
    DeviceModel(
        "delta_pro_ultra",
        "DELTA Pro Ultra",
        DIALECT_DPU,
        prefixes=("Y711", "Y701"),
        keywords=("delta pro ultra",),
        max_extra_batteries=5,
    ),
    DeviceModel(
        "delta_3_ultra",
        "DELTA 3 Ultra",
        DIALECT_GEN3,
        keywords=("delta 3 ultra",),
        max_extra_batteries=2,
    ),
    DeviceModel(
        "delta_3",
        "DELTA 3",
        DIALECT_GEN3,
        prefixes=("P231", "P321", "P351", "D361", "D3M1", "D3N1"),
        keywords=("delta 3",),
        max_extra_batteries=2,
    ),
    DeviceModel(
        "river_3",
        "RIVER 3",
        DIALECT_GEN3,
        prefixes=("R651", "R653", "R654", "R655", "R631", "R633", "R634"),
        keywords=("river 3",),
    ),
    DeviceModel(
        "delta_2",
        "DELTA 2",
        DIALECT_JSON,
        prefixes=("R331", "R335", "R351", "R354"),
        keywords=("delta 2",),
        solar_voltage_divisor=10.0,
        max_extra_batteries=2,
    ),
    DeviceModel(
        "river_2",
        "RIVER 2",
        DIALECT_JSON,
        prefixes=("R601", "R603", "R611", "R613", "R621", "R623"),
        keywords=("river 2",),
        solar_voltage_divisor=1000.0,
    ),
)

UNKNOWN_MODEL = DeviceModel("unknown", "EcoFlow", "")

_BY_KEY = {m.key: m for m in MODELS}


def model_by_key(key: str) -> DeviceModel:
    """Return a model from its key, or the unknown model."""
    return _BY_KEY.get(key, UNKNOWN_MODEL)


def detect_model(product_name: str | None, sn: str | None) -> DeviceModel:
    """Recognise the model from the product name, then the serial prefix.

    The name comes from the cloud and is the most precise source ("DELTA 3
    Ultra" vs "DELTA 3"); the prefix is the fallback when the name is empty.
    """
    name = (product_name or "").lower()
    if name:
        for model in MODELS:
            if any(kw in name for kw in model.keywords):
                return model
    prefix = (sn or "")[:4].upper()
    if prefix:
        for model in MODELS:
            if prefix in model.prefixes:
                return model
    return UNKNOWN_MODEL


def is_supported(model: DeviceModel) -> bool:
    """Return whether the model is one this integration handles."""
    return model is not UNKNOWN_MODEL
