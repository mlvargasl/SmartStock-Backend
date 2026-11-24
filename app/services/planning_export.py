"""Export saved production recommendations and ingredient requirements."""
import csv
from decimal import Decimal
from io import BytesIO, StringIO
from xml.sax.saxutils import escape


def export_rows(records, requirements, start, end):
    dates = sorted({record.forecast_date for record in records})
    products = {}
    for record in records:
        for item in record.items:
            product = products.setdefault(item.product_id, {'name': item.product_name, 'days': {}})
            product['days'][record.forecast_date] = item.final_units
    rows = [["Producto", *[day.strftime('%d/%m/%Y') for day in dates]], *[
        [product['name'], *[product['days'].get(day, '') for day in dates]]
        for product in sorted(products.values(), key=lambda item: item['name'].casefold())
    ]]
    rows.extend([[], ["Ingredientes necesarios"], ["Ingrediente", "Unidad", "Necesario", "Stock actual", "Stock mínimo", "Falta para producir", "Pedir para llegar al mínimo"]])
    for item in requirements["ingredients"]:
        rows.append([item['name'], item['unit'], item['required'], item['current_stock'], item['minimum_stock'], item['shortage'], item['order_to_minimum']])
    if not requirements['complete']:
        rows.extend([[], ["Cálculo incompleto"], ["Productos sin receta", ', '.join(x['product_name'] for x in requirements['products_without_recipe'])], ["Ingredientes sin inventario", ', '.join(requirements['ingredients_without_stock'])]])
    return rows


def safe(value):
    if value is None:
        return "No disponible"
    text = str(value)
    return "'" + text if text.lstrip().startswith(('=', '+', '-', '@')) and not isinstance(value, (int, float, Decimal)) else text


def render_export(rows, fmt):
    if fmt == 'csv':
        output = StringIO(newline='')
        csv.writer(output).writerows([[safe(v) for v in row] for row in rows])
        return ('\ufeff' + output.getvalue()).encode('utf-8')
    if fmt == 'xlsx':
        from openpyxl import Workbook
        from openpyxl.utils import get_column_letter
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = 'Planificación'
        for row in rows:
            sheet.append([safe(value) if isinstance(value, str) else value for value in row])
        for index in range(1, max(map(len, rows), default=0) + 1):
            sheet.column_dimensions[get_column_letter(index)].width = 24
        output = BytesIO()
        workbook.save(output)
        return output.getvalue()
    if fmt == 'pdf':
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
        output = BytesIO()
        doc = SimpleDocTemplate(output, pagesize=landscape(A4), leftMargin=25, rightMargin=25, topMargin=25, bottomMargin=25)
        style = getSampleStyleSheet()['BodyText']
        style.fontSize = 8
        style.leading = 10
        content = []
        section = []
        def flush():
            if not section:
                return
            width = max(map(len, section))
            data = [[Paragraph(escape(str(v if v is not None else 'No disponible')), style) for v in row] + [''] * (width-len(row)) for row in section]
            table = Table(data, colWidths=[(landscape(A4)[0]-50)/width]*width, repeatRows=1)
            table.setStyle(TableStyle([('GRID',(0,0),(-1,-1),0.3,colors.lightgrey),('VALIGN',(0,0),(-1,-1),'TOP')]))
            content.extend([table, Spacer(1, 10)])
            section.clear()
        split = next((index for index, row in enumerate(rows) if not row), len(rows))
        products = rows[:split]
        for first in range(1, len(products[0]), 7):
            for row in products:
                section.append([row[0], *row[first:first + 7]])
            flush()
        for row in rows[split + 1:]:
            if not row:
                flush()
            else:
                section.append(row)
        flush()
        doc.build(content)
        return output.getvalue()
    raise ValueError('Formato no compatible')
