import pytest
from datetime import datetime, date
from database import db
from models import Variety, Planting, SavedReport

def test_saved_report_creation(app):
    """Test creating a saved report"""
    with app.app_context():
        report = SavedReport(
            year=2025,
            format='pdf',
            file_path='/app/instance/garden_report_2025.pdf',
            notes='Test report'
        )
        db.session.add(report)
        db.session.commit()

        assert report.id is not None
        assert report.year == 2025
        assert report.format == 'pdf'
        assert report.file_path == '/app/instance/garden_report_2025.pdf'

def test_saved_report_to_dict(app):
    """Test SavedReport serialization"""
    with app.app_context():
        report = SavedReport(
            year=2025,
            format='csv',
            file_path='/app/instance/garden_report_2025.csv'
        )
        db.session.add(report)
        db.session.commit()

        data = report.to_dict()
        assert data['year'] == 2025
        assert data['format'] == 'csv'
        assert 'file_path' in data
        assert 'generated_at' in data

def test_saved_report_list_route(app, client):
    """Test the saved reports list page"""
    with app.app_context():
        report = SavedReport(year=2025, format='pdf', file_path='/tmp/test.pdf')
        db.session.add(report)
        db.session.commit()

        response = client.get('/reports/saved')
        assert response.status_code == 200
        assert b'Saved Reports' in response.data or b'saved' in response.data.lower()

def test_generate_pdf_report_route(app, client):
    """Test generating a PDF report"""
    with app.app_context():
        # Create test data
        variety = Variety(name='Test Tomato', plant_family='Solanaceae')
        db.session.add(variety)
        db.session.commit()

        planting = Planting(
            variety_id=variety.id,
            year=2025,
            quantity=5,
            planting_date=date(2025, 5, 15)
        )
        db.session.add(planting)
        db.session.commit()

        response = client.get(f'/reports/2025/generate-pdf', follow_redirects=True)
        assert response.status_code == 200
        assert b'Saved Reports' in response.data or b'saved reports' in response.data.lower()

def test_generate_pdf_creates_saved_report(app):
    """Test that generating a PDF creates a SavedReport record"""
    with app.app_context():
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

        # Use the generate_pdf_report function directly
        with app.test_request_context():
            from flask import url_for
            # We'll simulate the route call
            response = app.test_client().get(f'/reports/2025/generate-pdf')
            
            # Check that a SavedReport was created
            reports = SavedReport.query.filter_by(year=2025, format='pdf').all()
            assert len(reports) >= 1

def test_export_pdf_route(app, client):
    """Test the PDF export route returns PDF"""
    with app.app_context():
        variety = Variety(name='Test Bean', plant_family='Fabaceae')
        db.session.add(variety)
        db.session.commit()

        planting = Planting(
            variety_id=variety.id,
            year=2025,
            quantity=3,
            planting_date=date(2025, 6, 1)
        )
        db.session.add(planting)
        db.session.commit()

        response = client.get('/reports/2025/export-pdf')
        assert response.status_code == 200
        assert response.content_type == 'application/pdf'
        # PDF should start with %PDF
        assert response.data.startswith(b'%PDF')