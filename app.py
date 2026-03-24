from flask import Flask, request, redirect, render_template, render_template_string, Response, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, date
import csv
from io import StringIO
from flask import send_from_directory

# ✅ NEW (for file upload)
import os
from werkzeug.utils import secure_filename


app = Flask(__name__)

# ✅ NEW (upload config)
UPLOAD_FOLDER = 'uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

import os

db_url = os.environ.get('DATABASE_URL')

if db_url and db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://")

app.config['SQLALCHEMY_DATABASE_URI'] = db_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
# ---------------- MODEL ----------------
class Investment(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    type = db.Column(db.String(50))
    start_date = db.Column(db.Date)

    bank_name = db.Column(db.String(100))
    fd_number = db.Column(db.String(100))
    invested_amount = db.Column(db.Float)
    interest_rate = db.Column(db.Float)

    maturity_date = db.Column(db.Date)
    maturity_amount = db.Column(db.Float)

    goal = db.Column(db.String(100))   # NEW
    notes = db.Column(db.String(200)) # NEW

    status = db.Column(db.String(50))

    is_closed = db.Column(db.Boolean, default=False)
    closed_on = db.Column(db.Date)
    closure_amount = db.Column(db.Float)

    receipt_file = db.Column(db.String(200))

with app.app_context():
    db.create_all()


# ---------------- HELPERS ----------------
def days_remaining(maturity_date):
    if not maturity_date:
        return "-"
    delta = (maturity_date - date.today()).days
    return delta

def maturity_status(i):
    if i.is_closed:
        return "Closed"
    d = days_remaining(i.maturity_date)
    if isinstance(d, int):
        if d < 0:
            return "Matured"
        elif d <= 30:
            return "Maturing Soon"
    return "Active"


# ---------------- ADD FD ----------------
@app.route('/test')
def test_form():
    return render_template("add_fd.html", fd=None)



@app.route('/add_investment', methods=['POST'])
def add_investment():
    file = request.files.get('receipt')

    filename = None
    if file and file.filename:
        filename = secure_filename(file.filename)
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

    fd_number = request.form.get('fd_number')

    # 🔴 STEP 3: DUPLICATE CHECK (ADD HERE)
    existing = Investment.query.filter_by(fd_number=fd_number).first()
    if existing:
        return f"<h3>❌ FD Number {fd_number} already exists!</h3><a href='/test'>Go Back</a>"

    # ✅ NORMAL SAVE FLOW
    inv = Investment(
        type="FD",
        start_date=datetime.strptime(request.form.get('start_date'), "%Y-%m-%d") if request.form.get('start_date') else date.today(),

        bank_name=request.form.get('bank_name'),
        fd_number=fd_number,
        invested_amount=float(request.form.get('invested_amount') or 0),
        interest_rate=float(request.form.get('interest_rate') or 0),

        maturity_date=datetime.strptime(request.form.get('maturity_date'), "%Y-%m-%d") if request.form.get('maturity_date') else None,
        maturity_amount=float(request.form.get('maturity_amount') or 0),

        goal=request.form.get('goal'),
        notes=request.form.get('notes'),
        receipt_file=filename,
        status="Active"
    )

    db.session.add(inv)
    db.session.commit()

    return redirect('/investments')

# ---------------- DASHBOARD ----------------
@app.route('/investments')
def investments():
    filter_type = request.args.get('filter', 'all')
    all_data = Investment.query.all()

    def match(i):
        s = maturity_status(i)
        if filter_type == 'active':
            return s == "Active"
        elif filter_type == 'matured':
            return s == "Matured"
        elif filter_type == 'closed':
            return s == "Closed"
        return True

    data = [i for i in all_data if match(i)]

    total_invested = sum(i.invested_amount or 0 for i in all_data)
    total_maturity = sum(i.maturity_amount or 0 for i in all_data)
    active_count = sum(1 for i in all_data if maturity_status(i) == "Active")
    closed_count = sum(1 for i in all_data if maturity_status(i) == "Closed")

    bank_summary = {}
    for i in all_data:
        bank_summary[i.bank_name] = bank_summary.get(i.bank_name, 0) + (i.invested_amount or 0)

    return render_template(
        "dashboard.html",
        data=data,
        total_invested=total_invested,
        total_maturity=total_maturity,
        active_count=active_count,
        closed_count=closed_count,
        maturity_status=maturity_status,
        bank_summary=bank_summary
    )


@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/')
def home():
    return redirect('/investments')

@app.route('/delete/<int:id>')
def delete_fd(id):
    fd = Investment.query.get_or_404(id)

    db.session.delete(fd)
    db.session.commit()

    return redirect('/investments')


@app.route('/close/<int:id>')
def close_fd(id):
    fd = Investment.query.get_or_404(id)

    fd.is_closed = True
    fd.closed_on = date.today()

    db.session.commit()

    return redirect('/investments')



@app.route('/edit/<int:id>', methods=['GET', 'POST'])
def edit_fd(id):
    fd = Investment.query.get_or_404(id)

    if request.method == 'POST':
        fd.bank_name = request.form.get('bank_name')
        fd.fd_number = request.form.get('fd_number')

        fd.start_date = datetime.strptime(request.form.get('start_date'), "%Y-%m-%d") if request.form.get('start_date') else None

        fd.invested_amount = float(request.form.get('invested_amount') or 0)
        fd.interest_rate = float(request.form.get('interest_rate') or 0)

        fd.maturity_date = datetime.strptime(request.form.get('maturity_date'), "%Y-%m-%d") if request.form.get('maturity_date') else None
        fd.maturity_amount = float(request.form.get('maturity_amount') or 0)

        fd.goal = request.form.get('goal')
        fd.notes = request.form.get('notes')

        db.session.commit()

        return redirect('/investments')

    return render_template("add_fd.html", fd=fd)
# ---------------- EXPORT ----------------
@app.route('/export')
def export():
    si = StringIO()
    cw = csv.writer(si)

    data = Investment.query.all()

    # HEADER
    cw.writerow([
        'FD Number', 'Bank', 'Start Date', 'Maturity Date',
        'Principal', 'Maturity Amount', 'Interest %',
        'Days Remaining', 'Status', 'Goal', 'Notes'
    ])

    # DATA ROWS
    for i in data:
        days = days_remaining(i.maturity_date)
        status = maturity_status(i)

        cw.writerow([
            i.fd_number,
            i.bank_name,
            i.start_date,
            i.maturity_date,
            i.invested_amount,
            i.maturity_amount,
            i.interest_rate,
            days,
            status,
            i.goal,
            i.notes
        ])

    # ---------------- SUMMARY ----------------
    cw.writerow([])
    cw.writerow(['SUMMARY'])

    total_invested = sum(i.invested_amount or 0 for i in data)
    total_maturity = sum(i.maturity_amount or 0 for i in data)
    active_count = sum(1 for i in data if maturity_status(i) == "Active")
    closed_count = sum(1 for i in data if maturity_status(i) == "Closed")

    cw.writerow(['Total Invested', total_invested])
    cw.writerow(['Total Maturity', total_maturity])
    cw.writerow(['Active FDs', active_count])
    cw.writerow(['Closed FDs', closed_count])

    # ---------------- BANK SUMMARY ----------------
    cw.writerow([])
    cw.writerow(['Bank-wise Summary'])

    bank_summary = {}
    for i in data:
        bank_summary[i.bank_name] = bank_summary.get(i.bank_name, 0) + (i.invested_amount or 0)

    for bank, amt in bank_summary.items():
        cw.writerow([bank, amt])

    output = si.getvalue()

    return Response(
        output,
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment;filename=fd_full_report.csv"}
    )

if __name__ == '__main__':
    app.run(debug=True)