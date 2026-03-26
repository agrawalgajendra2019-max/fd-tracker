from app import app, send_email_alerts

with app.app_context():
    print("Running daily email job...")
    send_email_alerts()
    print("Done.")