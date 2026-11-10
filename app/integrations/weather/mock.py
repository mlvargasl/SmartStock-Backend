from datetime import date
from app.integrations.weather.schemas import WeatherData


class MockWeatherProvider:
    async def get_weather(self, day: date) -> WeatherData:
        return WeatherData(
            date=day,
            temperature=20.0,
            min_temperature=14.0,
            max_temperature=25.0,
            precipitation=0.0,
            precipitation_probability=10.0,
            weather_condition="clear",
            source="mock-weather",
        )
