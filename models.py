from datetime import datetime
from database import db
import json

class Variety(db.Model):
    __tablename__ = 'varieties'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False, unique=True)
    plant_family = db.Column(db.String(100), nullable=True)
    optimal_sowing_months = db.Column(db.String(100), nullable=True)  # JSON array as string
    outdoor_spacing_cm = db.Column(db.Integer, nullable=True)
    indoor_pod_size_cm = db.Column(db.Integer, nullable=True)
    days_to_harvest = db.Column(db.Integer, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    plantings = db.relationship('Planting', backref='variety', cascade='all, delete-orphan')

    def validate_sowing_months(self):
        if not self.optimal_sowing_months:
            return
        try:
            months = json.loads(self.optimal_sowing_months)
            if not isinstance(months, list):
                raise ValueError("Must be a list")
            for m in months:
                if not isinstance(m, int) or m < 1 or m > 12:
                    return False
        except (json.JSONDecodeError, ValueError):
            return False
        return True

    def get_sowing_months_list(self):
        if not self.optimal_sowing_months:
            return []
        try:
            return json.loads(self.optimal_sowing_months)
        except json.JSONDecodeError:
            return []

    def set_sowing_months_list(self, months_list):
        self.optimal_sowing_months = json.dumps(months_list)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'plant_family': self.plant_family,
            'optimal_sowing_months': self.get_sowing_months_list(),
            'outdoor_spacing_cm': self.outdoor_spacing_cm,
            'indoor_pod_size_cm': self.indoor_pod_size_cm,
            'days_to_harvest': self.days_to_harvest,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class Planting(db.Model):
    __tablename__ = 'plantings'

    id = db.Column(db.Integer, primary_key=True)
    variety_id = db.Column(db.Integer, db.ForeignKey('varieties.id'), nullable=False)
    year = db.Column(db.Integer, nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    planting_date = db.Column(db.Date, nullable=False)
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    harvests = db.relationship('Harvest', backref='planting', cascade='all, delete-orphan')

    def validate_dates(self):
        if not self.planting_date:
            return False
        if self.year != self.planting_date.year:
            return False
        if self.quantity <= 0:
            return False
        return True

    def to_dict(self):
        return {
            'id': self.id,
            'variety_id': self.variety_id,
            'year': self.year,
            'quantity': self.quantity,
            'planting_date': self.planting_date.isoformat() if self.planting_date else None,
            'notes': self.notes,
            'variety_name': self.variety.name if self.variety else None
        }


class Harvest(db.Model):
    __tablename__ = 'harvests'

    id = db.Column(db.Integer, primary_key=True)
    planting_id = db.Column(db.Integer, db.ForeignKey('plantings.id'), nullable=False)
    first_harvest_date = db.Column(db.Date, nullable=False)
    last_harvest_date = db.Column(db.Date, nullable=True)
    quantity_harvested = db.Column(db.String(200), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def validate_dates(self):
        if not self.first_harvest_date:
            return False
        if self.last_harvest_date and self.last_harvest_date < self.first_harvest_date:
            return False
        # Check that harvest is after planting (same day not allowed)
        planting = Planting.query.get(self.planting_id)
        if planting and self.first_harvest_date <= planting.planting_date:
            return False
        if planting and self.last_harvest_date and self.last_harvest_date <= planting.planting_date:
            return False
        return True

    def to_dict(self):
        return {
            'id': self.id,
            'planting_id': self.planting_id,
            'first_harvest_date': self.first_harvest_date.isoformat() if self.first_harvest_date else None,
            'last_harvest_date': self.last_harvest_date.isoformat() if self.last_harvest_date else None,
            'quantity_harvested': self.quantity_harvested,
            'notes': self.notes
        }