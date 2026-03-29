from datetime import datetime
# from app import db   # ← YES we use this
from extensions import db


class IncomeEntry(db.Model):
    __tablename__ = 'income_entries'

    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    date = db.Column(db.Date, nullable=False)

    source = db.Column(db.String(20), nullable=False)

    mode = db.Column(db.String(10), nullable=False)

    amount = db.Column(db.Float, nullable=False)

    notes = db.Column(db.Text)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)