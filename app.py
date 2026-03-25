from flask import Flask, request, redirect, render_template, render_template_string, Response, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, date
import csv
from io import StringIO
from flask import send_from_directory
from werkzeug.security import generate_password_hash, check_password_hash

# ✅ NEW (for file upload)
import os
from werkzeug.utils import secure_filename


app = Flask(__name__)
app.secret_key = "mysecret123"

# ✅ NEW (upload config)
UPLOAD_FOLDER = 'uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER


import os

db_url = "sqlite:///investment.db"

if not db_url:
    db_url = "sqlite:///investment.db"

if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://")

app.config['SQLALCHEMY_DATABASE_URI'] = db_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False


db = SQLAlchemy(app)

from flask import session, redirect, request, render_template

USERNAME = "admin"
PASSWORD = "scrypt:32768:8:1$ti4MKlnAZmKgKGgt$4208dba8fbdfef3781b9747f0c1474e18c53249a0f8dbff5e1c5491ea64f18cabaf8a48c81034b3d5dffd0452bf9be6d89e975bf17b4f9a11883236012a1737b"

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form['username']).first()

        if user and check_password_hash(user.password, request.form['password']):
            session['logged_in'] = True
            return redirect('/investments')
        else:
            return "Invalid credentials"

    return render_template('login.html')

from functools import wraps

def login_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if not session.get('logged_in'):
            return redirect('/login')
        return func(*args, **kwargs)
    return wrapper
# ---------------- MODEL ----------------
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(200))


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

    # create default user if not exists
    if not User.query.filter_by(username="admin").first():
        from werkzeug.security import generate_password_hash
        user = User(
            username="admin",
            password=generate_password_hash("1234")
        )
        db.session.add(user)
        db.session.commit()

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
@login_required
def test_form():
    return render_template("add_fd.html", fd=None)



@app.route('/add_investment', methods=['POST'])
@login_required
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
@login_required
def investments():
    filter_type = request.args.get('filter', 'all')
    all_data = Investment.query.all()

    from datetime import date

    today = date.today()

    matured_count = 0
    soon_count = 0

    for i in data:
        if i.is_closed:
            continue

        days_left = (i.maturity_date - today).days

        if days_left < 0:
            matured_count += 1
        elif days_left <= 7:
            soon_count += 1

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
    return redirect('/login')

@app.route('/delete/<int:id>')
@login_required
def delete_fd(id):
    fd = Investment.query.get_or_404(id)

    db.session.delete(fd)
    db.session.commit()

    return redirect('/investments')


@app.route('/close/<int:id>')
@login_required
def close_fd(id):
    fd = Investment.query.get_or_404(id)

    fd.is_closed = True
    fd.closed_on = date.today()

    db.session.commit()

    return redirect('/investments')



@app.route('/edit/<int:id>', methods=['GET', 'POST'])
@login_required
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




@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')





# 🔐 ADD HERE
@app.route('/change_password', methods=['GET', 'POST'])
@login_required
def change_password():
    user = User.query.filter_by(username="admin").first()

    if request.method == 'POST':
        current = request.form.get('current_password')
        new = request.form.get('new_password')

        if not check_password_hash(user.password, current):
            return "❌ Current password incorrect"

        user.password = generate_password_hash(new)
        db.session.commit()
        session.clear()
        return redirect('/login')

    return render_template("change_password.html")


if __name__ == '__main__':
    app.run(debug=True)

