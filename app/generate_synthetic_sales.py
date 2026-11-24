"""Generate clearly labeled, repeatable sales data for local demonstrations."""

import argparse
import math
import random
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.database import SessionLocal
from app.models import (
    CalendarObservation,
    Product,
    Sale,
    SaleTransaction,
    WeatherObservation,
)


def synthetic_weather(day: date, seed: int) -> dict:
    """A deterministic Santiago-like daily weather sample for demonstrations."""
    rng = random.Random(seed + day.toordinal())
    annual_phase = 2 * math.pi * (day.timetuple().tm_yday - 30) / 365
    mean_temp = 18 + 7 * math.sin(annual_phase)
    rainy_season = day.month in (5, 6, 7, 8)
    rainy = rng.random() < (0.30 if rainy_season else 0.06)
    precipitation = round(rng.uniform(1.0, 12.0), 1) if rainy else 0.0
    return {
        "temperature_max_c": round(mean_temp + 6 + rng.uniform(-2, 2), 1),
        "temperature_min_c": round(mean_temp - 6 + rng.uniform(-2, 2), 1),
        "precipitation_mm": precipitation,
        "precipitation_probability_percent": 75.0 if rainy else 5.0,
        "weather_code": 61 if rainy else 0,
    }


def synthetic_calendar(day: date) -> dict:
    """Small Chile-focused calendar sample for demo dates without imported events."""
    holidays = {
        (1, 1), (5, 1), (5, 21), (8, 15), (9, 18),
        (9, 19), (10, 12), (11, 1), (12, 8), (12, 25),
    }
    first_sunday_may = 1 + (6 - date(day.year, 5, 1).weekday()) % 7
    first_sunday_june = 1 + (6 - date(day.year, 6, 1).weekday()) % 7
    festive_dates = {
        (2, 14),
        (5, first_sunday_may + 7),  # Mother's Day
        (6, first_sunday_june + 14),  # Father's Day
        (10, 31),
    }
    return {
        "is_holiday": (day.month, day.day) in holidays,
        "is_festivity": (day.month, day.day) in festive_dates,
    }


def units_for_day(
    day: date, product_index: int, weather: dict, calendar: dict, seed: int
) -> int:
    """Demo-only demand includes weekday, weather, holiday and festivity signals."""
    rng = random.Random(seed + day.toordinal() * 37 + product_index)
    weekday_factor = (0.72, 0.82, 0.92, 1.0, 1.22, 1.55, 1.35)[day.weekday()]
    seasonal_factor = 1 + 0.12 * math.sin(
        2 * math.pi * (day.timetuple().tm_yday - 30) / 365
    )
    product_base = 5.5 + product_index * 1.4
    temp_delta = (weather["temperature_max_c"] - 20) / 10
    product_temp_effect = temp_delta * (0.13 if product_index % 2 else -0.10)
    rain_effect = -0.035 * weather["precipitation_mm"]
    calendar_factor = (
        1.35 if calendar["is_holiday"] else 1.2 if calendar["is_festivity"] else 1.0
    )
    weather_factor = max(0.45, (1 + product_temp_effect + rain_effect) * calendar_factor)
    amount = rng.gauss(
        product_base * weekday_factor * seasonal_factor * weather_factor, 1.6
    )
    return max(1, round(amount))


def generate(days: int = 365, seed: int = 2026) -> tuple[int, int, int, int]:
    if days < 1 or days > 3650:
        raise ValueError("days debe estar entre 1 y 3650")

    today = date.today()
    first_day = today - timedelta(days=days - 1)
    rng = random.Random(seed)
    added_transactions = 0
    updated_transactions = 0
    total_units = 0
    stored_weather_days = 0

    with SessionLocal() as db:
        products = list(
            db.scalars(select(Product).where(Product.active.is_(True)).order_by(Product.id))
        )
        if not products:
            raise RuntimeError("No hay productos activos; ejecuta primero python -m app.seed")

        # Re-read the rows with their line items so older demo data can be refreshed.
        existing_rows = {
            transaction.external_id: transaction
            for transaction in db.scalars(
                select(SaleTransaction)
                .options(selectinload(SaleTransaction.items))
                .where(
                    SaleTransaction.source == "SYNTHETIC",
                    SaleTransaction.sale_date >= first_day,
                    SaleTransaction.sale_date <= today,
                )
            )
        }
        weather_by_date = {
            observation.observation_date: observation
            for observation in db.scalars(
                select(WeatherObservation).where(
                    WeatherObservation.observation_date >= first_day,
                    WeatherObservation.observation_date <= today,
                )
            )
        }
        calendar_by_date = {
            observation.observation_date: observation
            for observation in db.scalars(
                select(CalendarObservation).where(
                    CalendarObservation.observation_date >= first_day,
                    CalendarObservation.observation_date <= today,
                )
            )
        }

        day = first_day
        while day <= today:
            generated_weather = synthetic_weather(day, seed)
            observation = weather_by_date.get(day)
            if observation is None:
                observation = WeatherObservation(
                    observation_date=day, source="SYNTHETIC", **generated_weather
                )
                db.add(observation)
                stored_weather_days += 1
            elif observation.source == "SYNTHETIC":
                for field, value in generated_weather.items():
                    setattr(observation, field, value)
                stored_weather_days += 1
            weather = {
                "temperature_max_c": float(observation.temperature_max_c or 0),
                "temperature_min_c": float(observation.temperature_min_c or 0),
                "precipitation_mm": float(observation.precipitation_mm),
            }

            synthetic_events = synthetic_calendar(day)
            calendar_observation = calendar_by_date.get(day)
            if calendar_observation is None:
                calendar_observation = CalendarObservation(
                    observation_date=day,
                    source="SYNTHETIC",
                    **synthetic_events,
                )
                db.add(calendar_observation)
            elif calendar_observation.source == "SYNTHETIC":
                calendar_observation.is_holiday = synthetic_events["is_holiday"]
                calendar_observation.is_festivity = synthetic_events["is_festivity"]
            calendar = {
                "is_holiday": calendar_observation.is_holiday,
                "is_festivity": calendar_observation.is_festivity,
            }

            for index, product in enumerate(products):
                external_id = f"synthetic-v1-{day.isoformat()}-product-{product.id}"
                quantity = units_for_day(day, index, weather, calendar, seed)
                transaction = existing_rows.get(external_id)
                if quantity:
                    if transaction is None:
                        transaction = SaleTransaction(
                            source="SYNTHETIC",
                            external_id=external_id,
                            sale_date=day,
                            items=[
                                Sale(
                                    product_id=product.id,
                                    quantity=quantity,
                                    sale_date=day,
                                )
                            ],
                        )
                        db.add(transaction)
                        added_transactions += 1
                    else:
                        transaction.items[0].quantity = quantity
                        updated_transactions += 1
                    total_units += quantity
            day += timedelta(days=1)
        db.commit()

    return added_transactions, updated_transactions, total_units, stored_weather_days


def main():
    parser = argparse.ArgumentParser(
        description="Crea ventas sintéticas marcadas como SYNTHETIC para desarrollo."
    )
    parser.add_argument("--days", type=int, default=365, help="Días a generar (1-3650).")
    parser.add_argument("--seed", type=int, default=2026, help="Semilla aleatoria reproducible.")
    args = parser.parse_args()

    added, updated, units, weather_days = generate(days=args.days, seed=args.seed)
    print(
        f"Ventas sintéticas: {added} transacciones nuevas, {updated} actualizadas, "
        f"{units} unidades y {weather_days} días climáticos preparados."
    )


if __name__ == "__main__":
    main()
