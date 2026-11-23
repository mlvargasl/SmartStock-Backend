from datetime import datetime, timezone


def test_product_stock_sales_and_cancellation(client, auth):
    admin = auth()
    product = client.post('/api/products', headers=admin, json={'name': 'Stock pan'}).json()
    pid = product['id']
    assert product['stock_quantity'] == 0
    assert client.put(f'/api/products/{pid}/stock', headers=auth('PRODUCTION_MANAGER'), json={'stock_quantity': 10}).status_code == 200
    body = {'sold_at': datetime.now(timezone.utc).isoformat(), 'items': [{'product_id': pid, 'quantity': 4}]}
    sale = client.post('/api/sale-transactions', headers=admin, json=body)
    assert sale.status_code == 201, sale.text
    assert client.get(f'/api/products/{pid}', headers=admin).json()['stock_quantity'] == 6
    assert client.post('/api/sale-transactions', headers=admin, json=body).status_code == 201
    assert client.post('/api/sale-transactions', headers=admin, json=body).status_code == 400
    assert client.get(f'/api/products/{pid}', headers=admin).json()['stock_quantity'] == 2
    assert client.patch(f"/api/sale-transactions/{sale.json()['id']}/cancel", headers=admin).status_code == 200
    assert client.get(f'/api/products/{pid}', headers=admin).json()['stock_quantity'] == 6
    assert client.patch(f"/api/sale-transactions/{sale.json()['id']}/cancel", headers=admin).status_code == 409
    assert client.get(f'/api/products/{pid}', headers=admin).json()['stock_quantity'] == 6
    assert client.put(f'/api/products/{pid}/stock', headers=admin, json={'stock_quantity': -1}).status_code == 422


def test_import_does_not_change_stock_and_sale_atomic(client, auth):
    h = auth()
    a = client.post('/api/products', headers=h, json={'name': 'Stock a'}).json()['id']
    b = client.post('/api/products', headers=h, json={'name': 'Stock b'}).json()['id']
    client.put(f'/api/products/{a}/stock', headers=h, json={'stock_quantity': 10})
    body = {'sold_at': datetime.now(timezone.utc).isoformat(), 'items': [{'product_id': a, 'quantity': 2}, {'product_id': b, 'quantity': 1}]}
    assert client.post('/api/sale-transactions', headers=h, json=body).status_code == 400
    assert client.get(f'/api/products/{a}', headers=h).json()['stock_quantity'] == 10
    csv = 'fecha,producto,cantidad\n2026-10-01,Stock a,5\n'
    assert client.post('/api/sales/import', headers=h, files={'file': ('ventas.csv', csv, 'text/csv')}).status_code == 200
    assert client.get(f'/api/products/{a}', headers=h).json()['stock_quantity'] == 10


def test_bulk_stock_update_is_atomic_and_rejects_stale_values(client, auth):
    h = auth()
    first = client.post('/api/products', headers=h, json={'name': 'Lote uno'}).json()['id']
    second = client.post('/api/products', headers=h, json={'name': 'Lote dos'}).json()['id']
    data = {'items': [{'product_id': first, 'expected_stock': 0, 'stock_quantity': 5}, {'product_id': second, 'expected_stock': 0, 'stock_quantity': 8}]}
    response = client.post('/api/products/stock/bulk', headers=auth('PRODUCTION_MANAGER'), json=data)
    assert response.status_code == 200, response.text
    assert client.get(f'/api/products/{first}', headers=h).json()['stock_quantity'] == 5
    assert client.get(f'/api/products/{second}', headers=h).json()['stock_quantity'] == 8
    data['items'][0]['expected_stock'] = 5
    data['items'][0]['stock_quantity'] = 6
    data['items'][1]['stock_quantity'] = 9
    assert client.post('/api/products/stock/bulk', headers=h, json=data).status_code == 409
    assert client.get(f'/api/products/{first}', headers=h).json()['stock_quantity'] == 5
    assert client.get(f'/api/products/{second}', headers=h).json()['stock_quantity'] == 8
    assert client.post('/api/products/stock/bulk', json=data).status_code == 401
