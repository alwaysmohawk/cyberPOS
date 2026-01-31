"""Weather fetching for cyberPOS dispatch receipts.
Uses Open-Meteo (free, no API key needed). Location: Toronto.
"""

import urllib.request
import json

WEATHER_CODES = {
    0: "Clear Sky",         1: "Mainly Clear",     2: "Partly Cloudy",
    3: "Overcast",          45: "Foggy",            48: "Rime Fog",
    51: "Light Drizzle",    53: "Drizzle",          55: "Dense Drizzle",
    61: "Slight Rain",      63: "Moderate Rain",    65: "Heavy Rain",
    71: "Slight Snow",      73: "Moderate Snow",    75: "Heavy Snow",
    77: "Snow Grains",      80: "Slight Showers",   81: "Mod. Showers",
    82: "Violent Showers",  85: "Snow Showers",     86: "Heavy Snow Showers",
    95: "Thunderstorm",     96: "T-Storm + Hail",   99: "T-Storm + Heavy Hail",
}

def wind_dir(degrees):
    dirs = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
    return dirs[round(degrees / 45) % 8]

def get_weather():
    """Fetch Toronto current weather from Open-Meteo"""
    url = (
        "https://api.open-meteo.com/v1/forecast"
        "?latitude=43.6532&longitude=-79.3832"
        "&current_weather=true"
        "&hourly=temperature_2m,precipitation_probability"
        "&timezone=America/Toronto"
        "&forecast_days=1"
    )
    try:
        with urllib.request.urlopen(url, timeout=5) as resp:
            data = json.loads(resp.read())

        current = data['current_weather']
        hourly = data['hourly']
        temps = hourly['temperature_2m']
        precip = max(hourly['precipitation_probability'])

        return {
            'condition': WEATHER_CODES.get(current['weathercode'], 'Unknown'),
            'temp': round(current['temperature']),
            'temp_high': round(max(temps)),
            'temp_low': round(min(temps)),
            'wind_speed': int(current['windspeed']),
            'wind_dir': wind_dir(current['winddirection']),
            'precip': round(precip),
        }
    except Exception as e:
        print(f"Warning: Weather fetch failed ({e})")
        return None

def get_tomorrow_weather():
    """Fetch tomorrow's Toronto weather forecast from Open-Meteo daily summary"""
    url = (
        "https://api.open-meteo.com/v1/forecast"
        "?latitude=43.6532&longitude=-79.3832"
        "&daily=temperature_2m_max,temperature_2m_min"
        ",precipitation_probability_max,weathercode"
        ",windspeed_10m_max,winddirection_10m_dominant"
        "&timezone=America/Toronto"
        "&forecast_days=2"
    )
    try:
        with urllib.request.urlopen(url, timeout=5) as resp:
            data = json.loads(resp.read())

        daily = data['daily']

        return {
            'condition': WEATHER_CODES.get(daily['weathercode'][1], 'Unknown'),
            'temp_high': round(daily['temperature_2m_max'][1]),
            'temp_low': round(daily['temperature_2m_min'][1]),
            'wind_speed': int(daily['windspeed_10m_max'][1]),
            'wind_dir': wind_dir(daily['winddirection_10m_dominant'][1]),
            'precip': round(daily['precipitation_probability_max'][1]),
        }
    except Exception as e:
        print(f"Warning: Tomorrow weather fetch failed ({e})")
        return None
