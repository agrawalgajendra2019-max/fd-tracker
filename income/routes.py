from flask import Blueprint, render_template, request, redirect, url_for
from datetime import datetime, date   # ✅ FIXED
from extensions import db
from income.models import IncomeEntry
from flask import session
from app import login_required
import logging
from sqlalchemy import func, case, extract

income_bp = Blueprint('income', __name__, url_prefix='/income')


# 🔷 ADD INCOME
@income_bp.route('/add', methods=['GET', 'POST'])
@login_required
def add_income():
    if request.method == 'POST':
        date_val = request.form['date']
        source = request.form['source']
        mode = request.form['mode']
        amount = request.form['amount']
        notes = request.form['notes']

        new_entry = IncomeEntry(
            user_id=1,
            date=datetime.strptime(date_val, "%Y-%m-%d"),
            source=source,
            mode=mode,
            amount=float(amount),
            notes=notes
        )

        db.session.add(new_entry)
        db.session.commit()

        return redirect(url_for('income.income_list'))

    return render_template('income/add_income.html')


# 🔷 LIST ALL ENTRIES
@income_bp.route('/')
@login_required
def income_list():

    entries = IncomeEntry.query.order_by(IncomeEntry.date.desc()).all()
    entries = entries or []

    # 🔷 CARDS
    total_income = sum((e.amount or 0) for e in entries)
    clinic_total = sum((e.amount or 0) for e in entries if e.source == 'clinic')
    pharmacy_total = sum((e.amount or 0) for e in entries if e.source == 'pharmacy')

    today = date.today()

    def safe_date(d):
        if not d:
            return None
        return d if isinstance(d, date) else d.date()

    today_income = sum(
        (e.amount or 0) for e in entries
        if e.date and safe_date(e.date) == today
    )

    # 🔷 EMPTY SUMMARIES (SAFE)
    from collections import defaultdict

    # DAILY SUMMARY
    daily_data = defaultdict(lambda: {"clinic": 0, "pharmacy": 0})

    for e in entries:
        if not e.date:
            continue

        d = e.date.date() if hasattr(e.date, "date") else e.date

        if e.source == 'clinic':
            daily_data[d]["clinic"] += e.amount or 0
        elif e.source == 'pharmacy':
            daily_data[d]["pharmacy"] += e.amount or 0

    daily_summary = []
    for d, val in daily_data.items():
        daily_summary.append({
            "date": d,
            "clinic_total": val["clinic"],
            "pharmacy_total": val["pharmacy"],
            "total": val["clinic"] + val["pharmacy"]
        })

    # MONTHLY SUMMARY
    monthly_data = defaultdict(lambda: {"clinic": 0, "pharmacy": 0})

    for e in entries:
        if not e.date:
            continue

        d = e.date.date() if hasattr(e.date, "date") else e.date
        key = (d.year, d.month)

        if e.source == 'clinic':
            monthly_data[key]["clinic"] += e.amount or 0
        elif e.source == 'pharmacy':
            monthly_data[key]["pharmacy"] += e.amount or 0

    monthly_summary = []
    for (year, month), val in monthly_data.items():
        monthly_summary.append({
            "year": year,
            "month": month,
            "clinic_total": val["clinic"],
            "pharmacy_total": val["pharmacy"],
            "total": val["clinic"] + val["pharmacy"]
        })

    # YEARLY SUMMARY
    yearly_data = defaultdict(lambda: {"clinic": 0, "pharmacy": 0})

    for e in entries:
        if not e.date:
            continue

        d = e.date.date() if hasattr(e.date, "date") else e.date
        year = d.year

        if e.source == 'clinic':
            yearly_data[year]["clinic"] += e.amount or 0
        elif e.source == 'pharmacy':
            yearly_data[year]["pharmacy"] += e.amount or 0

    yearly_summary = []
    for year, val in yearly_data.items():
        yearly_summary.append({
            "year": year,
            "clinic_total": val["clinic"],
            "pharmacy_total": val["pharmacy"],
            "total": val["clinic"] + val["pharmacy"]
        })

    return render_template(
        'income/income_list.html',
        entries=entries,
        daily_summary=daily_summary,
        monthly_summary=monthly_summary,
        yearly_summary=yearly_summary,
        total_income=total_income,
        clinic_total=clinic_total,
        pharmacy_total=pharmacy_total,
        today_income=today_income
    )


# 🔷 DELETE ENTRY
@income_bp.route('/delete/<int:id>', methods=['POST'])
@login_required
def delete_income(id):
    entry = IncomeEntry.query.get(id)

    if entry:
        logging.info(f"Income delete attempt: ID={id}, Amount={entry.amount}, Source={entry.source}")

        db.session.delete(entry)
        db.session.commit()

        logging.info(f"Income deleted successfully: ID={id}")
    else:
        logging.warning(f"Income delete failed (not found): ID={id}")

    return redirect('/income/')


# 🔷 EDIT ENTRY
@income_bp.route('/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_income(id):
    entry = IncomeEntry.query.get_or_404(id)

    if request.method == 'POST':
        entry.date = datetime.strptime(request.form['date'], "%Y-%m-%d")
        entry.source = request.form['source']
        entry.mode = request.form['mode']
        entry.amount = float(request.form['amount'])
        entry.notes = request.form['notes']

        db.session.commit()

        return redirect(url_for('income.income_list'))

    return render_template('income/edit_income.html', entry=entry)

import csv
from flask import Response

@income_bp.route('/export')
@login_required
def export_income():
    entries = IncomeEntry.query.order_by(IncomeEntry.date.desc()).all()

    def generate():
        yield "Date,Source,Mode,Amount,Notes\n"

        for e in entries:
            date_str = e.date.strftime("%Y-%m-%d") if e.date else ""
            source = e.source or ""
            mode = e.mode or ""
            amount = e.amount or 0
            notes = (e.notes or "").replace(",", " ")  # avoid CSV break

            yield f"{date_str},{source},{mode},{amount},{notes}\n"

    return Response(
        generate(),
        mimetype='text/csv',
        headers={"Content-Disposition": "attachment; filename=income.csv"}
    )