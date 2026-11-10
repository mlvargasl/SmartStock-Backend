from datetime import date as Date
from pydantic import BaseModel, ConfigDict, Field


class WeatherData(BaseModel):
    date: Date = Field(examples=["2026-11-10"])
    temperature: float = Field(
        description="Temperatura media diaria en °C", examples=[21.5]
    )
    min_temperature: float | None = Field(
        default=None, description="Mínima diaria en °C"
    )
    max_temperature: float | None = Field(
        default=None, description="Máxima diaria en °C"
    )
    precipitation: float = Field(ge=0, description="Precipitación diaria en mm")
    precipitation_probability: float | None = Field(
        default=None,
        ge=0,
        le=100,
        description="Probabilidad máxima diaria en porcentaje",
    )
    weather_condition: str | None = None
    source: str
    model_config = ConfigDict(
        allow_inf_nan=False,
        json_schema_extra={
            "example": {
                "date": "2026-11-10",
                "temperature": 21.5,
                "min_temperature": 14.0,
                "max_temperature": 25.0,
                "precipitation": 0.0,
                "precipitation_probability": 10,
                "weather_condition": "clear",
                "source": "Open-Meteo",
            }
        },
    )
