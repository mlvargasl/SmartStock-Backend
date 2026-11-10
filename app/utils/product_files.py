"""Column selection for product/recipe spreadsheets."""

from fastapi import HTTPException
from app.utils.sales_files import read_sales_file


def product_columns(headers):
    headers = [
        str(value).strip().lower() if value is not None else "" for value in headers
    ]
    nonempty = [header for header in headers if header]
    if len(nonempty) != len(set(nonempty)):
        raise HTTPException(400, "El archivo contiene columnas duplicadas.")
    required = ("producto", "ingrediente", "cantidad", "unidad")
    if not set(required).issubset(headers):
        raise HTTPException(
            400,
            "El archivo debe contener las columnas producto, ingrediente, cantidad y unidad.",
        )
    names = list(required)
    if "stock_minimo" in headers:
        names.append("stock_minimo")
    return {name: headers.index(name) for name in names}


def read_product_file(filename, content):
    return read_sales_file(filename, content, column_selector=product_columns)
