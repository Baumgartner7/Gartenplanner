import pytest
from datetime import datetime, date, timedelta
from database import db
from models import Variety, Planting, YearlyPlan, NotificationSetting, NotificationLog

def test_notification_setting_creation(app):
    """Test creating a notification setting"""
    with app.app_context():
        setting = NotificationSetting(
            email='test@example.com',
            days_before=2,
            enabled=True
        )
        db.session.add(setting)
        db.session.commit()

        assert setting.id is not None
        assert setting.email == 'test@example.com'
        assert setting.days_before == 2
        assert setting.enabled is True

def test_notification_setting_unique_email(app):
    """Test that email must be unique"""
    with app.app_context():
        setting1 = NotificationSetting(email='test@example.com', days_before=1)
        setting2 = NotificationSetting(email='test@example.com', days_before=2)
        
        db.session.add(setting1)
        db.session.commit()
        
        db.session.add(setting2)
        with pytest.raises(Exception):  # UNIQUE constraint failed
            db.session.commit()

def test_notification_log_creation(app):
    """Test creating notification logs"""
    with app.app_context():
        # Create a plan
        variety = Variety(name='Test Carrot', plant_family='Apiaceae')
        db.session.add(variety)
        db.session.commit()

        planting = Planting(
            variety_id=variety.id,
            year=2025,
            quantity=10,
            planting_date=date(2025, 4, 1)
        )
        db.session.add(planting)
        db.session.commit()

        plan = YearlyPlan(
            year=2025,
            variety_id=variety.id,
            planned_quantity=10,
            planned_sowing_date=date(2025, 4, 15),
            status='finalized'
        )
        db.session.add(plan)
        db.session.commit()

        # Create a notification log
        log = NotificationLog(
            yearly_plan_id=plan.id,
            notification_type='sowing',
            status='sent'
        )
        db.session.add(log)
        db.session.commit()

        assert log.id is not None
        assert log.yearly_plan_id == plan.id
        assert log.status == 'sent'

def test_notification_check_route(app, client, monkeypatch):
    """Test the notifications/check endpoint"""
    with app.app_context():
        # Create settings
        setting = NotificationSetting(
            email='test@example.com',
            days_before=1,
            enabled=True
        )
        db.session.add(setting)
        
        # Create a plan due tomorrow
        variety = Variety(name='Test Tomato', plant_family='Solanaceae')
        db.session.add(variety)
        db.session.commit()

        tomorrow = date.today() + timedelta(days=1)
        plan = YearlyPlan(
            year=tomorrow.year,
            variety_id=variety.id,
            planned_quantity=5,
            planned_sowing_date=tomorrow,
            status='finalized'
        )
        db.session.add(plan)
        db.session.commit()

        # Mock the mail sending to avoid actual email
        def mock_mail_send(self, msg):
            pass

        from flask_mail import Mail
        monkeypatch.setattr(Mail, 'send', mock_mail_send, raising=True)

        response = client.get('/notifications/check')
        assert response.status_code == 200
        # Check that a log was created
        log = NotificationLog.query.filter_by(yearly_plan_id=plan.id).first()
        assert log is not None
        assert log.status == 'sent'

def test_notification_check_disabled(app, client):
    """Test that notifications are not sent when disabled"""
    with app.app_context():
        setting = NotificationSetting(
            email='test@example.com',
            days_before=1,
            enabled=False  # Disabled
        )
        db.session.add(setting)
        db.session.commit()

        response = client.get('/notifications/check')
        assert response.status_code == 200
        json_data = response.get_json()
        assert json_data['status'] == 'disabled'

def test_notification_duplicate_prevention(app, client, monkeypatch):
    """Test that notifications aren't sent twice for same plan within 1 day"""
    with app.app_context():
        setting = NotificationSetting(email='test@example.com', days_before=1, enabled=True)
        db.session.add(setting)
        
        variety = Variety(name='Test Pepper', plant_family='Solanaceae')
        db.session.add(variety)
        db.session.commit()

        tomorrow = date.today() + timedelta(days=1)
        plan = YearlyPlan(
            year=tomorrow.year,
            variety_id=variety.id,
            planned_quantity=3,
            planned_sowing_date=tomorrow,
            status='finalized'
        )
        db.session.add(plan)
        db.session.commit()

        # Mock mail
        sent_count = [0]

        def mock_mail_send(self, msg):
            sent_count[0] += 1

        from flask_mail import Mail
        monkeypatch.setattr(Mail, 'send', mock_mail_send, raising=True)

        # First call - should send
        response1 = client.get('/notifications/check')
        assert sent_count[0] == 1

        # Second call soon after - should not send again
        response2 = client.get('/notifications/check')
        assert sent_count[0] == 1  # Still 1, not 2