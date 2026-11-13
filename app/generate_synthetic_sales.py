"""Generate clearly labeled, repeatable sales data for local demonstrations."""

import argparse
import math
import random
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.database import SessionLocal
from app.models import Product, Sale, SaleTransaction, WeatherObservation


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


def units_for_day(
    day: date, product_index: int, weather: dict, seed: int
) -> int:
    """A demo-only pattern with weekday, season, temperature and rain effects."""
    rng = random.Random(seed + day.toordinal() * 37 + product_index)
    weekday_factor = (0.72, 0.82, 0.92, 1.0, 1.22, 1.55, 1.35)[day.weekday()]
    seasonal_factor = 1 + 0.12 * math.sin(
        2 * math.pi * (day.timetuple().tm_yday - 30) / 365
    )
    product_base = 5.5 + product_index * 1.4
    temp_delta = (weather["temperature_max_c"] - 20) / 10
    product_temp_effect = temp_delta * (0.13 if product_index % 2 else -0.10)
    rain_effect = -0.035 * weather["precipitation_mm"]
    weather_factor = max(0.45, 1 + product_temp_effect + rain_effect)
    amount = rng.gauss(
        product_base * weekday_factor * seasonal_factor * weather_factor, 1.6
    )
    return max(1, round(amount))


def generate(days: int = 365, seed: int = 2026) -> tuple[int, int]:
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

        day = first_day
        while day <= today:
            weather = synthetic_weather(day, seed)
            observation = weather_by_date.get(day)
            if observation is None:
                observation = WeatherObservation(
                    observation_date=day, source="SYNTHETIC", **weather
                )
                db.add(observation)
                stored_weather_days += 1
            elif observation.source == "SYNTHETIC":
                for field, value in weather.items():
                    setattr(observation, field, value)
                stored_weather_days += 1

            for index, product in enumerate(products):
                external_id = f"synthetic-v1-{day.isoformat()}-product-{product.id}"
                quantity = units_for_day(day, index, weather, seed)
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
