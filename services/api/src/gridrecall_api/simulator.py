from gridrecall_api.schemas import IncidentContext, Site, Telemetry


def seed_sites() -> list[Site]:
    return [
        Site(
            name="Ajegunle Mini-Grid",
            community="Ajegunle, Lagos",
            capacity_kw=85,
            inverter_model="SMA-STP-50",
        ),
        Site(
            name="Kura Mini-Grid",
            community="Kura, Kano",
            capacity_kw=120,
            inverter_model="SMA-STP-50",
        ),
        Site(
            name="Igbeti Mini-Grid",
            community="Igbeti, Oyo",
            capacity_kw=70,
            inverter_model="Huawei-SUN2000",
        ),
    ]


def overheating_context(site: Site, variation: float = 0) -> IncidentContext:
    return IncidentContext(
        site_id=site.id,
        site_name=site.name,
        inverter_model=site.inverter_model,
        fault_type="inverter_overheating_output_derating",
        symptoms=[
            "inverter temperature rising",
            "power output falling",
            "solar irradiance normal",
            "battery condition normal",
        ],
        telemetry=Telemetry(
            inverter_temperature_c=78.4 + variation,
            power_output_kw=31.8 - variation,
            solar_irradiance_w_m2=812 + variation,
            battery_state_of_charge_pct=74,
            ambient_temperature_c=34.2,
            load_demand_kw=49.5,
            alarms=["THERMAL_DERATING", "FAN_AIRFLOW_LOW"],
        ),
    )
