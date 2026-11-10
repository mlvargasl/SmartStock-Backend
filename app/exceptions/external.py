"""Controlled errors raised by external providers."""


class ExternalAPIError(Exception):
    status_code = 503
    detail = "External service temporarily unavailable"


class WeatherAPIError(ExternalAPIError):
    detail = "Weather service temporarily unavailable"


class CalendarAPIError(ExternalAPIError):
    detail = "Calendar service temporarily unavailable"


class ExternalAPITimeoutError(ExternalAPIError):
    pass


class WeatherAPITimeoutError(WeatherAPIError, ExternalAPITimeoutError):
    pass


class CalendarAPITimeoutError(CalendarAPIError, ExternalAPITimeoutError):
    pass


class WeatherDateUnavailable(WeatherAPIError):
    status_code = 422
    detail = "Weather data unavailable for the requested date"
