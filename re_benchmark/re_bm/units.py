"""단위 표준화: 전력=MWh, 비율=%, 배출량=tCO2e."""

_ENERGY_TO_MWH = {
    "kwh": 1e-3, "mwh": 1.0, "gwh": 1e3, "twh": 1e6,
    "gj": 1 / 3.6, "tj": 1e3 / 3.6, "pj": 1e6 / 3.6,
    "millionkwh": 1e3, "billionkwh": 1e6, "천kwh": 1.0, "백만kwh": 1e3, "억kwh": 1e5,
}
# "MtCO2e"/"MTCO2e" 는 회사마다 백만톤/메트릭톤으로 뜻이 달라 자동 환산하지 않는다 (검토 대상).
_EMISSION_TO_T = {"tco2e": 1.0, "ktco2e": 1e3, "천tco2e": 1e3, "만tco2e": 1e4, "백만tco2e": 1e6,
                 "metrictonsco2e": 1.0, "metrictonco2e": 1.0, "millionmetrictonsco2e": 1e6, "thousandmetrictonsco2e": 1e3}


def _key(unit: str) -> str:
    return unit.lower().replace(" ", "").replace("-", "").replace("₂", "2").replace("co2eq", "co2e")


def standardize(metric: str, value: float, unit: str) -> float | None:
    """환산 불가하면 None 을 돌려 사람이 검토하게 한다 (추측 환산 금지)."""
    k = _key(unit)
    if metric == "re_ratio":
        return value if k in ("%", "percent", "pct") else None
    if metric in ("total_electricity", "re_electricity"):
        f = _ENERGY_TO_MWH.get(k)
        return value * f if f is not None else None
    if metric.startswith("scope2"):
        f = _EMISSION_TO_T.get(k)
        return value * f if f is not None else None
    return None
