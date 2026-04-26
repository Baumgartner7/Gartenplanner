from flask import Flask, render_template, request, redirect, url_for, flash, Response, current_app
from flask_mail import Mail
from datetime import datetime, date, timedelta
from database import db
from models import Variety, Planting, Harvest, YearlyPlan, SavedReport, NotificationSetting, NotificationLog
import csv
import io
import re
import os
import json

mail = Mail()

def create_app():
    app = Flask(__name__)
    app.secret_key = 'gartenplanner-secret-key-change-in-production'
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///garden.db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    # Flask-Mail configuration (use environment variables in production)
    app.config['MAIL_SERVER'] = os.getenv('MAIL_SERVER', 'localhost')
    app.config['MAIL_PORT'] = int(os.getenv('MAIL_PORT', 25))
    app.config['MAIL_USE_TLS'] = os.getenv('MAIL_USE_TLS', 'false').lower() == 'true'
    app.config['MAIL_USE_SSL'] = os.getenv('MAIL_USE_SSL', 'false').lower() == 'true'
    app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME')
    app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD')
    app.config['MAIL_DEFAULT_SENDER'] = os.getenv('MAIL_DEFAULT_SENDER', 'gardener@example.com')

    # Make datetime available in all templates
    app.jinja_env.globals['datetime'] = datetime

    db.init_app(app)
    mail.init_app(app)

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

    # Yearly Plan routes
    @app.route('/plans/<int:year>')
    def plan_year(year):
        """View yearly planting plan with sorting"""
        sort_by = request.args.get('sort', 'date')  # 'date' or 'family'
        # Use database ordering for consistency with tests
        if sort_by == 'family':
            plans = YearlyPlan.query.filter_by(year=year).join(
                Variety, YearlyPlan.variety_id == Variety.id
            ).order_by(Variety.plant_family.asc(), YearlyPlan.planned_sowing_date.asc()).all()
        else:  # default: by sowing date ASCENDING, then family DESCENDING
            plans = YearlyPlan.query.filter_by(year=year).join(
                Variety, YearlyPlan.variety_id == Variety.id
            ).order_by(YearlyPlan.planned_sowing_date.asc(), Variety.plant_family.desc()).all()
        
        total_quantity = sum(p.planned_quantity for p in plans)
        distinct_varieties = len(set(p.variety_id for p in plans))
        
        return render_template('yearly_plans/report.html', year=year, plans=plans,
                               total_quantity=total_quantity, distinct_varieties=distinct_varieties,
                               current_sort=sort_by)

    @app.route('/plans/create', methods=['GET', 'POST'])
    def plan_create():
        """Create a single plan entry"""
        varieties = Variety.query.order_by(Variety.name).all()
        if request.method == 'POST':
            variety_id = request.form.get('variety_id')
            year = request.form.get('year', type=int)
            planned_quantity = request.form.get('planned_quantity', type=int)
            sowing_date_str = request.form.get('planned_sowing_date')
            notes = request.form.get('notes', '').strip() or None
            status = request.form.get('status', 'draft')
            
            # Parse sowing date if provided
            planned_sowing_date = None
            if sowing_date_str:
                try:
                    planned_sowing_date = datetime.strptime(sowing_date_str, '%Y-%m-%d').date()
                except ValueError:
                    flash('Invalid sowing date format.', 'error')
                    return render_template('yearly_plans/create.html', varieties=varieties)
            
            plan = YearlyPlan(
                year=year,
                variety_id=int(variety_id),
                planned_quantity=planned_quantity,
                planned_sowing_date=planned_sowing_date,
                notes=notes,
                status=status
            )
            
            if not plan.validate():
                flash('Invalid plan data. Check quantity and status.', 'error')
                return render_template('yearly_plans/create.html', varieties=varieties)
            
            db.session.add(plan)
            try:
                db.session.commit()
                flash('Plan created successfully!', 'success')
                return redirect(url_for('plan_year', year=year))
            except Exception as e:
                db.session.rollback()
                flash(f'Error creating plan: {str(e)}', 'error')
        
        # Pre-select year if provided as query param
        selected_year = request.args.get('year', type=int)
        return render_template('yearly_plans/create.html', varieties=varieties, selected_year=selected_year)

    @app.route('/plans/<int:id>/edit', methods=['GET', 'POST'])
    def plan_edit(id):
        plan = YearlyPlan.query.get_or_404(id)
        varieties = Variety.query.order_by(Variety.name).all()
        if request.method == 'POST':
            variety_id = request.form.get('variety_id')
            year = request.form.get('year', type=int)
            planned_quantity = request.form.get('planned_quantity', type=int)
            sowing_date_str = request.form.get('planned_sowing_date')
            notes = request.form.get('notes', '').strip() or None
            status = request.form.get('status', 'draft')
            
            planned_sowing_date = None
            if sowing_date_str:
                try:
                    planned_sowing_date = datetime.strptime(sowing_date_str, '%Y-%m-%d').date()
                except ValueError:
                    flash('Invalid sowing date format.', 'error')
                    return render_template('yearly_plans/edit.html', plan=plan, varieties=varieties)
            
            plan.variety_id = int(variety_id)
            plan.year = year
            plan.planned_quantity = planned_quantity
            plan.planned_sowing_date = planned_sowing_date
            plan.notes = notes
            plan.status = status
            
            if not plan.validate():
                flash('Invalid plan data. Check quantity and status.', 'error')
                return render_template('yearly_plans/edit.html', plan=plan, varieties=varieties)
            
            try:
                db.session.commit()
                flash('Plan updated successfully!', 'success')
                return redirect(url_for('plan_year', year=plan.year))
            except Exception as e:
                db.session.rollback()
                flash(f'Error updating plan: {str(e)}', 'error')
        
        return render_template('yearly_plans/edit.html', plan=plan, varieties=varieties)

    @app.route('/plans/<int:id>/delete', methods=['POST'])
    def plan_delete(id):
        plan = YearlyPlan.query.get_or_404(id)
        year = plan.year
        db.session.delete(plan)
        db.session.commit()
        flash('Plan deleted.', 'success')
        return redirect(url_for('plan_year', year=year))

    @app.route('/plans/create-from-template/<int:target_year>', methods=['GET', 'POST'])
    def plan_create_from_template(target_year):
        """Create plan entries from previous year's plantings"""
        # Get available years with plantings
        available_years = db.session.query(Planting.year).distinct().order_by(Planting.year.desc()).all()
        available_years = [y[0] for y in available_years]
        
        if request.method == 'POST':
            source_year = request.form.get('source_year', type=int)
            selected_planting_ids = request.form.getlist('selected_plantings')
            
            if not source_year or not selected_planting_ids:
                flash('Please select a source year and at least one planting.', 'error')
                return render_template('yearly_plans/create_from_template.html', 
                                     target_year=target_year, available_years=available_years)
            
            # Get selected plantings
            plantings = Planting.query.filter(
                Planting.id.in_(selected_planting_ids),
                Planting.year == source_year
            ).options(db.joinedload(Planting.variety)).all()
            
            plans_created = 0
            for planting in plantings:
                # Check if plan already exists for this variety in target year
                existing = YearlyPlan.query.filter_by(
                    year=target_year,
                    variety_id=planting.variety_id
                ).first()
                if existing:
                    continue  # Skip duplicates
                
                # Create plan from planting
                plan = YearlyPlan(
                    year=target_year,
                    variety_id=planting.variety_id,
                    planned_quantity=planting.quantity,
                    planned_sowing_date=planting.planting_date,  # Use actual planting date as planned
                    notes=f'Copied from {source_year} planting',
                    status='draft'
                )
                db.session.add(plan)
                plans_created += 1
            
            try:
                db.session.commit()
                flash(f'Plan created from template: {plans_created} entries from {source_year}.', 'success')
                return redirect(url_for('plan_year', year=target_year))
            except Exception as e:
                db.session.rollback()
                flash(f'Error creating plans: {str(e)}', 'error')
        
        # GET: show selection form
        source_year = request.args.get('source_year', type=int)
        plantings = []
        if source_year:
            plantings = Planting.query.filter_by(year=source_year).options(
                db.joinedload(Planting.variety)
            ).order_by(Planting.planting_date).all()
        
        return render_template('yearly_plans/create_from_template.html',
                             target_year=target_year, available_years=available_years,
                             source_year=source_year, plantings=plantings)

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
                # Update the variety's harvest stats after adding a harvest
                update_variety_harvest_stats(planting.variety_id)
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
                # Update the variety's harvest stats after editing a harvest
                update_variety_harvest_stats(planting.variety_id)
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
        variety_id = harvest.planting.variety_id
        db.session.delete(harvest)
        db.session.commit()
        # Update the variety's harvest stats after deleting a harvest
        update_variety_harvest_stats(variety_id)
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

    @app.route('/reports/<int:year>/export-pdf')
    def export_year_pdf(year):
        """Generate PDF report for a specific year"""
        from weasyprint import HTML

        plantings = Planting.query.filter_by(year=year).options(
            db.joinedload(Planting.variety),
            db.joinedload(Planting.harvests)
        ).order_by(Planting.planting_date).all()

        # Calculate summary stats
        total_quantity = sum(p.quantity for p in plantings)
        total_varieties = len(set(p.variety_id for p in plantings))

        # Render HTML template for PDF
        html_string = render_template(
            'reports/pdf_year.html',
            year=year,
            plantings=plantings,
            total_quantity=total_quantity,
            total_varieties=total_varieties,
            datetime=datetime
        )

        # Generate PDF
        pdf = HTML(string=html_string).write_pdf()

        # Save PDF to instance directory
        instance_dir = current_app.instance_path
        os.makedirs(instance_dir, exist_ok=True)
        pdf_filename = f'garden_report_{year}.pdf'
        pdf_path = os.path.join(instance_dir, pdf_filename)

        with open(pdf_path, 'wb') as f:
            f.write(pdf)

        # Record saved report
        saved_report = SavedReport(
            year=year,
            format='pdf',
            file_path=pdf_path,
            notes=f'Generated on {datetime.utcnow().strftime("%Y-%m-%d %H:%M")}'
        )
        db.session.add(saved_report)
        db.session.commit()

        # Send file as response
        return Response(
            pdf,
            mimetype='application/pdf',
            headers={'Content-Disposition': f'attachment;filename={pdf_filename}'}
        )

    @app.route('/reports/saved')
    def saved_reports_list():
        """List all saved reports"""
        reports = SavedReport.query.order_by(SavedReport.generated_at.desc()).all()
        return render_template('reports/saved.html', reports=reports)

    @app.route('/reports/<int:year>/generate-pdf')
    def generate_pdf_report(year):
        """Generate and save a PDF report (without immediate download)"""
        from weasyprint import HTML

        plantings = Planting.query.filter_by(year=year).options(
            db.joinedload(Planting.variety),
            db.joinedload(Planting.harvests)
        ).order_by(Planting.planting_date).all()

        total_quantity = sum(p.quantity for p in plantings)
        total_varieties = len(set(p.variety_id for p in plantings))

        html_string = render_template(
            'reports/pdf_year.html',
            year=year,
            plantings=plantings,
            total_quantity=total_quantity,
            total_varieties=total_varieties,
            datetime=datetime
        )

        pdf = HTML(string=html_string).write_pdf()

        instance_dir = current_app.instance_path
        os.makedirs(instance_dir, exist_ok=True)
        pdf_filename = f'garden_report_{year}_{datetime.utcnow().strftime("%Y%m%d_%H%M%S")}.pdf'
        pdf_path = os.path.join(instance_dir, pdf_filename)

        with open(pdf_path, 'wb') as f:
            f.write(pdf)

        saved_report = SavedReport(
            year=year,
            format='pdf',
            file_path=pdf_path,
            notes=f'Generated manually on {datetime.utcnow().strftime("%Y-%m-%d %H:%M")}'
        )
        db.session.add(saved_report)
        db.session.commit()

        flash(f'PDF report for {year} generated and saved.', 'success')
        return redirect(url_for('saved_reports_list'))

    # Notification Settings
    @app.route('/notifications/settings', methods=['GET', 'POST'])
    def notification_settings():
        """Manage notification email settings"""
        settings = NotificationSetting.query.first()
        if not settings:
            settings = NotificationSetting(
                emails=json.dumps([current_app.config.get('MAIL_DEFAULT_SENDER', 'gardener@example.com')]),
                days_before=1,
                enabled=True
            )
            db.session.add(settings)
            db.session.commit()

        if request.method == 'POST':
            emails_input = request.form.get('emails', '').strip()
            days_before = request.form.get('days_before', type=int, default=1)
            enabled = request.form.get('enabled') == 'on'

            # Parse emails (comma-separated)
            emails_list = [email.strip() for email in emails_input.split(',') if email.strip()]
            
            settings.set_emails_list(emails_list)
            settings.days_before = days_before
            settings.enabled = enabled

            try:
                db.session.commit()
                flash('Notification settings updated!', 'success')
            except Exception as e:
                db.session.rollback()
                flash(f'Error updating settings: {str(e)}', 'error')

        return render_template('notifications/settings.html', settings=settings)

    @app.route('/notifications/check')
    def notifications_check():
        """Check for upcoming sowings and send notifications (called by cron)"""
        from flask_mail import Message

        # Get settings
        settings = NotificationSetting.query.first()
        if not settings or not settings.enabled:
            return {'status': 'disabled', 'message': 'Notifications are disabled'}, 200

        # Get current date and calculate target range
        today = date.today()
        
        # Find all planting plans that are due in the next N days
        upcoming_plans = YearlyPlan.query.filter(
            YearlyPlan.status == 'finalized',
            YearlyPlan.planned_sowing_date >= today,
            YearlyPlan.planned_sowing_date <= today + timedelta(days=settings.days_before)
        ).all()

        notifications_sent = 0

        for plan in upcoming_plans:
            # Check if we already sent a notification for this plan recently
            recent_log = NotificationLog.query.filter(
                NotificationLog.yearly_plan_id == plan.id,
                NotificationLog.notification_type == 'sowing',
                NotificationLog.sent_at >= datetime.utcnow() - timedelta(days=1)
            ).first()
            
            if recent_log:
                continue  # Already sent recently

            try:
                msg = Message(
                    subject=f"Gartenplanner: Sowing Reminder - {plan.variety.name}",
                    recipients=settings.get_emails_list(),
                    html=f"""
                    <h2>Sowing Reminder</h2>
                    <p>It's time to sow <strong>{plan.variety.name}</strong> ({plan.variety.plant_family or 'Unknown family'}).</p>
                    <ul>
                        <li><strong>Planned Sowing Date:</strong> {plan.planned_sowing_date.strftime('%Y-%m-%d')}</li>
                        <li><strong>Planned Quantity:</strong> {plan.planned_quantity}</li>
                        <li><strong>Notes:</strong> {plan.notes or 'None'}</li>
                    </ul>
                    <p>This reminder is {settings.days_before} day(s) before the planned sowing date.</p>
                    """
                )
                mail.send(msg)
                
                # Log successful notification
                log = NotificationLog(
                    yearly_plan_id=plan.id,
                    notification_type='sowing',
                    status='sent'
                )
                db.session.add(log)
                notifications_sent += 1
            except Exception as e:
                # Log error
                log = NotificationLog(
                    yearly_plan_id=plan.id,
                    notification_type='sowing',
                    status='failed',
                    error_message=str(e)
                )
                db.session.add(log)

        db.session.commit()

        return {
            'status': 'ok',
            'notifications_sent': notifications_sent,
            'total_checked': len(upcoming_plans)
        }, 200

    # CLI Commands
    @app.cli.command('send-year-end')
    def send_year_end_email():
        """Send year-end summary email to all users with opted-in users"""
        from flask_mail import Message
        from sqlalchemy.orm import joinedload

        # Get notification settings
        settings = NotificationSetting.query.first()
        if not settings or not settings.enabled:
            print('Notifications are disabled. Enable them in settings first.')
            return

        # Get previous year
        current_year = datetime.utcnow().year
        previous_year = current_year - 1

        # Get all plantings from previous year with variety and harvest data
        plantings = Planting.query.filter_by(year=previous_year).options(
            joinedload(Planting.variety),
            joinedload(Planting.harvests)
        ).order_by(Planting.planting_date).all()

        if not plantings:
            print(f'No plantings found for {previous_year}. Nothing to report.')
            return

        # Generate summary statistics
        total_quantity = sum(p.quantity for p in plantings)
        total_varieties = len(set(p.variety_id for p in plantings))
        
        # Build HTML email
        html_content = f"""
        <html>
        <body>
            <h2>Gartenplanner - Year-End Summary {previous_year}</h2>
            <p>Here's your gardening summary for {previous_year}:</p>
            <ul>
                <li><strong>Total Varieties Planted:</strong> {total_varieties}</li>
                <li><strong>Total Plants/Seeds:</strong> {total_quantity}</li>
                <li><strong>Total Plantings:</strong> {len(plantings)}</li>
            </ul>
            <h3>Planting Details</h3>
            <table border="1" cellpadding="5" cellspacing="0">
                <tr><th>Variety</th><th>Quantity</th><th>Planting Date</th><th>Harvest Notes</th></tr>
        """
        
        for planting in plantings:
            harvest_summary = ', '.join(h.notes or 'No notes' for h in planting.harvests) if planting.harvests else 'No harvest recorded'
            html_content += f"""
                <tr>
                    <td>{planting.variety.name}</td>
                    <td>{planting.quantity}</td>
                    <td>{planting.planting_date.strftime('%Y-%m-%d')}</td>
                    <td>{harvest_summary}</td>
                </tr>
            """
        
        html_content += """
            </table>
            <p>Thank you for using Gartenplanner!</p>
        </body>
        </html>
        """

        # Send email
        try:
            msg = Message(
                subject=f"Gartenplanner Year-End Summary {previous_year}",
                recipients=settings.get_emails_list(),
                html=html_content
            )
            mail.send(msg)
            print(f'Year-end email sent successfully to {settings.get_emails_list()}')
        except Exception as e:
            print(f'Failed to send year-end email: {str(e)}')

    return app

def update_variety_harvest_stats(variety_id):
    """Update the average days-to-harvest for a variety based on all its harvests"""
    # This function may be called within an existing transaction, so don't create a new one
    variety = Variety.query.get(variety_id)
    if not variety:
        return

    # Get all harvests for this variety (through any planting)
    harvests = Harvest.query.join(
        Planting, Harvest.planting_id == Planting.id
    ).filter(
        Planting.variety_id == variety_id
    ).all()

    if harvests:
        total_days = sum(h.get_days_to_harvest() for h in harvests if h.get_days_to_harvest() is not None)
        count = sum(1 for h in harvests if h.get_days_to_harvest() is not None)
        if count > 0:
            variety.days_to_harvest_actual_avg = total_days / count
        else:
            variety.days_to_harvest_actual_avg = None
    else:
        variety.days_to_harvest_actual_avg = None
    
    # Variety is already in the session, just mark as dirty
    # The caller's transaction will handle the commit

if __name__ == '__main__':
    app = create_app()
    app.run(debug=True)