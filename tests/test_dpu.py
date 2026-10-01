"""Delta Pro Ultra heartbeats."""

from __future__ import annotations

from custom_components.ecoflow_app.models import model_by_key
from custom_components.ecoflow_app.parsers import parse_payload

from .helpers import f32, frame, msg, u

DPU = model_by_key("delta_pro_ultra")


def test_app_show_heartbeat() -> None:
    pdata = (
        u(21, 76)
        + u(22, 2)
        + u(26, 300)
        + f32(41, 1200.0)
        + f32(42, 450.0)
        + f32(48, 200.0)
        + f32(53, 250.0)
        + f32(56, 800.0)
        + f32(57, 150.0)
        + f32(58, 250.0)
    )
    values = parse_payload(frame(2, 1, pdata), DPU).values
    assert values["soc"] == 76
    assert values["battery_pack_count"] == 2
    assert values["input_power_w"] == 1200.0
    assert values["ac_in_power_w"] == 800.0
    assert values["solar_lv_in_power_w"] == 150.0
    assert values["solar_hv_in_power_w"] == 250.0
    # Outlets missing from a full heartbeat are at 0 W.
    assert values["ac_out_power_w"] == 450.0


def test_backend_and_settings() -> None:
    backend = f32(61, 51.2) + f32(62, -3.5) + f32(91, 230.1) + f32(97, 35.0)
    para = u(9, 95) + u(10, 10) + u(5, 30) + u(4, 1)
    values = parse_payload(frame(2, 2, backend) + frame(2, 3, para), DPU).values
    assert values["battery_voltage_v"] == 51.2
    assert values["battery_current_a"] == -3.5
    assert values["ac_in_voltage_v"] == 230.1
    assert values["pcs_dc_temp_c"] == 35.0
    assert values["max_charge_soc"] == 95
    assert values["min_discharge_soc"] == 10
    assert values["backup_reserve_soc"] == 30
    assert values["backup_reserve_enabled"] is True


def test_battery_packs() -> None:
    pack1 = u(1, 1) + u(2, 2) + u(3, 80) + f32(4, 300.0) + f32(5, 4800.0) + u(11, 25)
    pack2 = u(1, 2) + u(3, 79) + f32(4, -10.0)
    values = parse_payload(frame(2, 4, msg(1, pack1) + msg(1, pack2)), DPU).values
    assert values["pack1_soc"] == 80
    assert values["pack1_power_w"] == 300.0
    assert values["pack1_remain_energy_wh"] == 4800.0
    assert values["pack1_temp_c"] == 25
    assert values["pack1_chg_dsg_state"] == "charging"
    assert values["pack2_soc"] == 79
    assert values["pack2_chg_dsg_state"] == "idle"


def test_display_frame_on_a_dpu_uses_the_dpu_schema() -> None:
    values = parse_payload(frame(254, 21, f32(262, 66.6) + u(270, 100) + u(462, 6144)), DPU).values
    assert values == {"soc": 66.6, "max_charge_soc": 100, "full_capacity_wh": 6144}


def test_idle_dc_output_still_reported() -> None:
    # A heartbeat with the DC (Anderson) output at 0 W: the device leaves the
    # field out, the sensor must still exist with 0 W.
    pdata = u(21, 50) + f32(41, 100.0) + f32(42, 60.0) + f32(43, 10.0) + f32(45, 50.0)
    values = parse_payload(frame(2, 1, pdata), DPU).values
    assert values["dc_anderson_out_power_w"] == 0.0
    assert values["usb_c2_out_power_w"] == 0.0
    assert values["dc_out_power_w"] == 60.0
    assert values["ac_out_power_w"] == 0.0


def test_dc_output_voltage_current_and_raw_fields() -> None:
    backend = f32(61, 51.2) + f32(73, 12.6) + f32(74, 4.5) + u(21, 3) + f32(75, 120.1)
    values = parse_payload(frame(2, 2, backend), DPU).values
    assert values["dc_anderson_out_voltage_v"] == 12.6
    assert values["dc_anderson_out_current_a"] == 4.5
    assert values["ac_l1_1_out_voltage_v"] == 120.1
    # Fields without a dedicated sensor are still exposed.
    assert values["raw_sys_work_sta"] == 3
    assert values["raw_ev_max_charger_cur"] == 0.0


def test_settings_and_pack_extras() -> None:
    para = u(15, 120) + u(18, 30) + u(11, 1) + u(19, 0) + u(1, 2)
    pack = u(1, 3) + u(3, 90) + u(8, 100) + u(9, 5) + u(6, 12)
    values = parse_payload(frame(2, 3, para) + frame(2, 4, msg(1, pack)), DPU).values
    assert values["device_standby_min"] == 120
    assert values["ac_standby_min"] == 30
    assert values["ac_always_on_enabled"] is True
    assert values["solar_only_enabled"] is False
    assert values["raw_sys_work_mode"] == 2
    assert values["pack3_soc"] == 90
    assert values["pack3_power_w"] == 0.0
    assert values["raw_pack3_bp_soc_max"] == 100
    assert values["raw_pack3_heat_time"] == 12
