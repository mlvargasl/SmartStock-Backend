from datetime import date


def test_save_and_list_recommendations(client, auth):
    headers = auth()
    product = client.post('/api/products', headers=headers, json={'name': 'Producto prueba'}).json()
    data = {'forecast_date': str(date.today()), 'items': [{'product_id': product['id'], 'predicted_units': 10, 'final_units': 12, 'reason': 'Pedido especial'}]}
    saved = client.post('/api/recommendations', headers=headers, json=data)
    assert saved.status_code == 201, saved.text
    assert saved.json()['items'][0]['reason'] == 'Pedido especial'
    assert saved.json()['items'][0]['predicted_units'] == 10
    assert saved.json()['items'][0]['final_units'] == 12
    assert saved.json()['created_by_name'] == 'ADMIN'
    listed = client.get('/api/recommendations', headers=auth('PRODUCTION_MANAGER'))
    assert listed.status_code == 200
    assert any(record['id'] == saved.json()['id'] for record in listed.json())


def test_validate_recommendation_and_roles(client, auth):
    headers = auth()
    product = client.post('/api/products', headers=headers, json={'name': 'Otro producto'}).json()
    item = {'product_id': product['id'], 'predicted_units': 10, 'final_units': 11}
    body = {'forecast_date': '2026-11-23', 'items': [item]}
    assert client.post('/api/recommendations', headers=headers, json=body).status_code == 422
    item['reason'] = 'Evento'
    assert client.post('/api/recommendations', headers=auth('INVENTORY_MANAGER'), json=body).status_code == 403
    assert client.get('/api/recommendations').status_code == 401
    assert client.post('/api/recommendations', headers=headers, json={**body, 'items': [item, item]}).status_code == 422
    item['product_id'] = 999999
    assert client.post('/api/recommendations', headers=headers, json=body).status_code == 400


def test_edit_permissions_filter_and_audit(client, auth, connection):
    from sqlalchemy import text
    admin = auth()
    manager = auth('PRODUCTION_MANAGER')
    pid = client.post('/api/products', headers=admin, json={'name': 'Pan editado'}).json()['id']
    payload = {'forecast_date': '2026-11-23', 'items': [{'product_id': pid, 'predicted_units': 10, 'final_units': 10}]}
    rec = client.post('/api/recommendations', headers=admin, json=payload).json()
    update = {'items': [{'product_id': pid, 'final_units': 15, 'reason': 'Pedido especial'}]}
    url = f"/api/recommendations/{rec['id']}"
    assert client.put(url, headers=auth('INVENTORY_MANAGER'), json=update).status_code == 403
    assert client.put(url, headers=admin, json={'items': [{'product_id': pid, 'final_units': 15}]}).status_code == 400
    response = client.put(url, headers=manager, json=update)
    assert response.status_code == 200, response.text
    assert response.json()['items'][0]['predicted_units'] == 10
    assert response.json()['items'][0]['final_units'] == 15
    assert len(client.get('/api/recommendations?day=2026-11-23', headers=manager).json()) == 1
    assert client.get('/api/recommendations?day=2026-11-24', headers=manager).json() == []
    assert connection.execute(text('select count(*) from recommendation_changes')).scalar() == 1


def test_ingredient_requirements_latest_per_day_and_missing_recipe(client, auth):
    h = auth()
    pid = client.post('/api/products', headers=h, json={'name': 'Pan'}).json()['id']
    missing = client.post('/api/products', headers=h, json={'name': 'Sin receta'}).json()['id']
    iid = client.post('/api/ingredients', headers=h, json={'name': 'Harina', 'unit': 'g', 'minimum_stock': 25}).json()['id']
    assert client.post('/api/recipes', headers=h, json={'product_id': pid, 'ingredients': [{'ingredient_id': iid, 'quantity_per_unit': 5}]}).status_code == 201
    assert client.put(f'/api/inventory/{iid}', headers=h, json={'current_stock': 20}).status_code == 200
    def create(day, amount, product=pid):
        return client.post('/api/recommendations', headers=h, json={'forecast_date': day, 'items': [{'product_id': product, 'predicted_units': amount, 'final_units': amount}]})
    assert create('2026-11-23', 2).status_code == 201
    assert create('2026-11-23', 4).status_code == 201
    assert create('2026-11-24', 3).status_code == 201
    assert create('2026-11-25', 1, missing).status_code == 201
    url = '/api/recommendations/ingredients?start_date=2026-11-23&end_date=2026-11-25'
    result = client.get(url, headers=h)
    assert result.status_code == 200, result.text
    data = result.json()
    assert not data['complete'] and data['products_without_recipe'][0]['product_name'] == 'Sin receta'
    entry = data['ingredients'][0]
    assert float(entry['required']) == 35 and float(entry['remaining']) == -15 and float(entry['shortage']) == 15
    assert float(entry['minimum_stock']) == 25 and float(entry['order_to_minimum']) == 40
    assert entry['low_stock'] is True and entry['low_after_production'] is True
    assert float(client.get(f'/api/inventory/{iid}', headers=h).json()['current_stock']) == 20
    assert client.get('/api/recommendations/ingredients?start_date=2026-11-26&end_date=2026-11-25', headers=h).status_code == 400
    inventory_response = client.get(url, headers=auth('INVENTORY_MANAGER'))
    assert inventory_response.status_code == 200
    assert inventory_response.json() == data
    assert client.get('/api/recommendations', headers=auth('INVENTORY_MANAGER')).status_code == 200


def test_ingredient_minimum_after_production_without_shortage(client, auth):
    h = auth()
    pid = client.post('/api/products', headers=h, json={'name': 'Pan especial'}).json()['id']
    iid = client.post('/api/ingredients', headers=h, json={'name': 'Harina especial', 'unit': 'g', 'minimum_stock': 10}).json()['id']
    assert client.post('/api/recipes', headers=h, json={'product_id': pid, 'ingredients': [{'ingredient_id': iid, 'quantity_per_unit': 5}]}).status_code == 201
    assert client.put(f'/api/inventory/{iid}', headers=h, json={'current_stock': 20}).status_code == 200
    body = {'forecast_date': '2026-11-23', 'items': [{'product_id': pid, 'predicted_units': 2, 'final_units': 2}]}
    assert client.post('/api/recommendations', headers=h, json=body).status_code == 201
    r = client.get('/api/recommendations/ingredients?start_date=2026-11-23&end_date=2026-11-23', headers=auth('INVENTORY_MANAGER'))
    assert r.status_code == 200
    item = r.json()['ingredients'][0]
    assert float(item['shortage']) == 0 and float(item['remaining']) == 10
    assert item['low_stock'] is False and item['low_after_production'] is True
    assert float(item['order_to_minimum']) == 0


def test_ingredients_for_exact_recommendation_update_and_current_stock(client, auth):
    admin = auth()
    inventory = auth('INVENTORY_MANAGER')
    product = client.post('/api/products', headers=admin, json={'name': 'Pan especial de prueba'}).json()['id']
    ingredient = client.post('/api/ingredients', headers=admin, json={'name': 'Harina especial de prueba', 'unit': 'g', 'minimum_stock': 5}).json()['id']
    assert client.post('/api/recipes', headers=admin, json={'product_id': product, 'ingredients': [{'ingredient_id': ingredient, 'quantity_per_unit': 5}]}).status_code == 201
    assert client.put(f'/api/inventory/{ingredient}', headers=admin, json={'current_stock': 20}).status_code == 200
    def create(units):
        response = client.post('/api/recommendations', headers=admin, json={'forecast_date': '2026-11-23', 'items': [{'product_id': product, 'predicted_units': units, 'final_units': units}]})
        assert response.status_code == 201
        return response.json()['id']
    first, second = create(2), create(3)
    def calculate(ident):
        return client.get(f'/api/recommendations/{ident}/ingredients', headers=inventory)
    assert float(calculate(first).json()['ingredients'][0]['required']) == 10
    assert float(calculate(second).json()['ingredients'][0]['required']) == 15
    assert client.put(f'/api/recommendations/{first}', headers=admin, json={'items': [{'product_id': product, 'final_units': 5, 'reason': 'Pedido especial'}]}).status_code == 200
    item = calculate(first).json()['ingredients'][0]
    assert float(item['required']) == 25 and float(item['shortage']) == 5
    assert float(calculate(second).json()['ingredients'][0]['required']) == 15
    assert client.put(f'/api/inventory/{ingredient}', headers=admin, json={'current_stock': 40}).status_code == 200
    item = calculate(first).json()['ingredients'][0]
    assert float(item['remaining']) == 15 and float(item['shortage']) == 0
    assert client.get('/api/recommendations/999999/ingredients', headers=inventory).status_code == 404
    assert client.get(f'/api/recommendations/{first}/ingredients').status_code == 401
