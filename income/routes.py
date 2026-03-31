from flask import Blueprint, render_template, request, redirect, url_for
from datetime import datetime
from extensions import db
from income.models import IncomeEntry
from flask import session
from app import login_required
import logging

income_bp = Blueprint('income', __name__, url_prefix='/income')


# 🔷 ADD INCOME
@income_bp.route('/add', methods=['GET', 'POST'])
@login_required
def add_income():
    if request.method == 'POST':
        date = request.form['date']
        source = request.form['source']
        mode = request.form['mode']
        amount = request.form['amount']
        notes = request.form['notes']

        new_entry = IncomeEntry(
            user_id=1,  # temporary (will connect login later)
            date=datetime.strptime(date, "%Y-%m-%d"),
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
from sqlalchemy import func, case, extract


@income_bp.route('/')
@login_required
def income_list():
    entries = IncomeEntry.query.order_by(IncomeEntry.date.desc()).all()

    # 🔷 DAILY SUMMARY
    daily_summary = db.session.query(
        IncomeEntry.date,
        func.sum(case((IncomeEntry.source == 'clinic', IncomeEntry.amount), else_=0)).label('clinic_total'),
        func.sum(case((IncomeEntry.source == 'pharmacy', IncomeEntry.amount), else_=0)).label('pharmacy_total'),
        func.sum(IncomeEntry.amount).label('total')
    ).group_by(IncomeEntry.date).order_by(IncomeEntry.date.desc()).all()

    # 🔷 MONTHLY SUMMARY
    monthly_summary = db.session.query(
        extract('year', IncomeEntry.date).label('year'),
        extract('month', IncomeEntry.date).label('month'),
        func.sum(case((IncomeEntry.source == 'clinic', IncomeEntry.amount), else_=0)).label('clinic_total'),
        func.sum(case((IncomeEntry.source == 'pharmacy', IncomeEntry.amount), else_=0)).label('pharmacy_total'),
        func.sum(IncomeEntry.amount).label('total')
    ).group_by('year', 'month').order_by('year', 'month').all()

    # 🔷 YEARLY SUMMARY
    yearly_summary = db.session.query(
        extract('year', IncomeEntry.date).label('year'),
        func.sum(case((IncomeEntry.source == 'clinic', IncomeEntry.amount), else_=0)).label('clinic_total'),
        func.sum(case((IncomeEntry.source == 'pharmacy', IncomeEntry.amount), else_=0)).label('pharmacy_total'),
        func.sum(IncomeEntry.amount).label('total')
    ).group_by('year').order_by('year').all()

    return render_template(
        'income/income_list.html',
        entries=entries,
        daily_summary=daily_summary,
        monthly_summary=monthly_summary,
        yearly_summary=yearly_summary
    )

# 🔷 DELETE ENTRY
import logging   # ✅ ensure this is at top of file

@income_bp.route('/delete/<int:id>', methods=['POST'])
@login_required
def delete_income(id):
    entry = IncomeEntry.query.get(id)

    if entry:
        # ✅ LOG 1 — BEFORE DELETE
        logging.info(f"Income delete attempt: ID={id}, Amount={entry.amount}, Source={entry.source}")

        db.session.delete(entry)
        db.session.commit()

        # ✅ LOG 2 — AFTER DELETE
        logging.info(f"Income deleted successfully: ID={id}")

    else:
        # ✅ LOG 3 — NOT FOUND (VERY IMPORTANT)
        logging.warning(f"Income delete failed (not found): ID={id}")

    return redirect('/income/')

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