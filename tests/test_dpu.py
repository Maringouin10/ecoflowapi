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
    values = parse_payload(frame(254, 21, f32(262, 66.6) + u(270, 100)), DPU).values
    assert values == {"soc": 66.6, "max_charge_soc": 100}
