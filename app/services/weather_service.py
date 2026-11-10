from datetime import date
from app.integrations.weather.base import WeatherProvider
from app.integrations.weather.schemas import WeatherData


class WeatherService:
    def __init__(self, provider: WeatherProvider):
        self.provider = provider

    async def get_weather(self, day: date) -> WeatherData:
        return await self.provider.get_weather(day)
