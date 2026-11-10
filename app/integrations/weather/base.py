from datetime import date
from typing import Protocol
from app.integrations.weather.schemas import WeatherData


class WeatherProvider(Protocol):
    async def get_weather(self, day: date) -> WeatherData: ...
