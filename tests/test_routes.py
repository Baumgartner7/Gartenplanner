import pytest
import sys
import os
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from models import db, Variety, Planting, Harvest

@pytest.fixture
def app():
    app = create_app()
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    with app.app_context():
        db.create_all()
        yield app
        db.drop_all()

@pytest.fixture
def client(app):
    return app.test_client()

@pytest.fixture
def init_data(app):
    with app.app_context():
        variety = Variety(name="Test Tomato", plant_family="Solanaceae")
        variety.set_sowing_months_list([3, 4])
        db.session.add(variety)
        db.session.commit()
        # Return the ID, not the object, to avoid DetachedInstanceError
        return variety.id

def test_index_route(client):
    response = client.get('/')
    assert response.status_code == 200
    assert b'Garden Dashboard' in response.data

def test_varieties_list(client, init_data):
    response = client.get('/varieties')
    assert response.status_code == 200
    assert b'Test Tomato' in response.data

def test_variety_create(client):
    response = client.post('/varieties/create', data={
        'name': 'New Tomato',
        'plant_family': 'Solanaceae',
        'sowing_months': ['4', '5']
    }, follow_redirects=True)
    assert response.status_code == 200
    assert b'New Tomato' in response.data or b'created successfully' in response.data

def test_variety_edit(client, init_data, app):
    with app.app_context():
        variety = Variety.query.get(init_data)
        assert variety is not None
        variety_id = variety.id
        response = client.post(f'/varieties/{variety_id}/edit', data={
            'name': 'Updated Tomato',
            'plant_family': 'Solanaceae',
            'sowing_months': ['5']
        }, follow_redirects=True)
        assert response.status_code == 200
        assert b'updated successfully' in response.data

def test_variety_delete(client, init_data, app):
    with app.app_context():
        variety = Variety.query.get(init_data)
        assert variety is not None
        variety_id = variety.id
    response = client.post(f'/varieties/{variety_id}/delete', follow_redirects=True)
    assert response.status_code == 200
    assert b'deleted' in response.data

def test_plantings_list(client, init_data):
    response = client.get('/plantings')
    assert response.status_code == 200
    assert b'Planting Journal' in response.data

def test_planting_create(client, init_data):
    response = client.post('/plantings/create', data={
        'variety_id': init_data,
        'year': 2024,
        'quantity': 5,
        'planting_date': '2024-05-15'
    }, follow_redirects=True)
    assert response.status_code == 200
    assert b'recorded successfully' in response.data or b'Planting Journal' in response.data

def test_planting_detail(client, init_data, app):
    with app.app_context():
        variety = Variety.query.get(init_data)
        planting = Planting(
            variety_id=variety.id,
            year=2024,
            quantity=3,
            planting_date=date(2024, 5, 20)
        )
        db.session.add(planting)
        db.session.commit()
        planting_id = planting.id

    response = client.get(f'/plantings/{planting_id}')
    assert response.status_code == 200

def test_planting_edit(client, init_data, app):
    with app.app_context():
        variety = Variety.query.get(init_data)
        planting = Planting(
            variety_id=variety.id,
            year=2024,
            quantity=3,
            planting_date=date(2024, 5, 20)
        )
        db.session.add(planting)
        db.session.commit()
        planting_id = planting.id

    response = client.post(f'/plantings/{planting_id}/edit', data={
        'variety_id': init_data,
        'year': 2024,
        'quantity': 10,
        'planting_date': '2024-05-25'
    }, follow_redirects=True)
    assert response.status_code == 200
    assert b'updated successfully' in response.data

def test_planting_delete(client, init_data, app):
    with app.app_context():
        variety = Variety.query.get(init_data)
        planting = Planting(
            variety_id=variety.id,
            year=2024,
            quantity=3,
            planting_date=date(2024, 5, 20)
        )
        db.session.add(planting)
        db.session.commit()
        planting_id = planting.id

    response = client.post(f'/plantings/{planting_id}/delete', follow_redirects=True)
    assert response.status_code == 200
    assert b'deleted' in response.data

def test_harvest_create(client, init_data, app):
    with app.app_context():
        variety = Variety.query.get(init_data)
        planting = Planting(
            variety_id=variety.id,
            year=2024,
            quantity=3,
            planting_date=date(2024, 5, 20)
        )
        db.session.add(planting)
        db.session.commit()
        planting_id = planting.id

    response = client.post(f'/plantings/{planting_id}/harvests/create', data={
        'first_harvest_date': '2024-07-15',
        'last_harvest_date': '2024-08-20',
        'quantity_harvested': '5 kg'
    }, follow_redirects=True)
    assert response.status_code == 200
    assert b'recorded successfully' in response.data or b'Planting Details' in response.data

def test_report_year(client, init_data, app):
    with app.app_context():
        variety = Variety.query.get(init_data)
        planting = Planting(
            variety_id=variety.id,
            year=2024,
            quantity=3,
            planting_date=date(2024, 5, 20)
        )
        db.session.add(planting)
        db.session.commit()

    response = client.get('/reports/2024')
    assert response.status_code == 200
    assert b'Yearly Report' in response.data
    assert b'2024' in response.data

def test_export_year(client, init_data, app):
    with app.app_context():
        variety = Variety.query.get(init_data)
        planting = Planting(
            variety_id=variety.id,
            year=2024,
            quantity=3,
            planting_date=date(2024, 5, 20)
        )
        db.session.add(planting)
        db.session.commit()

    response = client.get('/reports/2024/export')
    assert response.status_code == 200
    assert response.content_type == 'text/csv; charset=utf-8'
    assert b'Variety' in response.data