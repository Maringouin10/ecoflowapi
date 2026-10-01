"""Generate strings.json and translations/{en,fr}.json.

Run from the repository root:  python scripts/gen_translations.py
The test suite checks that every entity translation key is covered.
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "custom_components" / "ecoflow_app"

CONFIG = {
    "en": {
        "step": {
            "user": {
                "title": "EcoFlow account",
                "description": "Sign in with the e-mail and password of the EcoFlow app. No developer keys are needed.",
                "data": {"email": "E-mail", "password": "Password"},
            },
            "devices": {
                "title": "Batteries",
                "description": "Choose the devices to add. Supported: DELTA 2, DELTA 3, DELTA 3 Ultra, DELTA 2 extra battery, DELTA Pro Ultra, RIVER 2, RIVER 3.",
                "data": {"devices": "Devices"},
            },
            "reauth_confirm": {
                "title": "EcoFlow password",
                "description": "EcoFlow refused the password of {email}. Enter the current one.",
                "data": {"password": "Password"},
            },
        },
        "error": {
            "invalid_auth": "E-mail or password refused by EcoFlow.",
            "cannot_connect": "Could not reach the EcoFlow cloud.",
            "no_selection": "Select at least one device.",
        },
        "abort": {
            "already_configured": "This EcoFlow account is already configured.",
            "no_devices": "No device is linked to this EcoFlow account.",
            "reauth_successful": "Password updated.",
        },
    },
    "fr": {
        "step": {
            "user": {
                "title": "Compte EcoFlow",
                "description": "Connectez-vous avec l'e-mail et le mot de passe de l'application EcoFlow. Aucune clé développeur n'est nécessaire.",
                "data": {"email": "E-mail", "password": "Mot de passe"},
            },
            "devices": {
                "title": "Batteries",
                "description": "Choisissez les appareils à ajouter. Pris en charge : DELTA 2, DELTA 3, DELTA 3 Ultra, batterie supplémentaire DELTA 2, DELTA Pro Ultra, RIVER 2, RIVER 3.",
                "data": {"devices": "Appareils"},
            },
            "reauth_confirm": {
                "title": "Mot de passe EcoFlow",
                "description": "EcoFlow a refusé le mot de passe de {email}. Saisissez le mot de passe actuel.",
                "data": {"password": "Mot de passe"},
            },
        },
        "error": {
            "invalid_auth": "E-mail ou mot de passe refusé par EcoFlow.",
            "cannot_connect": "Impossible de joindre le cloud EcoFlow.",
            "no_selection": "Sélectionnez au moins un appareil.",
        },
        "abort": {
            "already_configured": "Ce compte EcoFlow est déjà configuré.",
            "no_devices": "Aucun appareil n'est associé à ce compte EcoFlow.",
            "reauth_successful": "Mot de passe mis à jour.",
        },
    },
}

OPTIONS = {
    "en": {
        "step": {
            "init": {
                "title": "Devices",
                "description": "Devices included in Home Assistant.",
                "data": {"devices": "Devices"},
            }
        },
        "error": {
            "cannot_connect": "Could not refresh the device list; showing the saved one.",
            "no_selection": "Select at least one device.",
        },
    },
    "fr": {
        "step": {
            "init": {
                "title": "Appareils",
                "description": "Appareils inclus dans Home Assistant.",
                "data": {"devices": "Appareils"},
            }
        },
        "error": {
            "cannot_connect": "Impossible de rafraîchir la liste ; la liste enregistrée est affichée.",
            "no_selection": "Sélectionnez au moins un appareil.",
        },
    },
}

STATE = {
    "en": {"idle": "Idle", "charging": "Charging", "discharging": "Discharging"},
    "fr": {"idle": "Au repos", "charging": "En charge", "discharging": "En décharge"},
}

# translation_key -> (English, French)
SENSOR = {
    "soc": ("State of charge", "Niveau de charge"),
    "main_battery_soc": ("Main battery state of charge", "Niveau batterie principale"),
    "soh": ("State of health", "État de santé"),
    "chg_dsg_state": ("Battery state", "État de la batterie"),
    "charge_remaining_min": ("Time to full", "Temps avant charge complète"),
    "discharge_remaining_min": ("Time to empty", "Autonomie restante"),
    "remaining_time_min": ("Remaining time", "Temps restant"),
    "cycles": ("Charge cycles", "Cycles de charge"),
    "battery_temp_c": ("Battery temperature", "Température batterie"),
    "min_cell_temp_c": ("Minimum cell temperature", "Température cellule min"),
    "max_cell_temp_c": ("Maximum cell temperature", "Température cellule max"),
    "max_mos_temp_c": ("MOSFET temperature", "Température MOSFET"),
    "battery_voltage_v": ("Battery voltage", "Tension batterie"),
    "battery_current_a": ("Battery current", "Courant batterie"),
    "min_cell_voltage_v": ("Minimum cell voltage", "Tension cellule min"),
    "max_cell_voltage_v": ("Maximum cell voltage", "Tension cellule max"),
    "remain_capacity_mah": ("Remaining capacity", "Capacité restante"),
    "full_capacity_mah": ("Full capacity", "Capacité pleine charge"),
    "design_capacity_mah": ("Design capacity", "Capacité nominale"),
    "remain_capacity_wh": ("Remaining energy", "Énergie restante"),
    "full_capacity_wh": ("Total capacity", "Capacité totale"),
    "battery_pack_count": ("Battery packs", "Packs batterie"),
    "battery_power_w": ("Battery power", "Puissance batterie"),
    "max_charge_soc": ("Charge limit", "Limite de charge"),
    "min_discharge_soc": ("Discharge limit", "Limite de décharge"),
    "backup_reserve_soc": ("Backup reserve", "Réserve de secours"),
    "ac_charge_power_limit_w": ("AC charge power setting", "Puissance de charge AC réglée"),
    "input_power_w": ("Total input power", "Puissance d'entrée totale"),
    "output_power_w": ("Total output power", "Puissance de sortie totale"),
    "battery_charge_power_w": ("Battery charge power", "Puissance de charge batterie"),
    "battery_discharge_power_w": ("Battery discharge power", "Puissance de décharge batterie"),
    "ac_in_power_w": ("AC input power", "Puissance entrée AC"),
    "ac_out_power_w": ("AC output power", "Puissance sortie AC"),
    "ac_hv_out_power_w": ("AC output power (high voltage)", "Puissance sortie AC (haute tension)"),
    "ac_lv_out_power_w": ("AC output power (low voltage)", "Puissance sortie AC (basse tension)"),
    "ac_l1_1_out_power_w": ("AC outlet L1-1 power", "Puissance prise AC L1-1"),
    "ac_l1_2_out_power_w": ("AC outlet L1-2 power", "Puissance prise AC L1-2"),
    "ac_l2_1_out_power_w": ("AC outlet L2-1 power", "Puissance prise AC L2-1"),
    "ac_l2_2_out_power_w": ("AC outlet L2-2 power", "Puissance prise AC L2-2"),
    "ac_tt30_out_power_w": ("AC TT-30 outlet power", "Puissance prise AC TT-30"),
    "ac_l14_out_power_w": ("AC L14-30 outlet power", "Puissance prise AC L14-30"),
    "power_in_out_in_power_w": ("Power In/Out input power", "Puissance entrée Power In/Out"),
    "power_in_out_out_power_w": ("Power In/Out output power", "Puissance sortie Power In/Out"),
    "ac_in_voltage_v": ("AC input voltage", "Tension entrée AC"),
    "ac_in_current_a": ("AC input current", "Courant entrée AC"),
    "ac_out_voltage_v": ("AC output voltage", "Tension sortie AC"),
    "ac_out_current_a": ("AC output current", "Courant sortie AC"),
    "ac_in_freq_hz": ("AC input frequency", "Fréquence entrée AC"),
    "ac_out_freq_hz": ("AC output frequency", "Fréquence sortie AC"),
    "solar_in_power_w": ("Solar input power", "Puissance solaire"),
    "solar2_in_power_w": ("Solar input 2 power", "Puissance solaire 2"),
    "solar_hv_in_power_w": (
        "Solar input power (high voltage)",
        "Puissance solaire (haute tension)",
    ),
    "solar_lv_in_power_w": ("Solar input power (low voltage)", "Puissance solaire (basse tension)"),
    "solar_total_power_w": ("Total solar power", "Puissance solaire totale"),
    "solar_in_voltage_v": ("Solar input voltage", "Tension solaire"),
    "solar_in_current_a": ("Solar input current", "Courant solaire"),
    "solar_hv_in_voltage_v": ("Solar voltage (high voltage)", "Tension solaire (haute tension)"),
    "solar_hv_in_current_a": ("Solar current (high voltage)", "Courant solaire (haute tension)"),
    "solar_lv_in_voltage_v": ("Solar voltage (low voltage)", "Tension solaire (basse tension)"),
    "solar_lv_in_current_a": ("Solar current (low voltage)", "Courant solaire (basse tension)"),
    "dc12v_out_power_w": ("12 V output power", "Puissance sortie 12 V"),
    "dc24v_out_power_w": ("24 V output power", "Puissance sortie 24 V"),
    "usb_a1_out_power_w": ("USB-A 1 power", "Puissance USB-A 1"),
    "usb_a2_out_power_w": ("USB-A 2 power", "Puissance USB-A 2"),
    "usb_qc1_out_power_w": ("USB-A fast charge 1 power", "Puissance USB-A charge rapide 1"),
    "usb_qc2_out_power_w": ("USB-A fast charge 2 power", "Puissance USB-A charge rapide 2"),
    "usb_c1_out_power_w": ("USB-C 1 power", "Puissance USB-C 1"),
    "usb_c2_out_power_w": ("USB-C 2 power", "Puissance USB-C 2"),
    "usb_c3_out_power_w": ("USB-C 3 power", "Puissance USB-C 3"),
    "dc_out_power_w": ("DC output power (total)", "Puissance sortie DC (totale)"),
    "dc_anderson_out_power_w": ("DC output power (Anderson)", "Puissance sortie DC (Anderson)"),
    "dc_anderson_out_voltage_v": ("DC output voltage (Anderson)", "Tension sortie DC (Anderson)"),
    "dc_anderson_out_current_a": ("DC output current (Anderson)", "Courant sortie DC (Anderson)"),
    "dc12v_out_voltage_v": ("12 V output voltage", "Tension sortie 12 V"),
    "dc12v_out_current_a": ("12 V output current", "Courant sortie 12 V"),
    "usb_a1_out_voltage_v": ("USB-A 1 voltage", "Tension USB-A 1"),
    "usb_a1_out_current_a": ("USB-A 1 current", "Courant USB-A 1"),
    "usb_a2_out_voltage_v": ("USB-A 2 voltage", "Tension USB-A 2"),
    "usb_a2_out_current_a": ("USB-A 2 current", "Courant USB-A 2"),
    "usb_c1_out_voltage_v": ("USB-C 1 voltage", "Tension USB-C 1"),
    "usb_c1_out_current_a": ("USB-C 1 current", "Courant USB-C 1"),
    "usb_c2_out_voltage_v": ("USB-C 2 voltage", "Tension USB-C 2"),
    "usb_c2_out_current_a": ("USB-C 2 current", "Courant USB-C 2"),
    "pr_out_power_w": ("PR output power", "Puissance sortie PR"),
    "ac_l1_1_out_voltage_v": ("AC outlet L1-1 voltage", "Tension prise AC L1-1"),
    "ac_l1_1_out_current_a": ("AC outlet L1-1 current", "Courant prise AC L1-1"),
    "ac_l1_2_out_voltage_v": ("AC outlet L1-2 voltage", "Tension prise AC L1-2"),
    "ac_l1_2_out_current_a": ("AC outlet L1-2 current", "Courant prise AC L1-2"),
    "ac_l2_1_out_voltage_v": ("AC outlet L2-1 voltage", "Tension prise AC L2-1"),
    "ac_l2_1_out_current_a": ("AC outlet L2-1 current", "Courant prise AC L2-1"),
    "ac_l2_2_out_voltage_v": ("AC outlet L2-2 voltage", "Tension prise AC L2-2"),
    "ac_l2_2_out_current_a": ("AC outlet L2-2 current", "Courant prise AC L2-2"),
    "ac_tt30_out_voltage_v": ("AC TT-30 outlet voltage", "Tension prise AC TT-30"),
    "ac_tt30_out_current_a": ("AC TT-30 outlet current", "Courant prise AC TT-30"),
    "ac_l14_out_voltage_v": ("AC L14-30 outlet voltage", "Tension prise AC L14-30"),
    "ac_l14_out_current_a": ("AC L14-30 outlet current", "Courant prise AC L14-30"),
    "power_in_out_out_voltage_v": ("Power In/Out output voltage", "Tension sortie Power In/Out"),
    "power_in_out_out_current_a": ("Power In/Out output current", "Courant sortie Power In/Out"),
    "power_in_out_in_voltage_v": ("Power In/Out input voltage", "Tension entrée Power In/Out"),
    "power_in_out_in_current_a": ("Power In/Out input current", "Courant entrée Power In/Out"),
    "power_in_out_charge_power_limit_w": (
        "Power In/Out charge power setting",
        "Puissance de charge Power In/Out réglée",
    ),
    "ac_charge_power_max_w": ("AC charge power maximum", "Puissance de charge AC maximale"),
    "battery_charge_power_bms_w": ("Battery charge power (BMS)", "Puissance de charge (BMS)"),
    "battery_discharge_power_bms_w": (
        "Battery discharge power (BMS)",
        "Puissance de décharge (BMS)",
    ),
    "battery_charge_power_max_w": (
        "Battery charge power maximum",
        "Puissance de charge max batterie",
    ),
    "battery_discharge_power_max_w": (
        "Battery discharge power maximum",
        "Puissance de décharge max batterie",
    ),
    "ac_always_on_min_soc": ("AC always-on minimum charge", "Niveau min. AC toujours actif"),
    "device_standby_min": ("Device standby timeout", "Mise en veille appareil"),
    "ac_standby_min": ("AC standby timeout", "Mise en veille AC"),
    "dc_standby_min": ("DC standby timeout", "Mise en veille DC"),
    "screen_timeout_s": ("Screen timeout", "Extinction écran"),
    "inverter_temp_c": ("Inverter temperature", "Température onduleur"),
    "mppt_temp_c": ("Solar charger temperature", "Température chargeur solaire"),
    "pcs_dc_temp_c": ("PCS DC temperature", "Température PCS DC"),
    "pcs_ac_temp_c": ("PCS AC temperature", "Température PCS AC"),
    "mppt_lv_temp_c": (
        "Solar charger temperature (low voltage)",
        "Température chargeur solaire (basse tension)",
    ),
    "mppt_hv_temp_c": (
        "Solar charger temperature (high voltage)",
        "Température chargeur solaire (haute tension)",
    ),
    "pd_temp_c": ("Power distribution temperature", "Température distribution"),
    "fan_level": ("Fan level", "Niveau ventilateur"),
    "pd_error_code": ("Power distribution error code", "Code erreur distribution"),
    "inverter_error_code": ("Inverter error code", "Code erreur onduleur"),
    "mppt_error_code": ("Solar charger error code", "Code erreur chargeur solaire"),
    "bms_error_code": ("BMS error code", "Code erreur BMS"),
    "system_error_code": ("System error code", "Code erreur système"),
    "input_energy_kwh": ("Total input energy", "Énergie entrée totale"),
    "output_energy_kwh": ("Total output energy", "Énergie sortie totale"),
    "ac_in_energy_kwh": ("AC input energy", "Énergie entrée AC"),
    "ac_out_energy_kwh": ("AC output energy", "Énergie sortie AC"),
    "solar_in_energy_kwh": ("Solar energy", "Énergie solaire"),
    "battery_charge_energy_kwh": ("Battery charge energy", "Énergie chargée batterie"),
    "battery_discharge_energy_kwh": ("Battery discharge energy", "Énergie déchargée batterie"),
    "ac_in_energy_lifetime_kwh": (
        "AC input energy (device counter)",
        "Énergie entrée AC (compteur appareil)",
    ),
    "ac_out_energy_lifetime_kwh": (
        "AC output energy (device counter)",
        "Énergie sortie AC (compteur appareil)",
    ),
    "solar_in_energy_lifetime_kwh": (
        "Solar energy (device counter)",
        "Énergie solaire (compteur appareil)",
    ),
    "dc12v_out_energy_lifetime_kwh": (
        "12 V output energy (device counter)",
        "Énergie sortie 12 V (compteur appareil)",
    ),
    "usb_c_out_energy_lifetime_kwh": (
        "USB-C output energy (device counter)",
        "Énergie sortie USB-C (compteur appareil)",
    ),
    "usb_a_out_energy_lifetime_kwh": (
        "USB-A output energy (device counter)",
        "Énergie sortie USB-A (compteur appareil)",
    ),
    "battery_charge_energy_lifetime_kwh": (
        "Battery charge energy (BMS counter)",
        "Énergie chargée (compteur BMS)",
    ),
    "battery_discharge_energy_lifetime_kwh": (
        "Battery discharge energy (BMS counter)",
        "Énergie déchargée (compteur BMS)",
    ),
}

EXTRA = {
    "soc": ("Extra battery {index} state of charge", "Batterie supp. {index} niveau de charge"),
    "soh": ("Extra battery {index} state of health", "Batterie supp. {index} état de santé"),
    "cycles": ("Extra battery {index} cycles", "Batterie supp. {index} cycles"),
    "temp_c": ("Extra battery {index} temperature", "Batterie supp. {index} température"),
    "voltage_v": ("Extra battery {index} voltage", "Batterie supp. {index} tension"),
    "current_a": ("Extra battery {index} current", "Batterie supp. {index} courant"),
    "in_power_w": ("Extra battery {index} input power", "Batterie supp. {index} puissance entrée"),
    "out_power_w": (
        "Extra battery {index} output power",
        "Batterie supp. {index} puissance sortie",
    ),
    "power_w": ("Extra battery {index} power", "Batterie supp. {index} puissance"),
    "remain_capacity_mah": (
        "Extra battery {index} remaining capacity",
        "Batterie supp. {index} capacité restante",
    ),
    "full_capacity_mah": (
        "Extra battery {index} full capacity",
        "Batterie supp. {index} capacité pleine charge",
    ),
    "design_capacity_mah": (
        "Extra battery {index} design capacity",
        "Batterie supp. {index} capacité nominale",
    ),
    "max_cell_temp_c": (
        "Extra battery {index} max cell temperature",
        "Batterie supp. {index} température cellule max",
    ),
    "min_cell_temp_c": (
        "Extra battery {index} min cell temperature",
        "Batterie supp. {index} température cellule min",
    ),
    "max_cell_voltage_v": (
        "Extra battery {index} max cell voltage",
        "Batterie supp. {index} tension cellule max",
    ),
    "min_cell_voltage_v": (
        "Extra battery {index} min cell voltage",
        "Batterie supp. {index} tension cellule min",
    ),
    "error_code": ("Extra battery {index} error code", "Batterie supp. {index} code erreur"),
    "battery_charge_energy_lifetime_kwh": (
        "Extra battery {index} charge energy (BMS counter)",
        "Batterie supp. {index} énergie chargée (compteur BMS)",
    ),
    "battery_discharge_energy_lifetime_kwh": (
        "Extra battery {index} discharge energy (BMS counter)",
        "Batterie supp. {index} énergie déchargée (compteur BMS)",
    ),
}

PACK = {
    "soc": ("Battery pack {index} state of charge", "Pack batterie {index} niveau de charge"),
    "power_w": ("Battery pack {index} power", "Pack batterie {index} puissance"),
    "remain_energy_wh": (
        "Battery pack {index} remaining energy",
        "Pack batterie {index} énergie restante",
    ),
    "temp_c": ("Battery pack {index} temperature", "Pack batterie {index} température"),
    "remaining_time_min": (
        "Battery pack {index} remaining time",
        "Pack batterie {index} temps restant",
    ),
    "chg_dsg_state": ("Battery pack {index} state", "Pack batterie {index} état"),
}

BINARY = {
    "online": ("Online", "En ligne"),
    "ac_out_enabled": ("AC output", "Sortie AC"),
    "dc12v_out_enabled": ("12 V output", "Sortie 12 V"),
    "usb_out_enabled": ("USB output", "Sortie USB"),
    "xboost_enabled": ("X-Boost", "X-Boost"),
    "backup_reserve_enabled": ("Backup reserve", "Réserve de secours"),
    "ac_in_connected": ("AC input connected", "Entrée AC branchée"),
    "ac_always_on_enabled": ("AC always on", "AC toujours actif"),
    "solar_only_enabled": ("Solar only charging", "Charge solaire uniquement"),
}


def build(lang: int, code: str) -> dict:
    sensors: dict[str, dict] = {}
    for key, names in SENSOR.items():
        sensors[key] = {"name": names[lang]}
    for key, names in EXTRA.items():
        sensors[f"extra_{key}"] = {"name": names[lang]}
    for key, names in PACK.items():
        sensors[f"pack_{key}"] = {"name": names[lang]}
    for key in ("chg_dsg_state", "pack_chg_dsg_state"):
        sensors[key]["state"] = STATE[code]
    return {
        "config": CONFIG[code],
        "options": OPTIONS[code],
        "entity": {
            "sensor": sensors,
            "binary_sensor": {k: {"name": v[lang]} for k, v in BINARY.items()},
        },
    }


def main() -> None:
    en = build(0, "en")
    fr = build(1, "fr")
    (ROOT / "translations").mkdir(exist_ok=True)
    for path, data in (
        (ROOT / "strings.json", en),
        (ROOT / "translations" / "en.json", en),
        (ROOT / "translations" / "fr.json", fr),
    ):
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
