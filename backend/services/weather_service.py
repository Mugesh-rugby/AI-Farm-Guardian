import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

try:
    from config import OPENWEATHER_API_KEY
except ImportError:
    from backend.config import OPENWEATHER_API_KEY

logger = logging.getLogger(__name__)
_CACHE_SECONDS = 600
_weather_cache: dict[tuple[float, float], tuple[float, dict[str, Any]]] = {}


def _advisories(current: dict[str, Any], forecast: list[dict[str, Any]]) -> list[str]:
    messages = []
    next_rain = next(
        (item["rain_probability"] for item in forecast if item.get("rain_probability") is not None),
        None,
    )
    if next_rain is not None and next_rain >= 50:
        messages.append(f"Forecast rain probability is {next_rain:.0f}%; review planned field applications.")
    if current["humidity"] >= 80:
        messages.append("Relative humidity is high; scout susceptible crops and check local disease guidance.")
    if current["wind_speed_kmh"] >= 20:
        messages.append("Wind is elevated; check product labels and local conditions before spraying.")
    return messages


async def get_weather(
    lat: float,
    lon: float,
    force_refresh: bool = False,
) -> dict[str, Any] | None:
    if not OPENWEATHER_API_KEY:
        return None
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        raise ValueError("Latitude or longitude is outside the valid range.")

    cache_key = (round(lat, 4), round(lon, 4))
    cached = _weather_cache.get(cache_key)
    now = time.monotonic()
    if not force_refresh and cached and now - cached[0] < _CACHE_SECONDS:
        return cached[1]

    params = {"lat": lat, "lon": lon, "appid": OPENWEATHER_API_KEY, "units": "metric"}
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            current_response = await client.get(
                "https://api.openweathermap.org/data/2.5/weather", params=params
            )
            current_response.raise_for_status()
            current_payload = current_response.json()

            forecast_response = await client.get(
                "https://api.openweathermap.org/data/2.5/forecast", params=params
            )
            forecast_response.raise_for_status()
            forecast_payload = forecast_response.json()
    except httpx.HTTPError as error:
        status_code = getattr(getattr(error, "response", None), "status_code", None)
        logger.warning("OpenWeather request failed (HTTP %s).", status_code or "network error")
        return None
    except (KeyError, TypeError, ValueError):
        logger.warning("OpenWeather returned an invalid response.")
        return None

    main = current_payload.get("main", {})
    wind = current_payload.get("wind", {})
    conditions = current_payload.get("weather") or [{}]
    if not all(key in main for key in ("temp", "feels_like", "humidity")):
        logger.warning("OpenWeather response is missing current weather fields.")
        return None

    timezone_offset = current_payload.get(
        "timezone", (forecast_payload.get("city") or {}).get("timezone", 0)
    )
    daily_forecasts: dict[str, tuple[float, dict[str, Any]]] = {}
    for entry in forecast_payload.get("list", []):
        values = entry.get("main", {})
        forecast_time = entry.get("dt_txt")
        if "temp" not in values or not forecast_time:
            continue

        try:
            utc_time = datetime.strptime(forecast_time, "%Y-%m-%d %H:%M:%S").replace(
                tzinfo=timezone.utc
            )
        except ValueError:
            continue
        local_time = utc_time + timedelta(seconds=timezone_offset)
        local_date = local_time.date().isoformat()
        distance_from_noon = abs(
            local_time.hour * 60 + local_time.minute - 12 * 60
        )
        item = {
                "time": forecast_time,
                "temperature": values["temp"],
                "humidity": values.get("humidity"),
                "rain_probability": (
                    entry["pop"] * 100 if entry.get("pop") is not None else None
                ),
            }
        selected = daily_forecasts.get(local_date)
        if selected is None or distance_from_noon < selected[0]:
            daily_forecasts[local_date] = (distance_from_noon, item)
    forecast = [daily_forecasts[day][1] for day in sorted(daily_forecasts)]

    rain = current_payload.get("rain") or {}
    first_condition = conditions[0]
    current = {
        "temperature": main["temp"],
        "feels_like": main["feels_like"],
        "humidity": main["humidity"],
        "wind_speed": wind.get("speed"),
        "wind_speed_kmh": (
            round(wind["speed"] * 3.6, 1) if wind.get("speed") is not None else None
        ),
        "rainfall_mm": rain.get("1h"),
        "condition": first_condition.get("description", "Unavailable").title(),
        "description": first_condition.get("description", "Unavailable").title(),
        "icon": first_condition.get("icon"),
        "location_name": current_payload.get("name"),
        "timezone_offset": timezone_offset,
        "rain_probability": forecast[0]["rain_probability"] if forecast else None,
        "forecast": forecast,
        "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "source": "OpenWeather",
    }
    current["advisories"] = _advisories(current, forecast)
    _weather_cache[cache_key] = (now, current)
    return current


class WeatherIntelligenceService:
    async def get_weather_data(
        self,
        lat: float,
        lon: float,
        force_refresh: bool = False,
    ) -> dict[str, Any] | None:
        return await get_weather(lat, lon, force_refresh=force_refresh)


weather_service = WeatherIntelligenceService()
