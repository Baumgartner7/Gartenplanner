import pytest
from datetime import datetime, date, timedelta
from models import db, Variety, YearlyPlan, Planting
from app import create_app
import json

@pytest.fixture
def app():
    app = create_app()
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()

@pytest.fixture
def client(app):
    return app.test_client()

@pytest.fixture
def sample_variety(app):
    with app.app_context():
        variety = Variety(
            name='Tomato',
            plant_family='Solanaceae',
            days_to_harvest=90
        )
        variety.set_sowing_months_list([4, 5])  # April, May
        db.session.add(variety)
        db.session.commit()
        return variety.id

class TestYearlyPlanModel:
    def test_create_yearly_plan(self, app, sample_variety):
        with app.app_context():
            variety = Variety.query.get(sample_variety)
            plan = YearlyPlan(
                year=2025,
                variety_id=variety.id,
                planned_quantity=10,
                planned_sowing_date=date(2025, 4, 15),
                notes='Test plan',
                status='draft'
            )
            db.session.add(plan)
            db.session.commit()
            
            assert plan.id is not None
            assert plan.year == 2025
            assert plan.variety_id == variety.id
            assert plan.planned_quantity == 10
            assert plan.status == 'draft'

    def test_yearly_plan_validation_valid(self, app, sample_variety):
        with app.app_context():
            variety = Variety.query.get(sample_variety)
            plan = YearlyPlan(
                year=2025,
                variety_id=variety.id,
                planned_quantity=5,
                planned_sowing_date=date(2025, 4, 1),
                status='draft'
            )
            assert plan.validate() is True

    def test_yearly_plan_validation_invalid_quantity(self, app, sample_variety):
        with app.app_context():
            variety = Variety.query.get(sample_variety)
            plan = YearlyPlan(
                year=2025,
                variety_id=variety.id,
                planned_quantity=0,
                planned_sowing_date=date(2025, 4, 1),
                status='draft'
            )
            assert plan.validate() is False

    def test_yearly_plan_validation_invalid_status(self, app, sample_variety):
        with app.app_context():
            variety = Variety.query.get(sample_variety)
            plan = YearlyPlan(
                year=2025,
                variety_id=variety.id,
                planned_quantity=5,
                planned_sowing_date=date(2025, 4, 1),
                status='invalid'
            )
            assert plan.validate() is False

    def test_yearly_plan_validation_missing_variety(self, app):
        with app.app_context():
            plan = YearlyPlan(
                year=2025,
                variety_id=None,
                planned_quantity=5,
                planned_sowing_date=date(2025, 4, 1),
                status='draft'
            )
            assert plan.validate() is False

    def test_compute_sowing_date_from_months(self, app, sample_variety):
        """Test that planned_sowing_date can be auto-computed from variety's optimal months"""
        with app.app_context():
            variety = Variety.query.get(sample_variety)
            # Verify variety has sowing months
            assert len(variety.get_sowing_months_list()) == 2
            # Create plan without explicit sowing date
            plan = YearlyPlan(
                year=2025,
                variety_id=variety.id,
                planned_quantity=10,
                planned_sowing_date=None,
                status='draft'
            )
            # Compute suggested date (first optimal month, mid-month)
            suggested_date = plan.compute_sowing_date_from_variety()
            assert suggested_date is not None
            assert suggested_date.year == 2025
            assert suggested_date.month == 4  # First optimal month
            assert 1 <= suggested_date.day <= 31

class TestYearlyPlanRoutes:
    def test_list_plans_page(self, client, sample_variety):
        response = client.get('/plans/2025')
        assert response.status_code == 200
        assert b'Yearly Plan: 2025' in response.data

    def test_create_plan_page(self, client):
        response = client.get('/plans/create?year=2025')
        assert response.status_code == 200
        assert b'Create Yearly Plan' in response.data

    def test_create_plan_from_template_page(self, client, sample_variety):
        response = client.get('/plans/create-from-template/2025')
        assert response.status_code == 200
        assert b'Create Plan from Previous Year' in response.data

    def test_create_plan_post(self, client, sample_variety):
        response = client.post('/plans/create', data={
            'year': '2025',
            'variety_id': str(sample_variety),
            'planned_quantity': '15',
            'planned_sowing_date': '2025-04-15',
            'notes': 'My plan',
            'status': 'draft'
        }, follow_redirects=True)
        assert response.status_code == 200
        assert b'Plan created successfully' in response.data

    def test_edit_plan(self, client, sample_variety, app):
        # Create a plan first
        with app.app_context():
            variety = Variety.query.get(sample_variety)
            plan = YearlyPlan(
                year=2025,
                variety_id=variety.id,
                planned_quantity=10,
                planned_sowing_date=date(2025, 4, 15),
                status='draft'
            )
            db.session.add(plan)
            db.session.commit()
            plan_id = plan.id
        
        response = client.post(f'/plans/{plan_id}/edit', data={
            'year': '2025',
            'variety_id': str(sample_variety),
            'planned_quantity': '20',
            'planned_sowing_date': '2025-05-01',
            'notes': 'Updated',
            'status': 'finalized'
        }, follow_redirects=True)
        assert response.status_code == 200
        assert b'Plan updated successfully' in response.data
        
        with app.app_context():
            updated = YearlyPlan.query.get(plan_id)
            assert updated.planned_quantity == 20
            assert updated.status == 'finalized'

    def test_delete_plan(self, client, sample_variety, app):
        with app.app_context():
            variety = Variety.query.get(sample_variety)
            plan = YearlyPlan(
                year=2025,
                variety_id=variety.id,
                planned_quantity=10,
                planned_sowing_date=date(2025, 4, 15),
                status='draft'
            )
            db.session.add(plan)
            db.session.commit()
            plan_id = plan.id
        
        response = client.post(f'/plans/{plan_id}/delete', follow_redirects=True)
        assert response.status_code == 200
        assert b'Plan deleted' in response.data
        
        with app.app_context():
            assert YearlyPlan.query.get(plan_id) is None

    def test_create_from_template(self, client, sample_variety, app):
        # Create a previous year's planting
        with app.app_context():
            variety = Variety.query.get(sample_variety)
            planting = Planting(
                variety_id=variety.id,
                year=2024,
                quantity=25,
                planting_date=date(2024, 4, 20)
            )
            db.session.add(planting)
            db.session.commit()
            planting_id = planting.id
        
        response = client.post('/plans/create-from-template/2025', data={
            'source_year': '2024',
            'selected_plantings': [str(planting_id)]
        }, follow_redirects=True)
        assert response.status_code == 200
        assert b'Plan created from template' in response.data
        
        with app.app_context():
            plan = YearlyPlan.query.filter_by(year=2025).first()
            assert plan is not None
            assert plan.planned_quantity == 25

class TestYearlyPlanReportSorting:
    def test_sort_by_sowing_date_then_family(self, app, sample_variety):
        """Test default sorting: first by sowing date, then by plant family"""
        with app.app_context():
            # Create another variety with different family
            family2 = Variety(
                name='Carrot',
                plant_family='Apiaceae',
                days_to_harvest=70
            )
            family2.set_sowing_months_list([3, 4])
            db.session.add(family2)
            db.session.commit()
            
            variety1 = Variety.query.get(sample_variety)  # Tomato, Solanaceae
            variety2 = family2  # Carrot, Apiaceae
            
            # Create plans with various sowing dates (multiple per variety allowed)
            plan1 = YearlyPlan(year=2025, variety_id=variety1.id, planned_quantity=10,
                             planned_sowing_date=date(2025, 4, 10), status='draft')
            plan2 = YearlyPlan(year=2025, variety_id=variety2.id, planned_quantity=15,
                             planned_sowing_date=date(2025, 4, 10), status='draft')
            plan3 = YearlyPlan(year=2025, variety_id=variety1.id, planned_quantity=5,
                             planned_sowing_date=date(2025, 3, 15), status='draft')
            
            db.session.add_all([plan1, plan2, plan3])
            db.session.commit()
            
            # Fetch sorted plans - default: by sowing date ASC, then family DESC (Z-A)
            sorted_plans = YearlyPlan.query.filter_by(year=2025) \
                .join(Variety).order_by(YearlyPlan.planned_sowing_date.asc(), Variety.plant_family.desc()).all()
            
            # Expected order: plan3 (March 15), plan1 (April 10, Solanaceae), plan2 (April 10, Apiaceae)
            assert sorted_plans[0].id == plan3.id
            assert sorted_plans[1].id == plan1.id  # Solanaceae > Apiaceae alphabetically (descending)
            assert sorted_plans[2].id == plan2.id
