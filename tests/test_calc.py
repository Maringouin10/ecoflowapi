"""Derived values and energy integration."""

from __future__ import annotations

import pytest

from custom_components.ecoflow_app.calc import derive, integrate


def test_battery_flow_and_solar_total() -> None:
    values = {
        "input_power_w": 500.0,
        "output_power_w": 200.0,
        "solar_in_power_w": 250.0,
        "solar2_in_power_w": 150.0,
    }
    derived = derive(values, values)
    assert derived["battery_charge_power_w"] == 300.0
    assert derived["battery_discharge_power_w"] == 0.0
    assert derived["solar_total_power_w"] == 400.0


def test_remaining_time_only_for_the_active_direction() -> None:
    values = {
        "chg_dsg_state": "charging",
        "charge_remaining_raw_min": 51,
        "discharge_remaining_raw_min": 12927,
    }
    derived = derive(values, values)
    assert derived["charge_remaining_min"] == 51
    assert derived["discharge_remaining_min"] is None


def test_soc_falls_back_to_the_main_battery_until_a_combined_one_arrives() -> None:
    values = {"main_battery_soc": 61.0}
    values.update(derive(values, {"main_battery_soc": 61.0}))
    assert values["soc"] == 61.0

    values["main_battery_soc"] = 60.0
    values.update(derive(values, {"main_battery_soc": 60.0}))
    assert values["soc"] == 60.0

    values["soc"] = 64.0
    values.update(derive(values, {"soc": 64.0}))
    values["main_battery_soc"] = 59.0
    values.update(derive(values, {"main_battery_soc": 59.0}))
    assert values["soc"] == 64.0


def test_trapezoidal_integration() -> None:
    values = {"ac_out_power_w": 1000.0}
    last: dict = {}
    integrate(values, last, 0.0, 300)
    assert values["ac_out_energy_kwh"] == 0.0
    values["ac_out_power_w"] = 2000.0
    integrate(values, last, 60.0, 300)
    # (1000 + 2000) / 2 W for one minute = 25 Wh
    assert values["ac_out_energy_kwh"] == pytest.approx(0.025)


def test_gaps_are_not_integrated() -> None:
    values = {"ac_out_power_w": 1000.0, "ac_out_energy_kwh": 1.0}
    last: dict = {}
    integrate(values, last, 0.0, 300)
    integrate(values, last, 3600.0, 300)
    assert values["ac_out_energy_kwh"] == 1.0
