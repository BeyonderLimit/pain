"""Weather via open-meteo (Phase 4: robust parsing + location timezone)."""

from __future__ import annotations

import aiohttp

from config import WEATHER_API_URL, Location


async def get_weather(location: Location) -> str:
    """Return a one-line weather summary for ``location`` (open-meteo)."""
    url = (
        f"{WEATHER_API_URL}?latitude={location.latitude}"
        f"&longitude={location.longitude}&current_weather=true"
        f"&timezone={location.timezone}"
    )
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                response.raise_for_status()
                data = await response.json()
    except aiohttp.ClientError as e:
        return f"Error fetching weather data: {e}"
    except Exception as e:
        return f"An unexpected error occurred: {e}"

    weather = data.get("current_weather")
    if not weather:
        return "Could not retrieve weather information."

    temp_celsius = weather.get("temperature")
    if temp_celsius is None:
        return "Could not retrieve temperature information."
    temp_fahrenheit = (temp_celsius * 9 / 5) + 32

    weather_code = weather.get("weathercode", "unknown")
    weather_descriptions = {
        0: "Clear sky",
        1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
        45: "Fog", 48: "Depositing rime fog",
        51: "Light drizzle", 53: "Moderate drizzle", 55: "Dense drizzle",
        61: "Slight rain", 63: "Moderate rain", 65: "Heavy rain",
        71: "Slight snow fall", 73: "Moderate snow fall", 75: "Heavy snow fall",
        77: "Snow grains",
        80: "Slight rain showers", 81: "Moderate rain showers", 82: "Violent rain showers",
        85: "Slight snow showers", 86: "Heavy snow showers",
        95: "Thunderstorm", 96: "Thunderstorm with slight hail", 99: "Thunderstorm with heavy hail",
    }
    weather_description = weather_descriptions.get(weather_code, "Unknown weather condition")
    return (
        f"The current weather in {location.name} is {weather_description} "
        f"with a temperature of {temp_fahrenheit:.1f}°F."
    )
