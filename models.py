from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class Investment(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    # Common fields
    type = db.Column(db.String(20))  # FD / SIP / ETF / Stock
    start_date = db.Column(db.Date)
    notes = db.Column(db.String(200))
    status = db.Column(db.String(20))  # active / closed

    # FD fields
    bank_name = db.Column(db.String(100))
    fd_number = db.Column(db.String(100), unique=True, nullable=False)
    invested_amount = db.Column(db.Float)
    interest_rate = db.Column(db.Float)
    maturity_date = db.Column(db.Date)
    maturity_amount = db.Column(db.Float)

    # SIP / ETF / Stock fields
    name = db.Column(db.String(100))
    sip_amount = db.Column(db.Float)
    sip_frequency = db.Column(db.String(20))  # monthly / weekly

    def __repr__(self):
        return f"<Investment {self.type}>"