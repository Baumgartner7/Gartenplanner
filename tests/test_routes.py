import pytest
import sys
import os
from datetime import date
from sqlalchemy.pool import StaticPool

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from models import db, Variety, Planting, Harvest

@pytest.fixture
def app():
    app = create_app()
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
        'connect_args': {'check_same_thread': False},
        'poolclass': StaticPool
    }
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.engine.dispose()

@pytest.fixture
def client(app):
    with app.test_client() as client:
        yield client


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

def test_variety_create_get(client):
    """Test GET request to variety_create route renders form."""
    response = client.get('/varieties/create')
    assert response.status_code == 200
    assert b'<form' in response.data

def test_variety_edit_get(client, init_data, app):
    """Test GET request to variety_edit route renders form."""
    with app.app_context():
        variety = Variety.query.get(init_data)
        variety_id = variety.id
    response = client.get(f'/varieties/{variety_id}/edit')
    assert response.status_code == 200
    assert b'<form' in response.data

def test_planting_create_get(client, init_data):
    """Test GET request to planting_create route renders form."""
    response = client.get('/plantings/create')
    assert response.status_code == 200
    assert b'<form' in response.data

def test_planting_edit_get(client, init_data, app):
    """Test GET request to planting_edit route renders form."""
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

    response = client.get(f'/plantings/{planting_id}/edit')
    assert response.status_code == 200
    assert b'<form' in response.data

def test_harvest_create_get(client, init_data, app):
    """Test GET request to harvest_create route renders form."""
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

    response = client.get(f'/plantings/{planting_id}/harvests/create')
    assert response.status_code == 200
    assert b'<form' in response.data

def test_harvest_edit_get(client, init_data, app):
    """Test GET request to harvest_edit route renders form."""
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

        harvest = Harvest(
            planting_id=planting_id,
            first_harvest_date=date(2024, 7, 15),
            last_harvest_date=date(2024, 8, 20)
        )
        db.session.add(harvest)
        db.session.commit()
        harvest_id = harvest.id

    response = client.get(f'/harvests/{harvest_id}/edit')
    assert response.status_code == 200
    assert b'<form' in response.data

def test_variety_404(client):
    """Test 404 for non-existent variety."""
    response = client.get('/varieties/99999')
    assert response.status_code == 404

def test_planting_404(client):
    """Test 404 for non-existent planting."""
    response = client.get('/plantings/99999')
    assert response.status_code == 404

def test_harvest_404(client):
    """Test 404 for non-existent harvest."""
    response = client.get('/harvests/99999')
    assert response.status_code == 404

def test_variety_create_duplicate_name(client, init_data, app):
    """Test creating variety with duplicate name fails."""
    with app.app_context():
        existing_variety = Variety.query.get(init_data)
        duplicate_name = existing_variety.name

    response = client.post('/varieties/create', data={
        'name': duplicate_name,
        'plant_family': 'Solanaceae',
        'sowing_months': ['4', '5']
    }, follow_redirects=True)
    assert response.status_code == 200
    assert b'already exists' in response.data.lower() or b'error' in response.data.lower()

def test_planting_create_invalid_date(client, init_data):
    """Test planting creation with invalid date format."""
    response = client.post('/plantings/create', data={
        'variety_id': init_data,
        'year': 2024,
        'quantity': 5,
        'planting_date': 'invalid-date'
    }, follow_redirects=True)
    assert response.status_code == 200
    assert b'Invalid date format' in response.data or b'error' in response.data.lower()

def test_planting_create_quantity_zero(client, init_data):
    """Test planting creation with quantity <= 0 fails validation."""
    response = client.post('/plantings/create', data={
        'variety_id': init_data,
        'year': 2024,
        'quantity': 0,
        'planting_date': '2024-05-15'
    }, follow_redirects=True)
    assert response.status_code == 200
    assert b'Invalid data' in response.data or b'error' in response.data.lower()

def test_harvest_create_invalid_date(client, init_data, app):
    """Test harvest creation with invalid date format."""
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
        'first_harvest_date': 'invalid-date',
        'last_harvest_date': '2024-08-20',
        'quantity_harvested': '5 kg'
    }, follow_redirects=True)
    assert response.status_code == 200
    assert b'Invalid date format' in response.data or b'error' in response.data.lower()

def test_harvest_create_harvest_before_planting(client, init_data, app):
    """Test harvest creation with harvest date before planting date."""
    with app.app_context():
        variety = Variety.query.get(init_data)
        planting = Planting(
            variety_id=variety.id,
            year=2024,
            quantity=3,
            planting_date=date(2024, 6, 1)
        )
        db.session.add(planting)
        db.session.commit()
        planting_id = planting.id

    response = client.post(f'/plantings/{planting_id}/harvests/create', data={
        'first_harvest_date': '2024-05-15',  # Before planting
        'last_harvest_date': '2024-06-01',
        'quantity_harvested': '5 kg'
    }, follow_redirects=True)
    assert response.status_code == 200
    assert b'Invalid dates' in response.data or b'error' in response.data.lower()

def test_report_year_no_data(client):
    """Test report for year with no data."""
    response = client.get('/reports/2020')
    assert response.status_code == 200
    # Should still render but with empty data
    assert b'Yearly Report' in response.data

def test_export_year_no_data(client):
    """Test export for year with no data."""
    response = client.get('/reports/2020/export')
    assert response.status_code == 200
    assert response.content_type == 'text/csv; charset=utf-8'
    # Should export headers only
    assert b'Variety' in response.data

def test_plantings_list_year_filter(client, init_data, app):
    """Test plantings list with year filter."""
    with app.app_context():
        variety = Variety.query.get(init_data)
        planting1 = Planting(
            variety_id=variety.id,
            year=2024,
            quantity=3,
            planting_date=date(2024, 5, 20)
        )
        planting2 = Planting(
            variety_id=variety.id,
            year=2023,
            quantity=2,
            planting_date=date(2023, 6, 1)
        )
        db.session.add(planting1)
        db.session.add(planting2)
        db.session.commit()

    response = client.get('/plantings?year=2024')
    assert response.status_code == 200
    assert b'Planting Journal' in response.data

def test_harvest_edit_invalid_date(client, init_data, app):
    """Test harvest edit with invalid date."""
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

        harvest = Harvest(
            planting_id=planting_id,
            first_harvest_date=date(2024, 7, 15),
            last_harvest_date=date(2024, 8, 20)
        )
        db.session.add(harvest)
        db.session.commit()
        harvest_id = harvest.id

    response = client.post(f'/harvests/{harvest_id}/edit', data={
        'first_harvest_date': 'invalid',
        'last_harvest_date': '2024-08-20',
        'quantity_harvested': '5 kg'
    }, follow_redirects=True)
    assert response.status_code == 200
    assert b'Invalid date format' in response.data or b'error' in response.data.lower()