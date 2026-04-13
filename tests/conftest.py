"""pytest fixtures shared across all test files"""
import sys
import os
import uuid
import pytest
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.pool import StaticPool
from database import db
from app import create_app

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


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
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def init_data(app):
    """Create initial test data"""
    from models import Variety, Planting
    from datetime import datetime
    with app.app_context():
        unique_name = f'Test Tomato {uuid.uuid4().hex[:8]}'
        variety = Variety(
            name=unique_name,
            plant_family='Solanaceae',
            days_to_harvest=90
        )
        db.session.add(variety)
        db.session.commit()
        return variety.id
