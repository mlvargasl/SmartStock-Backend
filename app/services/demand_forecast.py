"""Small, interpretable demand model trained from daily sales and weather."""

from collections import Counter, defaultdict
from datetime import date
from math import cos, pi, sin, sqrt

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Product, Sale, SaleTransaction, WeatherObservation


MIN_TRAINING_DAYS = 30


def _weather_features(day: date, weather: dict) -> list[float]:
    annual_phase = 2 * pi * (day.timetuple().tm_yday - 1) / 365.25
    return [
        float(day.weekday() == weekday) for weekday in range(1, 7)
    ] + [
        sin(annual_phase),
        cos(annual_phase),
        weather["temperature_max_c"],
        weather["temperature_min_c"],
        weather["precipitation_mm"],
        weather["precipitation_probability_percent"],
    ]


def _solve(matrix: list[list[float]], vector: list[float]) -> list[float]:
    """Solve a small square system with pivoted Gaussian elimination."""
    size = len(vector)
    augmented = [row[:] + [value] for row, value in zip(matrix, vector)]
    for column in range(size):
        pivot = max(range(column, size), key=lambda row: abs(augmented[row][column]))
        if abs(augmented[pivot][column]) < 1e-12:
            raise ValueError("Singular regression matrix")
        augmented[column], augmented[pivot] = augmented[pivot], augmented[column]
        divisor = augmented[column][column]
        augmented[column] = [value / divisor for value in augmented[column]]
        for row in range(size):
            if row == column:
                continue
            factor = augmented[row][column]
            if factor:
                augmented[row] = [
                    left - factor * right
                    for left, right in zip(augmented[row], augmented[column])
                ]
    return [augmented[row][-1] for row in range(size)]


def _fit_predict(rows: list[tuple[date, dict, int]], target_day: date, target_weather: dict):
    raw_features = [_weather_features(day, weather) for day, weather, _ in rows]
    target_raw = _weather_features(target_day, target_weather)
    feature_count = len(target_raw)

    means = [sum(row[index] for row in raw_features) / len(raw_features) for index in range(8, feature_count)]
    scales = []
    for offset, mean in enumerate(means, start=8):
        variance = sum((row[offset] - mean) ** 2 for row in raw_features) / len(raw_features)
        scales.append(sqrt(variance) or 1.0)

    def normalize(values):
        return [1.0, *values[:8], *[
            (values[index] - means[index - 8]) / scales[index - 8]
            for index in range(8, feature_count)
        ]]

    x_rows = [normalize(row) for row in raw_features]
    target = normalize(target_raw)
    width = len(target)
    gram = [[0.0] * width for _ in range(width)]
    rhs = [0.0] * width
    for x_row, (_, _, quantity) in zip(x_rows, rows):
        for i in range(width):
            rhs[i] += x_row[i] * quantity
            for j in range(width):
                gram[i][j] += x_row[i] * x_row[j]
    # Ridge regularization stabilizes estimates when weather variables co-vary.
    for index in range(1, width):
        gram[index][index] += 2.0
    coefficients = _solve(gram, rhs)
    return max(0, round(sum(a * b for a, b in zip(coefficients, target))))


def predict_demand(
    db: Session,
    target_day: date,
    target_weather: dict,
    sales_sources: list[str],
    weather_sources: list[str],
    product_id=None,
):
    if not sales_sources or not weather_sources:
        raise HTTPException(422, "Configura fuentes de ventas y clima para entrenar.")
    weather_rows = list(
        db.scalars(
            select(WeatherObservation)
            .where(WeatherObservation.source.in_(weather_sources))
            .order_by(WeatherObservation.observation_date)
        )
    )
    if len(weather_rows) < MIN_TRAINING_DAYS:
        raise HTTPException(
            422,
            f"Se requieren al menos {MIN_TRAINING_DAYS} días de clima histórico para entrenar.",
        )

    start = weather_rows[0].observation_date
    end = weather_rows[-1].observation_date
    weather_by_day = {
        row.observation_date: {
            "temperature_max_c": float(row.temperature_max_c or 0),
            "temperature_min_c": float(row.temperature_min_c or 0),
            "precipitation_mm": float(row.precipitation_mm),
            "precipitation_probability_percent": float(
                row.precipitation_probability_percent or 0
            ),
        }
        for row in weather_rows
    }
    quantities = defaultdict(int)
    for sale_day, pid, units in db.execute(
        select(Sale.sale_date, Sale.product_id, func.sum(Sale.quantity))
        .join(SaleTransaction, Sale.transaction_id == SaleTransaction.id)
        .where(
            SaleTransaction.status == "COMPLETED",
            SaleTransaction.source.in_(sales_sources),
            Sale.sale_date >= start,
            Sale.sale_date <= end,
        )
        .group_by(Sale.sale_date, Sale.product_id)
    ):
        quantities[(sale_day, pid)] = int(units)

    source_counts = Counter(
        dict(
            db.execute(
                select(SaleTransaction.source, func.count(SaleTransaction.id))
                .where(
                    SaleTransaction.status == "COMPLETED",
                    SaleTransaction.source.in_(sales_sources),
                    SaleTransaction.sale_date >= start,
                    SaleTransaction.sale_date <= end,
                )
                .group_by(SaleTransaction.source)
            ).all()
        )
    )
    products_query = select(Product).where(Product.active.is_(True)).order_by(Product.id)
    if product_id is not None:
        products_query = products_query.where(Product.id == product_id)
    products = list(db.scalars(products_query))
    if product_id is not None and not products:
        raise HTTPException(404, "Product not found")

    predictions = []
    for product in products:
        training = [
            (
                day,
                weather,
                quantities[(day, product.id)],
            )
            for day, weather in weather_by_day.items()
        ]
        if sum(units > 0 for _, _, units in training) < MIN_TRAINING_DAYS:
            raise HTTPException(
                422,
                f"El producto {product.name} no tiene suficientes días con ventas para entrenar.",
            )
        predictions.append(
            {
                "product_id": product.id,
                "product_name": product.name,
                "predicted_units": _fit_predict(training, target_day, target_weather),
                "training_days": len(training),
            }
        )

    used_sales_sources = sorted(source_counts)
    used_weather_sources = sorted({row.source for row in weather_rows})
    quality = (
        "synthetic"
        if "SYNTHETIC" in used_sales_sources or "SYNTHETIC" in used_weather_sources
        else "real"
    )
    return {
        "model": "ridge_linear_regression",
        "data_quality": quality,
        "training_period": {"start": start, "end": end},
        "training_sales_sources": used_sales_sources,
        "training_weather_sources": used_weather_sources,
        "predictions": predictions,
    }
