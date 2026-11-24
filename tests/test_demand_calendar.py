from datetime import date, timedelta

from app.services.demand_forecast import _fit_predict


def test_calendar_features_influence_demand_forecast():
    weather = {
        "temperature_max_c": 20,
        "temperature_min_c": 10,
        "precipitation_mm": 0,
        "precipitation_probability_percent": 0,
    }
    rows = []
    for i in range(120):
        day = date(2025, 1, 1) + timedelta(days=i)
        holiday = i % 10 == 0
        festivity = i % 13 == 0 and not holiday
        calendar = {"is_holiday": holiday, "is_festivity": festivity}
        rows.append((day, weather, calendar, 40 if holiday else 25 if festivity else 10))

    target = date(2025, 5, 1)
    def predict(holiday, festivity):
        return _fit_predict(rows, target, weather, {
            "is_holiday": holiday, "is_festivity": festivity,
        })

    normal = predict(False, False)
    assert predict(True, False) > normal
    assert predict(False, True) > normal
