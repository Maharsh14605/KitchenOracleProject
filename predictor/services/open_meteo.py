from __future__ import annotations
import math
import requests
from datetime import date, timedelta
from typing import Dict, List, Optional
from django.conf import settings
from django.db import transaction
from predictor.models import Weather

FORECAST_BASE = "https://api.open-meteo.com/v1/forecast"
ARCHIVE_BASE  = "https://archive-api.open-meteo.com/v1/archive"
M_PER_MILE = 1609.344

# How we split past vs future:
#  - archive: any day strictly earlier than today
#  - forecast: today and up to ~16 days ahead (Open-Meteo limit)
def _choose_base(start: date, end: date) -> str:
    today = date.today()
    if end < today:
        return ARCHIVE_BASE
    return FORECAST_BASE

def _common_params(start: date, end: date) -> dict:
    return {
        "latitude": settings.OPENMETEO["LAT"],
        "longitude": settings.OPENMETEO["LON"],
        "timezone": settings.OPENMETEO["TIMEZONE"],
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        # daily aggregates (units depend on below unit params)
        "daily": ",".join([
            "temperature_2m_max",
            "temperature_2m_min",
            "uv_index_max",
            "precipitation_sum",
            "snowfall_sum",
        ]),
        # hourlies we daily-average
        "hourly": ",".join([
            "pressure_msl",
            "visibility",
            "cloudcover",
            "windspeed_10m",
            "temperature_2m",
        ]),
        # units per your CSV / model
        "temperature_unit": settings.OPENMETEO.get("TEMPERATURE_UNIT", "fahrenheit"),
        "wind_speed_unit": settings.OPENMETEO.get("WIND_SPEED_UNIT", "mph"),
        "precipitation_unit": settings.OPENMETEO.get("PRECIPITATION_UNIT", "inch"),
    }

def _daily_series(data: dict, key: str) -> Dict[str, Optional[float]]:
    days = data.get("daily", {}).get("time", [])
    vals = data.get("daily", {}).get(key, [])
    return {d: v for d, v in zip(days, vals)}

def _hourly_to_daily_mean(data: dict, key: str) -> Dict[str, Optional[float]]:
    times: List[str] = data.get("hourly", {}).get("time", [])
    vals:  List[Optional[float]] = data.get("hourly", {}).get(key, [])
    by_day: Dict[str, List[float]] = {}
    for t, v in zip(times, vals):
        d = t[:10]
        if v is not None and not (isinstance(v, float) and math.isnan(v)):
            by_day.setdefault(d, []).append(float(v))
        else:
            by_day.setdefault(d, [])
    out: Dict[str, Optional[float]] = {}
    for d, arr in by_day.items():
        out[d] = (sum(arr)/len(arr)) if arr else None
    return out

def _num(x: Optional[float], fallback: float = 0.0) -> float:
    try:
        if x is None:
            return float(fallback)
        if isinstance(x, float) and math.isnan(x):
            return float(fallback)
        return float(x)
    except Exception:
        return float(fallback)

def fetch_and_store(start: date, end: date) -> int:
    """
    Fetch weather for [start, end] using the correct Open-Meteo endpoint
    (archive for past, forecast for present/future), and upsert Weather rows.
    """
    base = _choose_base(start, end)
    params = _common_params(start, end)

    r = requests.get(base, params=params, timeout=20)
    try:
        r.raise_for_status()
    except requests.HTTPError as e:
        # Show helpful info (like allowed range error)
        raise RuntimeError(f"Open-Meteo {r.status_code}: {r.text[:400]}") from e

    data = r.json()
    days = data.get("daily", {}).get("time", [])
    bucket: Dict[str, Dict[str, Optional[float]]] = {d: {} for d in days}

    # daily -> model fields
    daily_map = {
        "temperature_2m_max": "tempmax",     # °F
        "temperature_2m_min": "tempmin",     # °F
        "uv_index_max":       "uvindex",
        "precipitation_sum":  "precip",      # inches
        "snowfall_sum":       "snow",        # inches
    }
    for om_key, model_field in daily_map.items():
        series = _daily_series(data, om_key)
        for d, v in series.items():
            bucket.setdefault(d, {})[model_field] = v

    # hourly -> means -> model fields
    hourly_means = {
        "sealevelpressure": _hourly_to_daily_mean(data, "pressure_msl"),   # hPa
        "visibility_m":     _hourly_to_daily_mean(data, "visibility"),     # meters
        "cloudcover":       _hourly_to_daily_mean(data, "cloudcover"),     # %
        "windspeed":        _hourly_to_daily_mean(data, "windspeed_10m"),  # mph
        "temp":             _hourly_to_daily_mean(data, "temperature_2m"), # °F
    }
    for d in days:
        for field, series in hourly_means.items():
            bucket.setdefault(d, {})[field] = series.get(d)

    saved = 0
    with transaction.atomic():
        for d, fields in bucket.items():
            if not fields:
                continue

            # meters -> miles
            vis_m = fields.get("visibility_m")
            vis_miles = (vis_m / M_PER_MILE) if (vis_m is not None and not (isinstance(vis_m, float) and math.isnan(vis_m))) else None

            defaults = {
                "tempmax":          _num(fields.get("tempmax")),
                "tempmin":          _num(fields.get("tempmin")),
                "temp":             _num(fields.get("temp")),
                "precip":           _num(fields.get("precip")),
                "snow":             _num(fields.get("snow")),
                "windspeed":        _num(fields.get("windspeed")),
                "sealevelpressure": _num(fields.get("sealevelpressure")),
                "cloudcover":       _num(fields.get("cloudcover")),
                "visibility":       _num(vis_miles),
                "uvindex":          _num(fields.get("uvindex")),
                # required strings on your model
                "conditions":  "Forecast" if _choose_base(date.fromisoformat(d), date.fromisoformat(d)) == FORECAST_BASE else "Historical",
                "description": "Weather from Open-Meteo",
                "icon":        "forecast",
            }
            Weather.objects.update_or_create(datetime=d, defaults=defaults)
            saved += 1
    return saved
