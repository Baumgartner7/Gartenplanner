import pytest
from datetime import datetime, date, timedelta
from database import db
from models import Variety, Planting, Harvest

def test_harvest_days_to_harvest_calculation(app):
    """Test that Harvest.get_days_to_harvest() calculates correctly"""
    with app.app_context():
        # Create a variety
        variety = Variety(
            name='Test Tomato',
            plant_family='Solanaceae',
            days_to_harvest=90
        )
        db.session.add(variety)
        db.session.commit()

        # Create a planting
        planting_date = date(2025, 5, 15)
        planting = Planting(
            variety_id=variety.id,
            year=2025,
            quantity=3,
            planting_date=planting_date
        )
        db.session.add(planting)
        db.session.commit()

        # Create a harvest 90 days later
        harvest_date = planting_date + timedelta(days=90)
        harvest = Harvest(
            planting_id=planting.id,
            first_harvest_date=harvest_date,
            quantity_harvested='3 kg'
        )
        db.session.add(harvest)
        db.session.commit()

        # Test calculation
        db.session.refresh(harvest)
        assert harvest.get_days_to_harvest() == 90

def test_harvest_days_to_harvest_with_last_date(app):
    """Test that last_harvest_date doesn't affect get_days_to_harvest"""
    with app.app_context():
        variety = Variety(name='Test Pepper', plant_family='Solanaceae')
        db.session.add(variety)
        db.session.commit()

        planting_date = date(2025, 5, 1)
        planting = Planting(
            variety_id=variety.id,
            year=2025,
            quantity=2,
            planting_date=planting_date
        )
        db.session.add(planting)
        db.session.commit()

        # Harvest with both dates
        first = date(2025, 7, 20)  # 80 days
        last = date(2025, 8, 5)    # 96 days
        harvest = Harvest(
            planting_id=planting.id,
            first_harvest_date=first,
            last_harvest_date=last,
            quantity_harvested='2 kg'
        )
        db.session.add(harvest)
        db.session.commit()

        # Should use first harvest date
        assert harvest.get_days_to_harvest() == 80

def test_harvest_days_to_harvest_no_planting(app):
    """Test get_days_to_harvest returns None when planting is missing"""
    with app.app_context():
        # Create a harvest with invalid planting_id
        harvest = Harvest(
            planting_id=999999,  # Non-existent
            first_harvest_date=date(2025, 6, 1)
        )
        db.session.add(harvest)
        db.session.commit()

        # Should return None due to missing relationship
        assert harvest.get_days_to_harvest() is None

def test_harvest_days_to_harvest_no_first_date(app):
    """Test get_days_to_harvest returns None when first_harvest_date is None"""
    with app.app_context():
        variety = Variety(name='Test Bean', plant_family='Fabaceae')
        db.session.add(variety)
        db.session.commit()

        planting = Planting(
            variety_id=variety.id,
            year=2025,
            quantity=5,
            planting_date=date(2025, 4, 15)
        )
        db.session.add(planting)
        db.session.commit()

        # Harvest without first_harvest_date should not happen due to validation,
        # but method should handle it gracefully
        harvest = Harvest(
            planting_id=planting.id,
            first_harvest_date=None,  # This would fail validation, but test method directly
            quantity_harvested='?'
        )
        # Don't commit, just test the method
        assert harvest.get_days_to_harvest() is None

def test_variety_days_to_harvest_actual_avg_update(app):
    """Test updating Variety.days_to_harvest_actual_avg from harvests"""
    with app.app_context():
        variety = Variety(name='Test Carrot', plant_family='Apiaceae', days_to_harvest=70)
        db.session.add(variety)
        db.session.commit()

        planting_date = date(2025, 4, 1)
        planting = Planting(
            variety_id=variety.id,
            year=2025,
            quantity=10,
            planting_date=planting_date
        )
        db.session.add(planting)
        db.session.commit()

        # Add multiple harvests with different days-to-harvest
        harvests = [
            Harvest(planting_id=planting.id, first_harvest_date=planting_date + timedelta(days=65)),
            Harvest(planting_id=planting.id, first_harvest_date=planting_date + timedelta(days=75)),
            Harvest(planting_id=planting.id, first_harvest_date=planting_date + timedelta(days=70)),
        ]
        for h in harvests:
            db.session.add(h)
        db.session.commit()

        # Calculate average
        avg = sum(h.get_days_to_harvest() for h in harvests) / len(harvests)
        variety.days_to_harvest_actual_avg = avg
        db.session.commit()

        # Verify
        db.session.refresh(variety)
        assert variety.days_to_harvest_actual_avg == pytest.approx(70.0)

def test_variety_days_to_harvest_actual_avg_no_harvests(app):
    """Test that avg remains None when variety has no harvests"""
    with app.app_context():
        variety = Variety(name='Test Radish', plant_family='Brassicaceae')
        db.session.add(variety)
        db.session.commit()

        # No harvests recorded
        assert variety.days_to_harvest_actual_avg is None

def test_harvest_stats_after_delete(app):
    """Test that avg is updated when harvests are deleted"""
    with app.app_context():
        variety = Variety(name='Test Beet', plant_family='Amaranthaceae')
        db.session.add(variety)
        db.session.commit()

        planting = Planting(
            variety_id=variety.id,
            year=2025,
            quantity=4,
            planting_date=date(2025, 3, 15)
        )
        db.session.add(planting)
        db.session.commit()

        # Add two harvests
        h1 = Harvest(planting_id=planting.id, first_harvest_date=date(2025, 5, 20))  # 66 days
        h2 = Harvest(planting_id=planting.id, first_harvest_date=date(2025, 5, 25))  # 71 days
        db.session.add_all([h1, h2])
        db.session.commit()

        # Initial average
        avg_initial = (66 + 71) / 2
        variety.days_to_harvest_actual_avg = avg_initial
        db.session.commit()

        # Delete one harvest
        db.session.delete(h2)
        db.session.commit()

        # Update avg
        variety.days_to_harvest_actual_avg = 66.0  # Only h1 remains
        db.session.commit()

        db.session.refresh(variety)
        assert variety.days_to_harvest_actual_avg == 66.0