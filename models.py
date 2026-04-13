from datetime import datetime, date
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
    days_to_harvest_actual_avg = db.Column(db.Float, nullable=True)  # Calculated from actual harvests
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    plantings = db.relationship('Planting', backref='variety', cascade='all, delete-orphan')
    yearly_plans = db.relationship('YearlyPlan', backref='variety', cascade='all, delete-orphan')

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
            'days_to_harvest_actual_avg': self.days_to_harvest_actual_avg,
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


class YearlyPlan(db.Model):
    __tablename__ = 'yearly_plans'

    id = db.Column(db.Integer, primary_key=True)
    year = db.Column(db.Integer, nullable=False)
    variety_id = db.Column(db.Integer, db.ForeignKey('varieties.id'), nullable=False)
    planned_quantity = db.Column(db.Integer, nullable=False)
    planned_sowing_date = db.Column(db.Date, nullable=True)
    notes = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(20), nullable=False, default='draft')  # 'draft' or 'finalized'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def validate(self):
        """Validate the yearly plan entry"""
        if not self.variety_id:
            return False
        if self.planned_quantity is None or self.planned_quantity <= 0:
            return False
        if self.status not in ['draft', 'finalized']:
            return False
        if self.planned_sowing_date:
            if self.planned_sowing_date.year != self.year:
                return False
        # Check variety exists
        variety = Variety.query.get(self.variety_id)
        if not variety:
            return False
        return True

    def compute_sowing_date_from_variety(self):
        """Calculate a suggested sowing date based on variety's optimal months"""
        variety = Variety.query.get(self.variety_id)
        if not variety or not variety.optimal_sowing_months:
            return None
        months = variety.get_sowing_months_list()
        if not months:
            return None
        # Use first optimal month, set to middle of month
        first_month = sorted(months)[0]
        # Use 15th of the month, or last day if month has fewer days
        day = min(15, [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][first_month - 1])
        return date(self.year, first_month, day)

    def to_dict(self):
        return {
            'id': self.id,
            'year': self.year,
            'variety_id': self.variety_id,
            'variety_name': self.variety.name if self.variety else None,
            'plant_family': self.variety.plant_family if self.variety else None,
            'planned_quantity': self.planned_quantity,
            'planned_sowing_date': self.planned_sowing_date.isoformat() if self.planned_sowing_date else None,
            'notes': self.notes,
            'status': self.status,
            'created_at': self.created_at.isoformat() if self.created_at else None
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

    def get_days_to_harvest(self):
        """Calculate days from planting to first harvest for this harvest record"""
        if not self.planting or not self.first_harvest_date:
            return None
        return (self.first_harvest_date - self.planting.planting_date).days

    def to_dict(self):
        return {
            'id': self.id,
            'planting_id': self.planting_id,
            'first_harvest_date': self.first_harvest_date.isoformat() if self.first_harvest_date else None,
            'last_harvest_date': self.last_harvest_date.isoformat() if self.last_harvest_date else None,
            'quantity_harvested': self.quantity_harvested,
            'notes': self.notes
        }


class SavedReport(db.Model):
    __tablename__ = 'saved_reports'

    id = db.Column(db.Integer, primary_key=True)
    year = db.Column(db.Integer, nullable=False)
    format = db.Column(db.String(10), nullable=False)  # 'pdf' or 'csv'
    file_path = db.Column(db.String(500), nullable=True)  # Path to stored file if saved to disk
    generated_at = db.Column(db.DateTime, default=datetime.utcnow)
    notes = db.Column(db.Text, nullable=True)

    def to_dict(self):
        return {
            'id': self.id,
            'year': self.year,
            'format': self.format,
            'file_path': self.file_path,
            'generated_at': self.generated_at.isoformat() if self.generated_at else None,
            'notes': self.notes
        }


class NotificationSetting(db.Model):
    __tablename__ = 'notification_settings'

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(200), nullable=False, unique=True)
    days_before = db.Column(db.Integer, nullable=False, default=1)
    enabled = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'email': self.email,
            'days_before': self.days_before,
            'enabled': self.enabled,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class NotificationLog(db.Model):
    __tablename__ = 'notification_logs'

    id = db.Column(db.Integer, primary_key=True)
    planting_id = db.Column(db.Integer, db.ForeignKey('plantings.id'), nullable=True)
    yearly_plan_id = db.Column(db.Integer, db.ForeignKey('yearly_plans.id'), nullable=True)
    notification_type = db.Column(db.String(50), nullable=False)  # 'sowing'
    status = db.Column(db.String(20), nullable=False)  # 'sent' or 'failed'
    error_message = db.Column(db.Text, nullable=True)
    sent_at = db.Column(db.DateTime, default=datetime.utcnow)

    planting = db.relationship('Planting', backref='notification_logs')
    yearly_plan = db.relationship('YearlyPlan', backref='notification_logs')

    def to_dict(self):
        return {
            'id': self.id,
            'planting_id': self.planting_id,
            'yearly_plan_id': self.yearly_plan_id,
            'notification_type': self.notification_type,
            'status': self.status,
            'error_message': self.error_message,
            'sent_at': self.sent_at.isoformat() if self.sent_at else None
        }