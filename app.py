from flask import Flask, render_template, request, redirect, url_for, flash, Response
from datetime import datetime
from database import db
from models import Variety, Planting, Harvest
import csv
import io
import re

def create_app():
    app = Flask(__name__)
    app.secret_key = 'gartenplanner-secret-key-change-in-production'
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///garden.db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    # Make datetime available in all templates
    app.jinja_env.globals['datetime'] = datetime

    db.init_app(app)

    with app.app_context():
        db.create_all()

    # Custom filter to extract numeric value from string (e.g., "5 kg" -> 5.0)
    @app.template_filter('extract_number')
    def extract_number(value):
        if not value:
            return 0
        # Remove non-digit characters except decimal point
        match = re.search(r'[\d,.]+', str(value))
        if match:
            # Remove commas and convert to float
            num_str = match.group().replace(',', '.')
            try:
                return float(num_str)
            except ValueError:
                return 0
        return 0

    # Dashboard/Index
    @app.route('/')
    def index():
        variety_count = Variety.query.count()
        planting_count = Planting.query.count()
        harvest_count = Harvest.query.count()
        recent_varieties = Variety.query.order_by(Variety.created_at.desc()).limit(5).all()
        recent_plantings = Planting.query.order_by(Planting.created_at.desc()).limit(5).all()
        return render_template('index.html',
                               variety_count=variety_count,
                               planting_count=planting_count,
                               harvest_count=harvest_count,
                               recent_varieties=recent_varieties,
                               recent_plantings=recent_plantings)

    # Variety routes
    @app.route('/varieties')
    def varieties_list():
        varieties = Variety.query.order_by(Variety.name).all()
        return render_template('varieties/list.html', varieties=varieties)

    @app.route('/varieties/create', methods=['GET', 'POST'])
    def variety_create():
        if request.method == 'POST':
            name = request.form.get('name', '').strip()
            plant_family = request.form.get('plant_family', '').strip() or None
            outdoor_spacing = request.form.get('outdoor_spacing_cm')
            indoor_pod = request.form.get('indoor_pod_size_cm')
            days_to_harvest = request.form.get('days_to_harvest')
            sowing_months = request.form.getlist('sowing_months')

            variety = Variety(
                name=name,
                plant_family=plant_family,
                outdoor_spacing_cm=int(outdoor_spacing) if outdoor_spacing else None,
                indoor_pod_size_cm=int(indoor_pod) if indoor_pod else None,
                days_to_harvest=int(days_to_harvest) if days_to_harvest else None
            )
            if sowing_months:
                variety.set_sowing_months_list([int(m) for m in sowing_months])

            db.session.add(variety)
            try:
                db.session.commit()
                flash(f'Variety "{name}" created successfully!', 'success')
                return redirect(url_for('varieties_list'))
            except Exception as e:
                db.session.rollback()
                if 'UNIQUE constraint' in str(e):
                    flash(f'Variety with name "{name}" already exists.', 'error')
                else:
                    flash(f'Error creating variety: {str(e)}', 'error')

        return render_template('varieties/create.html')

    @app.route('/varieties/<int:id>/edit', methods=['GET', 'POST'])
    def variety_edit(id):
        variety = Variety.query.get_or_404(id)
        if request.method == 'POST':
            name = request.form.get('name', '').strip()
            plant_family = request.form.get('plant_family', '').strip() or None
            outdoor_spacing = request.form.get('outdoor_spacing_cm')
            indoor_pod = request.form.get('indoor_pod_size_cm')
            days_to_harvest = request.form.get('days_to_harvest')
            sowing_months = request.form.getlist('sowing_months')

            variety.name = name
            variety.plant_family = plant_family
            variety.outdoor_spacing_cm = int(outdoor_spacing) if outdoor_spacing else None
            variety.indoor_pod_size_cm = int(indoor_pod) if indoor_pod else None
            variety.days_to_harvest = int(days_to_harvest) if days_to_harvest else None
            variety.set_sowing_months_list([int(m) for m in sowing_months]) if sowing_months else variety.set_sowing_months_list([])

            try:
                db.session.commit()
                flash(f'Variety "{name}" updated successfully!', 'success')
                return redirect(url_for('varieties_list'))
            except Exception as e:
                db.session.rollback()
                if 'UNIQUE constraint' in str(e):
                    flash(f'Variety with name "{name}" already exists.', 'error')
                else:
                    flash(f'Error updating variety: {str(e)}', 'error')

        sowing_months = variety.get_sowing_months_list()
        return render_template('varieties/edit.html', variety=variety, sowing_months=sowing_months)

    @app.route('/varieties/<int:id>/delete', methods=['POST'])
    def variety_delete(id):
        variety = Variety.query.get_or_404(id)
        name = variety.name
        db.session.delete(variety)
        db.session.commit()
        flash(f'Variety "{name}" deleted.', 'success')
        return redirect(url_for('varieties_list'))

    @app.route('/varieties/<int:id>')
    def variety_detail(id):
        variety = Variety.query.get_or_404(id)
        plantings = Planting.query.filter_by(variety_id=id).order_by(Planting.year.desc()).all()
        return render_template('varieties/detail.html', variety=variety, plantings=plantings)

    # Planting routes
    @app.route('/plantings')
    def plantings_list():
        year_filter = request.args.get('year', type=int)
        query = Planting.query
        if year_filter:
            query = query.filter_by(year=year_filter)
        plantings = query.order_by(Planting.planting_date.desc()).all()
        years = db.session.query(Planting.year).distinct().order_by(Planting.year.desc()).all()
        years = [y[0] for y in years]
        return render_template('plantings/list.html', plantings=plantings, years=years, selected_year=year_filter)

    @app.route('/plantings/create', methods=['GET', 'POST'])
    def planting_create():
        varieties = Variety.query.order_by(Variety.name).all()
        if request.method == 'POST':
            variety_id = request.form.get('variety_id')
            year = request.form.get('year', type=int)
            quantity = request.form.get('quantity', type=int)
            planting_date_str = request.form.get('planting_date')
            notes = request.form.get('notes', '').strip() or None

            try:
                planting_date = datetime.strptime(planting_date_str, '%Y-%m-%d').date()
            except (ValueError, TypeError):
                flash('Invalid planting date format.', 'error')
                return render_template('plantings/create.html', varieties=varieties)

            planting = Planting(
                variety_id=int(variety_id),
                year=year,
                quantity=quantity,
                planting_date=planting_date,
                notes=notes
            )

            if not planting.validate_dates():
                flash('Invalid data: check that year matches planting date and quantity is positive.', 'error')
                return render_template('plantings/create.html', varieties=varieties)

            db.session.add(planting)
            try:
                db.session.commit()
                flash('Planting recorded successfully!', 'success')
                return redirect(url_for('plantings_list'))
            except Exception as e:
                db.session.rollback()
                flash(f'Error saving planting: {str(e)}', 'error')

        return render_template('plantings/create.html', varieties=varieties)

    @app.route('/plantings/<int:id>/edit', methods=['GET', 'POST'])
    def planting_edit(id):
        planting = Planting.query.get_or_404(id)
        varieties = Variety.query.order_by(Variety.name).all()
        if request.method == 'POST':
            variety_id = request.form.get('variety_id')
            year = request.form.get('year', type=int)
            quantity = request.form.get('quantity', type=int)
            planting_date_str = request.form.get('planting_date')
            notes = request.form.get('notes', '').strip() or None

            try:
                planting_date = datetime.strptime(planting_date_str, '%Y-%m-%d').date()
            except (ValueError, TypeError):
                flash('Invalid planting date format.', 'error')
                return render_template('plantings/edit.html', planting=planting, varieties=varieties)

            planting.variety_id = int(variety_id)
            planting.year = year
            planting.quantity = quantity
            planting.planting_date = planting_date
            planting.notes = notes

            if not planting.validate_dates():
                flash('Invalid data: check that year matches planting date and quantity is positive.', 'error')
                return render_template('plantings/edit.html', planting=planting, varieties=varieties)

            try:
                db.session.commit()
                flash('Planting updated successfully!', 'success')
                return redirect(url_for('plantings_list'))
            except Exception as e:
                db.session.rollback()
                flash(f'Error updating planting: {str(e)}', 'error')

        return render_template('plantings/edit.html', planting=planting, varieties=varieties)

    @app.route('/plantings/<int:id>/delete', methods=['POST'])
    def planting_delete(id):
        planting = Planting.query.get_or_404(id)
        db.session.delete(planting)
        db.session.commit()
        flash('Planting deleted.', 'success')
        return redirect(url_for('plantings_list'))

    @app.route('/plantings/<int:id>')
    def planting_detail(id):
        planting = Planting.query.get_or_404(id)
        harvests = Harvest.query.filter_by(planting_id=id).order_by(Harvest.first_harvest_date).all()
        return render_template('plantings/detail.html', planting=planting, harvests=harvests)

    # Harvest routes
    @app.route('/plantings/<int:planting_id>/harvests/create', methods=['GET', 'POST'])
    def harvest_create(planting_id):
        planting = Planting.query.get_or_404(planting_id)
        if request.method == 'POST':
            first_harvest_date_str = request.form.get('first_harvest_date')
            last_harvest_date_str = request.form.get('last_harvest_date', '').strip()
            quantity_harvested = request.form.get('quantity_harvested', '').strip() or None
            notes = request.form.get('notes', '').strip() or None

            try:
                first_harvest_date = datetime.strptime(first_harvest_date_str, '%Y-%m-%d').date()
            except (ValueError, TypeError):
                flash('Invalid first harvest date format.', 'error')
                return render_template('harvests/create.html', planting=planting)

            last_harvest_date = None
            if last_harvest_date_str:
                try:
                    last_harvest_date = datetime.strptime(last_harvest_date_str, '%Y-%m-%d').date()
                except ValueError:
                    flash('Invalid last harvest date format.', 'error')
                    return render_template('harvests/create.html', planting=planting)

            harvest = Harvest(
                planting_id=planting_id,
                first_harvest_date=first_harvest_date,
                last_harvest_date=last_harvest_date,
                quantity_harvested=quantity_harvested,
                notes=notes
            )

            if not harvest.validate_dates():
                flash('Invalid dates: harvest must be after planting date, and last harvest cannot be before first.', 'error')
                return render_template('harvests/create.html', planting=planting)

            db.session.add(harvest)
            try:
                db.session.commit()
                flash('Harvest recorded successfully!', 'success')
                return redirect(url_for('planting_detail', id=planting_id))
            except Exception as e:
                db.session.rollback()
                flash(f'Error saving harvest: {str(e)}', 'error')

        return render_template('harvests/create.html', planting=planting)

    @app.route('/harvests/<int:id>/edit', methods=['GET', 'POST'])
    def harvest_edit(id):
        harvest = Harvest.query.get_or_404(id)
        planting = harvest.planting
        if request.method == 'POST':
            first_harvest_date_str = request.form.get('first_harvest_date')
            last_harvest_date_str = request.form.get('last_harvest_date', '').strip()
            quantity_harvested = request.form.get('quantity_harvested', '').strip() or None
            notes = request.form.get('notes', '').strip() or None

            try:
                first_harvest_date = datetime.strptime(first_harvest_date_str, '%Y-%m-%d').date()
            except (ValueError, TypeError):
                flash('Invalid first harvest date format.', 'error')
                return render_template('harvests/edit.html', harvest=harvest, planting=planting)

            last_harvest_date = None
            if last_harvest_date_str:
                try:
                    last_harvest_date = datetime.strptime(last_harvest_date_str, '%Y-%m-%d').date()
                except ValueError:
                    flash('Invalid last harvest date format.', 'error')
                    return render_template('harvests/edit.html', harvest=harvest, planting=planting)

            harvest.first_harvest_date = first_harvest_date
            harvest.last_harvest_date = last_harvest_date
            harvest.quantity_harvested = quantity_harvested
            harvest.notes = notes

            if not harvest.validate_dates():
                flash('Invalid dates: harvest must be after planting date, and last harvest cannot be before first.', 'error')
                return render_template('harvests/edit.html', harvest=harvest, planting=planting)

            try:
                db.session.commit()
                flash('Harvest updated successfully!', 'success')
                return redirect(url_for('planting_detail', id=harvest.planting_id))
            except Exception as e:
                db.session.rollback()
                flash(f'Error updating harvest: {str(e)}', 'error')

        return render_template('harvests/edit.html', harvest=harvest, planting=planting)

    @app.route('/harvests/<int:id>/delete', methods=['POST'])
    def harvest_delete(id):
        harvest = Harvest.query.get_or_404(id)
        planting_id = harvest.planting_id
        db.session.delete(harvest)
        db.session.commit()
        flash('Harvest deleted.', 'success')
        return redirect(url_for('planting_detail', id=planting_id))

    # Reports
    @app.route('/reports/<int:year>')
    def report_year(year):
        from sqlalchemy.orm import joinedload
        plantings = Planting.query.filter_by(year=year).options(
            joinedload(Planting.harvests),
            joinedload(Planting.variety)
        ).order_by(Planting.planting_date).all()
        total_varieties = len(set(p.variety_id for p in plantings))
        total_quantity = sum(p.quantity for p in plantings)
        return render_template('reports/year.html', year=year, plantings=plantings,
                               total_varieties=total_varieties, total_quantity=total_quantity)

    @app.route('/reports/<int:year>/export')
    def export_year(year):
        plantings = Planting.query.filter_by(year=year).order_by(Planting.planting_date).all()

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['Variety', 'Quantity', 'Planting Date', 'Harvest Start', 'Harvest End', 'Harvested Amount', 'Notes'])

        for planting in plantings:
            variety = Variety.query.get(planting.variety_id)
            harvests = Harvest.query.filter_by(planting_id=planting.id).all()
            first_harvest = min(h.first_harvest_date for h in harvests) if harvests else ''
            last_harvest = max(h.last_harvest_date for h in harvests if h.last_harvest_date) if any(h.last_harvest_date for h in harvests) else ''
            total_harvested = ', '.join(h.quantity_harvested for h in harvests if h.quantity_harvested) if any(h.quantity_harvested for h in harvests) else ''

            writer.writerow([
                variety.name if variety else 'Unknown',
                planting.quantity,
                planting.planting_date.strftime('%Y-%m-%d'),
                first_harvest.strftime('%Y-%m-%d') if first_harvest else '',
                last_harvest.strftime('%Y-%m-%d') if last_harvest else '',
                total_harvested,
                planting.notes or ''
            ])

        output.seek(0)
        return Response(
            output.getvalue(),
            mimetype='text/csv',
            headers={'Content-Disposition': f'attachment;filename=garden_report_{year}.csv'}
        )

    return app

if __name__ == '__main__':
    app = create_app()
    app.run(host='0.0.0.0', port=5000, debug=True)