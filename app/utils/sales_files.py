"""Parsing and rendering of sales CSV and Excel files."""

import csv
import io
import math
from datetime import date, datetime
from decimal import Decimal
from xml.etree.ElementTree import ParseError
from zipfile import BadZipFile, ZipFile

from defusedxml.common import DefusedXmlException
from fastapi import HTTPException
from openpyxl import load_workbook
from openpyxl.utils.exceptions import InvalidFileException

MAX_ROWS = 50000
MAX_EXPANDED_BYTES = 30 * 1024 * 1024


def columns_for(headers):
    headers = [
        str(value).strip().lower() if value is not None else "" for value in headers
    ]
    nonempty = [header for header in headers if header]
    if len(nonempty) != len(set(nonempty)):
        raise HTTPException(400, "File contains duplicate columns")
    spanish = {"fecha", "producto", "cantidad"}
    english = {"date", "product", "quantity"}
    if spanish.issubset(headers):
        columns = {
            name: headers.index(column)
            for name, column in zip(
                ("date", "product", "quantity"), ("fecha", "producto", "cantidad")
            )
        }
        id_header, time_header = "id_venta", "hora"
    elif english.issubset(headers):
        columns = {
            name: headers.index(name) for name in ("date", "product", "quantity")
        }
        id_header, time_header = "sale_id", "time"
    else:
        raise HTTPException(
            400,
            "File requires fecha, producto and cantidad columns (or date, product and quantity)",
        )
    if (id_header in headers) != (time_header in headers):
        raise HTTPException(400, "ID and time columns must be supplied together")
    if id_header in headers:
        columns.update(
            sale_id=headers.index(id_header), time=headers.index(time_header)
        )
    return columns


def read_sales_file(filename: str, content: bytes, column_selector=columns_for):
    extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if extension == "csv":
        try:
            text = content.decode("utf-8-sig")
            if "\x00" in text:
                raise HTTPException(400, "Invalid CSV file")
            # Excel configured for Spanish locales commonly uses semicolons.
            first_line = text.splitlines()[0] if text else ""
            probe = next(csv.reader([first_line], strict=True), [])
            delimiter = ";" if len(probe) == 1 and ";" in first_line else ","
            reader = csv.reader(
                io.StringIO(text, newline=""), delimiter=delimiter, strict=True
            )
            headers = next(reader, [])
            columns = column_selector(headers)
            rows = []
            for values in reader:
                if not values:
                    continue
                if len(rows) >= MAX_ROWS:
                    raise HTTPException(400, "File exceeds 50000 rows")
                rows.append(
                    (
                        reader.line_num,
                        {
                            name: values[index] if index < len(values) else None
                            for name, index in columns.items()
                        },
                        None if len(values) == len(headers) else "Invalid columns",
                    )
                )
            return rows
        except UnicodeDecodeError:
            raise HTTPException(400, "CSV must be UTF-8 encoded")
        except csv.Error:
            raise HTTPException(400, "Malformed CSV file")
    if extension != "xlsx":
        raise HTTPException(400, "File must have a .csv or .xlsx extension")
    try:
        with ZipFile(io.BytesIO(content)) as archive:
            if (
                sum(entry.file_size for entry in archive.infolist())
                > MAX_EXPANDED_BYTES
            ):
                raise HTTPException(400, "Excel file is too large when expanded")
        workbook = load_workbook(
            io.BytesIO(content), read_only=True, data_only=False, keep_links=False
        )
        try:
            sheet = workbook.worksheets[0]
            if sheet.max_column and sheet.max_column > 100:
                raise HTTPException(400, "File exceeds 100 columns")
            if sheet.max_row and sheet.max_row > MAX_ROWS + 1:
                raise HTTPException(400, "File exceeds 50000 rows")
            iterator = sheet.iter_rows()
            header_cells = next(iterator, ())
            if len(header_cells) > 100:
                raise HTTPException(400, "File exceeds 100 columns")
            columns = column_selector([cell.value for cell in header_cells])
            rows = []
            for row_number, cells in enumerate(iterator, 2):
                if not any(cell.value is not None for cell in cells):
                    continue
                if len(rows) >= MAX_ROWS:
                    raise HTTPException(400, "File exceeds 50000 rows")
                values = {
                    name: cells[index].value if index < len(cells) else None
                    for name, index in columns.items()
                }
                formula = any(
                    index < len(cells) and cells[index].data_type == "f"
                    for index in columns.values()
                )
                rows.append(
                    (row_number, values, "No se permiten fórmulas" if formula else None)
                )
            return rows
        finally:
            workbook.close()
    except (
        BadZipFile,
        InvalidFileException,
        ParseError,
        DefusedXmlException,
        KeyError,
        ValueError,
        IndexError,
        OSError,
    ):
        raise HTTPException(400, "Invalid or unreadable Excel file")


def normalize_sale_row(values):
    raw_date = values["date"]
    raw_product = values["product"]
    raw_quantity = values["quantity"]
    if isinstance(raw_date, datetime):
        raw_date = raw_date.date()
    if isinstance(raw_date, date):
        raw_date = raw_date.isoformat()
    if not isinstance(raw_date, str) or not isinstance(raw_product, str):
        raise ValueError("Fecha o producto inválido")
    if isinstance(raw_quantity, bool):
        raise ValueError("Cantidad inválida")
    if isinstance(raw_quantity, (int, float, Decimal)):
        if not math.isfinite(raw_quantity):
            raise ValueError("Cantidad inválida")
        if raw_quantity != int(raw_quantity):
            raise ValueError("Cantidad debe ser un entero positivo")
        raw_quantity = str(int(raw_quantity))
    if not isinstance(raw_quantity, str):
        raise ValueError("Cantidad inválida")
    raw_quantity = raw_quantity.strip()
    if not raw_quantity.isascii() or not raw_quantity.isdecimal():
        raise ValueError("Cantidad debe ser un entero positivo")
    return raw_date.strip(), raw_product.strip(), int(raw_quantity)


def render_sales_csv(rows):
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(["fecha", "producto", "cantidad"])
    for sale, product_name in rows:
        # Prevent spreadsheet programs from executing a product name as a formula.
        if product_name.lstrip().startswith(("=", "+", "-", "@", "\t", "\r")):
            product_name = "'" + product_name
        writer.writerow([sale.sale_date.isoformat(), product_name, sale.quantity])
    return "\ufeff" + output.getvalue()
