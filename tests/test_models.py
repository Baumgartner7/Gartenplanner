import pytest
import sys
import os
from datetime import datetime, date

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from models import db, Variety, Planting, Harvest

@pytest.fixture
def app():
    app = Flask(__name__)
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    db.init_app(app)
    with app.app_context():
        db.create_all()
        yield app
        db.drop_all()

@pytest.fixture
def client(app):
    return app.test_client()

def test_variety_creation(app):
    with app.app_context():
        variety = Variety(
            name="Test Tomato",
            plant_family="Solanaceae",
            outdoor_spacing_cm=50,
            indoor_pod_size_cm=10,
            days_to_harvest=65
        )
        variety.set_sowing_months_list([3, 4, 5])
        db.session.add(variety)
        db.session.commit()

        retrieved = Variety.query.filter_by(name="Test Tomato").first()
        assert retrieved is not None
        assert retrieved.name == "Test Tomato"
        assert retrieved.plant_family == "Solanaceae"
        assert retrieved.outdoor_spacing_cm == 50
        assert retrieved.indoor_pod_size_cm == 10
        assert retrieved.days_to_harvest == 65
        assert retrieved.get_sowing_months_list() == [3, 4, 5]

def test_variety_validate_sowing_months(app):
    with app.app_context():
        variety = Variety(name="Test")
        variety.set_sowing_months_list([1, 6, 12])
        assert variety.validate_sowing_months() == True

        variety.set_sowing_months_list([0, 1])
        assert variety.validate_sowing_months() == False

        variety.set_sowing_months_list([13])
        assert variety.validate_sowing_months() == False

        variety.set_sowing_months_list([1, "not a number"])
        assert variety.validate_sowing_months() == False

def test_planting_creation_and_validation(app):
    with app.app_context():
        variety = Variety(name="Test Pepper")
        db.session.add(variety)
        db.session.commit()

        planting_date = date(2024, 5, 15)
        planting = Planting(
            variety_id=variety.id,
            year=2024,
            quantity=10,
            planting_date=planting_date
        )
        assert planting.validate_dates() == True

        # Invalid: quantity <= 0
        planting.quantity = 0
        assert planting.validate_dates() == False
        planting.quantity = 10

        # Invalid: year doesn't match planting date
        planting.year = 2023
        assert planting.validate_dates() == False
        planting.year = 2024

        # Invalid: no planting date
        planting.planting_date = None
        assert planting.validate_dates() == False

def test_harvest_creation_and_validation(app):
    with app.app_context():
        variety = Variety(name="Test Bean")
        db.session.add(variety)
        db.session.commit()

        planting_date = date(2024, 6, 1)
        planting = Planting(
            variety_id=variety.id,
            year=2024,
            quantity=5,
            planting_date=planting_date
        )
        db.session.add(planting)
        db.session.commit()

        # Valid harvest - after planting
        harvest = Harvest(
            planting_id=planting.id,
            first_harvest_date=date(2024, 7, 20),
            last_harvest_date=date(2024, 8, 15)
        )
        assert harvest.validate_dates() == True

        # Invalid: harvest before planting (same day is not allowed - must be after)
        harvest.first_harvest_date = date(2024, 6, 1)
        assert harvest.validate_dates() == False
        harvest.first_harvest_date = date(2024, 7, 20)

        # Invalid: last before first
        harvest.last_harvest_date = date(2024, 7, 10)
        assert harvest.validate_dates() == False
        harvest.last_harvest_date = date(2024, 8, 15)

        # Invalid: no first harvest date
        harvest.first_harvest_date = None
        assert harvest.validate_dates() == False

def test_cascade_delete(app):
    with app.app_context():
        variety = Variety(name="Cascade Test")
        db.session.add(variety)
        db.session.commit()

        planting = Planting(
            variety_id=variety.id,
            year=2024,
            quantity=3,
            planting_date=date(2024, 5, 1)
        )
        db.session.add(planting)
        db.session.commit()

        harvest = Harvest(
            planting_id=planting.id,
            first_harvest_date=date(2024, 7, 1)
        )
        db.session.add(harvest)
        db.session.commit()

        # Delete variety should cascade to plantings and harvests
        db.session.delete(variety)
        db.session.commit()

        assert Variety.query.get(variety.id) is None
        assert Planting.query.get(planting.id) is None
        assert Harvest.query.get(harvest.id) is None

def test_get_sowing_months_list_with_invalid_json(app):
    """Test get_sowing_months_list() with invalid JSON string."""
    with app.app_context():
        variety = Variety(name="Test Invalid JSON")
        variety.optimal_sowing_months = "[1, 2, 3"  # Invalid JSON - missing closing bracket
        assert variety.get_sowing_months_list() == []

        variety.optimal_sowing_months = "not a json string"
        assert variety.get_sowing_months_list() == []

def test_harvest_validate_dates_with_none_planting(app):
    """Test Harvest.validate_dates() when planting query returns None."""
    with app.app_context():
        harvest = Harvest(
            planting_id=99999,  # Non-existent planting
            first_harvest_date=date(2024, 7, 20)
        )
        # Should return True because planting is None (no constraint violation)
        assert harvest.validate_dates() == True

def test_variety_to_dict_with_none_created_at(app):
    """Test Variety.to_dict() when created_at is None."""
    with app.app_context():
        variety = Variety(
            name="Test No Created At",
            plant_family="Solanceae"
        )
        result = variety.to_dict()
        assert result['created_at'] is None
        assert result['name'] == variety.name

def test_harvest_validate_dates_planting_before_first_harvest(app):
    """Test Harvest.validate_dates() ensures all harvest dates are after planting."""
    with app.app_context():
        variety = Variety(name="Test Harvest Dates")
        db.session.add(variety)
        db.session.commit()

        planting = Planting(
            variety_id=variety.id,
            year=2024,
            quantity=5,
            planting_date=date(2024, 6, 1)
        )
        db.session.add(planting)
        db.session.commit()

        # Test with last_harvest_date on same day as planting (should fail)
        harvest = Harvest(
            planting_id=planting.id,
            first_harvest_date=date(2024, 6, 1),
            last_harvest_date=date(2024, 6, 1)
        )
        assert harvest.validate_dates() == False

        # Test with last_harvest_date before planting
        harvest.first_harvest_date = date(2024, 7, 1)
        harvest.last_harvest_date = date(2024, 5, 15)
        assert harvest.validate_dates() == False

def test_validate_sowing_months_with_empty_list(app):
    """Test validate_sowing_months() with empty list returns True."""
    with app.app_context():
        variety = Variety(name="Test Empty Months")
        variety.set_sowing_months_list([])
        # Empty list should be valid (no months to validate)
        assert variety.validate_sowing_months() == True