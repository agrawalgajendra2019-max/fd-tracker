from flask import Flask, request, redirect, render_template, render_template_string, Response, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, date
import csv
from io import StringIO
from werkzeug.security import generate_password_hash, check_password_hash
import smtplib
from email.mime.text import MIMEText
from auth import login_required
import logging

import os
from werkzeug.utils import secure_filename


app = Flask(__name__)
app.secret_key = "mysecret123"

logging.basicConfig(
    filename='app.log',
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s'
)

from income.routes import income_bp
app.register_blueprint(income_bp)

# ✅ Upload folder
UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# ✅ Supabase DB
app.config['SQLALCHEMY_DATABASE_URI'] = "postgresql://postgres.xvcvnrbdvzbycaqswrgv:Nagpurindiayavatmal1234@aws-1-ap-south-1.pooler.supabase.com:6543/postgres"
# import os
# app.config['SQLALCHEMY_DATABASE_URI'] = "postgresql://postgres:YOUR_PASSWORD@db.xvcvnrbdvzbycaqswrgv.supabase.co:5432/postgres"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize DB
# db = SQLAlchemy(app)
from extensions import db

db.init_app(app)

from flask import session, redirect, request, render_template

USERNAME = "admin"
PASSWORD = "scrypt:32768:8:1$ti4MKlnAZmKgKGgt$4208dba8fbdfef3781b9747f0c1474e18c53249a0f8dbff5e1c5491ea64f18cabaf8a48c81034b3d5dffd0452bf9be6d89e975bf17b4f9a11883236012a1737b"

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        logging.info(f"Login attempt: {request.form.get('username')}")

        user = User.query.filter_by(username=request.form['username']).first()

        if user and check_password_hash(user.password, request.form['password']):
            session['logged_in'] = True
            return redirect('/investments')
        else:
            return "Invalid credentials"

    return render_template('login.html')


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


# ==============================
# ✅ HELPER FUNCTIONS (ADD HERE)
# ==============================

def days_remaining(maturity_date):
    if not maturity_date:
        return None
    return (maturity_date - date.today()).days


def maturity_status(i):
    if i.is_closed:
        return "Closed"
    if not i.maturity_date:
        return "No Date"

    d = days_remaining(i.maturity_date)

    if d < 0:
        return "Matured"
    elif d <= 7:
        return "Maturing Soon"
    else:
        return "Active"

# 🔥 CREATE TABLES IN SUPABASE (ALWAYS RUN ON START)
with app.app_context():
    db.create_all()

    # create default user if not exists
    if not User.query.filter_by(username="admin").first():
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

    # ✅ LOG 1 — FD ADD ATTEMPT
    logging.info(f"FD add attempt: {fd_number}")

    # 🔴 DUPLICATE CHECK
    existing = Investment.query.filter_by(fd_number=fd_number).first()
    if existing:
        logging.warning(f"Duplicate FD blocked: {fd_number}")  # ✅ LOG 2
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

    # ✅ LOG 3 — SUCCESS
    logging.info(f"FD added successfully: {fd_number}")

    return redirect('/investments')




# ---------------- DASHBOARD ----------------
@app.route('/investments')
@login_required
def investments():
    all_data = Investment.query.all()

    filter_type = request.args.get('filter', 'all')

    matured_count = 0
    soon_count = 0

    for i in all_data:
        i.days_left = days_remaining(i.maturity_date)
        i.status_display = maturity_status(i)

        if i.status_display == "Matured":
            matured_count += 1
        elif i.status_display == "Maturing Soon":
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
    total_interest = total_maturity - total_invested
    net_worth = total_maturity
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
        total_interest=total_interest,
        net_worth=net_worth,
        active_count=active_count,
        closed_count=closed_count,
        maturity_status=maturity_status,
        bank_summary=bank_summary,
        matured_count=matured_count,   # ✅ FIX
        soon_count=soon_count          # ✅ FIX
    )


@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

from flask import session, redirect

@app.route('/')
def home():
    return redirect('/login')

@app.route('/delete/<int:id>', methods=['POST'])
@login_required
def delete_fd(id):
    fd = Investment.query.get(id)

    if fd:
        logging.info(f"FD delete attempt: ID={id}, FD={fd.fd_number}")

        db.session.delete(fd)
        db.session.commit()

        logging.info(f"FD deleted successfully: ID={id}")
    else:
        logging.warning(f"FD delete failed (not found): ID={id}")

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
@app.route('/export-csv')
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
    filename = f"fd_backup_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"

    return Response(
        output,
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment;filename={filename}"}
    )



def send_email_alert(message):
    sender = "gajendramanakshe@gmail.com"
    password = "sbpg ynyr acvp madl"   # NOT normal password
    receiver = "gajendramanakshe@gmail.com"

    msg = MIMEText(message)
    msg['Subject'] = "FD Alert 🚨"
    msg['From'] = sender
    msg['To'] = receiver

    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(sender, password)
        server.sendmail(sender, receiver, msg.as_string())
        server.quit()
        print("Email sent")
    except Exception as e:
        print("Email error:", e)


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


@app.route('/check-data')
def check_data():
    data = Investment.query.all()
    output = ""
    for i in data:
        output += f"{i.fd_number} | {i.start_date} | {i.maturity_date} <br>"
    return output



with app.app_context():
    from income.models import IncomeEntry
    db.create_all()

if __name__ == '__main__':
    app.run(debug=True)

