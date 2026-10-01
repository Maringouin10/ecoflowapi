"""Values computed from the reported ones, and energy integration.

Pure Python (no Home Assistant import) so it can be unit-tested.
"""

from __future__ import annotations

from typing import Any

# Power key -> energy key integrated from it (kWh).
ENERGY_SOURCES: dict[str, str] = {
    "input_power_w": "input_energy_kwh",
    "output_power_w": "output_energy_kwh",
    "ac_in_power_w": "ac_in_energy_kwh",
    "ac_out_power_w": "ac_out_energy_kwh",
    "solar_total_power_w": "solar_in_energy_kwh",
    "battery_charge_power_w": "battery_charge_energy_kwh",
    "battery_discharge_power_w": "battery_discharge_energy_kwh",
}

# A remaining time this long (> 4 days) is a placeholder, not an estimate.
REMAIN_TIME_PLACEHOLDER_MIN = 6000

# Delta Pro Ultra: per-outlet powers that add up to the AC / DC totals.
_DPU_AC_OUTLETS = (
    "ac_l1_1_out_power_w",
    "ac_l1_2_out_power_w",
    "ac_l2_1_out_power_w",
    "ac_l2_2_out_power_w",
    "ac_tt30_out_power_w",
    "ac_l14_out_power_w",
)
_DPU_DC_OUTLETS = (
    "usb_a1_out_power_w",
    "usb_a2_out_power_w",
    "usb_c1_out_power_w",
    "usb_c2_out_power_w",
    "dc_anderson_out_power_w",
)

_SOLAR_KEYS = (
    "solar_in_power_w",
    "solar2_in_power_w",
    "solar_hv_in_power_w",
    "solar_lv_in_power_w",
)

# Marker: "soc" is a copy of the main battery's SoC (no combined SoC seen).
_SOC_FROM_MAIN = "_soc_from_main"


def _num(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def derive(values: dict[str, Any], fresh: dict[str, Any]) -> dict[str, Any]:
    """Return computed values from the merged ``values``.

    ``fresh`` is what the last message contained, used to tell a combined SoC
    reported by the device from one copied here.
    """
    derived: dict[str, Any] = {}

    # Totals from the merged per-outlet values (never from one frame, which
    # only carries the outlets that changed).
    if any(_num(values.get(k)) for k in _DPU_AC_OUTLETS):
        derived["ac_out_power_w"] = round(
            sum(float(values[k]) for k in _DPU_AC_OUTLETS if _num(values.get(k))), 1
        )
    if _num(values.get("dc_anderson_out_power_w")):
        derived["dc_out_power_w"] = round(
            sum(float(values[k]) for k in _DPU_DC_OUTLETS if _num(values.get(k))), 1
        )

    solar = [values[k] for k in _SOLAR_KEYS if _num(values.get(k))]
    if solar:
        derived["solar_total_power_w"] = round(sum(solar), 1)

    p_in, p_out = values.get("input_power_w"), values.get("output_power_w")
    if _num(p_in) and _num(p_out):
        # Net flow into the battery. Approximate (conversion losses count as
        # output) but available on every model.
        net = float(p_in) - float(p_out)
        derived["battery_charge_power_w"] = round(max(net, 0.0), 1)
        derived["battery_discharge_power_w"] = round(max(-net, 0.0), 1)

    # Some messages only carry the built-in battery's SoC; use it for the
    # main SoC entity until the device reports a combined one.
    if "soc" in fresh:
        derived[_SOC_FROM_MAIN] = False
    elif values.get(_SOC_FROM_MAIN, True) and _num(values.get("main_battery_soc")):
        derived["soc"] = values["main_battery_soc"]
        derived[_SOC_FROM_MAIN] = True

    # Both remaining times are always reported and the inactive one sits on
    # a placeholder; only the active direction is meaningful.
    state = values.get("chg_dsg_state")
    for key, active in (("charge_remaining", "charging"), ("discharge_remaining", "discharging")):
        raw = values.get(f"{key}_raw_min")
        if not _num(raw):
            continue
        valid = raw < REMAIN_TIME_PLACEHOLDER_MIN and state in (active, None)
        derived[f"{key}_min"] = float(raw) if valid else None
    return derived


def integrate(
    values: dict[str, Any],
    last: dict[str, tuple[float, float]],
    now: float,
    max_gap: float,
) -> None:
    """Add the energy since the previous reading to each total (in place).

    Trapezoidal rule between two readings; a gap longer than ``max_gap``
    seconds is skipped because nothing is known about it.
    """
    for power_key, energy_key in ENERGY_SOURCES.items():
        power = values.get(power_key)
        if not _num(power):
            continue
        power = max(float(power), 0.0)
        previous = last.get(power_key)
        last[power_key] = (now, power)
        total = float(values.get(energy_key) or 0.0)
        if previous is not None:
            elapsed = now - previous[0]
            if 0 < elapsed <= max_gap:
                total += (previous[1] + power) / 2.0 * elapsed / 3_600_000.0
        values[energy_key] = round(total, 6)
