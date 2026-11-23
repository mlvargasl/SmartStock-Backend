
def test_inventory_bulk_permissions_decimal_and_atomic_conflict(client, auth):
    h = auth()
    first = client.post('/api/ingredients', headers=h, json={'name': 'Harina de prueba', 'unit': 'kg'}).json()['id']
    second = client.post('/api/ingredients', headers=h, json={'name': 'Azúcar de prueba', 'unit': 'kg'}).json()['id']
    data = {'items': [{'ingredient_id': first, 'expected_stock': '0', 'current_stock': '1.125'}, {'ingredient_id': second, 'expected_stock': '0', 'current_stock': '2.5'}]}
    assert client.post('/api/inventory/stock/bulk', json=data).status_code == 401
    assert client.post('/api/inventory/stock/bulk', headers=auth('PRODUCTION_MANAGER'), json=data).status_code == 403
    result = client.post('/api/inventory/stock/bulk', headers=auth('INVENTORY_MANAGER'), json=data)
    assert result.status_code == 200, result.text
    assert float(client.get(f'/api/inventory/{first}', headers=h).json()['current_stock']) == 1.125
    data['items'][0]['expected_stock'] = '1.125'
    data['items'][0]['current_stock'] = '3'
    assert client.post('/api/inventory/stock/bulk', headers=h, json=data).status_code == 409
    assert float(client.get(f'/api/inventory/{first}', headers=h).json()['current_stock']) == 1.125
    assert float(client.get(f'/api/inventory/{second}', headers=h).json()['current_stock']) == 2.5
    data['items'][1]['expected_stock'] = '2.5'
    data['items'][1]['current_stock'] = '-1'
    assert client.post('/api/inventory/stock/bulk', headers=h, json=data).status_code == 422
