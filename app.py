import os
from dotenv import load_dotenv
from flask import Flask, request, redirect, url_for, session, render_template
from models.log import Log
from extensions import db, limiter
from werkzeug.exceptions import HTTPException
from sqlalchemy import inspect, text

load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'fallback-secret-key')
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

limiter.init_app(app)
db.init_app(app)

def get_client_ip():
    """Get client IP address, taking into account proxies and load balancers."""
    if request.headers.getlist("X-Forwarded-For"):
        ip = request.headers.getlist("X-Forwarded-For")[0].split(',')[0].strip()
    elif request.headers.getlist("X-Real-IP"):
        ip = request.headers.getlist("X-Real-IP")[0]
    else:
        ip = request.remote_addr
    return ip

def ensure_log_table_schema():
    """Ensure the logs table has all required columns, adding them if missing."""
    with app.app_context():
        inspector = inspect(db.engine)
        if not inspector.has_table("logs"):
            # Table doesn't exist yet - db.create_all() will handle it
            return

        existing_columns = [col['name'] for col in inspector.get_columns('logs')]

        # Add missing columns
        with db.engine.connect() as conn:
            trans = conn.begin()
            try:
                if 'ip_address' not in existing_columns:
                    conn.execute(text("ALTER TABLE logs ADD COLUMN ip_address VARCHAR(45)"))
                    print("Added ip_address column to logs table")

                if 'status' not in existing_columns:
                    conn.execute(text("ALTER TABLE logs ADD COLUMN status VARCHAR(20) DEFAULT 'Success'"))
                    print("Added status column to logs table")

                if 'reason' not in existing_columns:
                    conn.execute(text("ALTER TABLE logs ADD COLUMN reason VARCHAR(255)"))
                    print("Added reason column to logs table")

                trans.commit()
            except Exception as e:
                trans.rollback()
                print(f"Error updating logs table schema: {e}")

# Apply schema fixes on startup
ensure_log_table_schema()

# Logging middleware for unauthorized access
@app.before_request
def log_unauthorized_access():
    # Skip logging for static files and auth routes to avoid noise
    if request.endpoint and ('static' in request.endpoint or request.endpoint.startswith('auth.')):
        return

    # Check if user is trying to access protected routes without login
    if 'username' not in session and request.endpoint:
        # Allow access to login and register pages
        if request.endpoint not in ['auth.login', 'auth.register', 'auth.logout']:
            ip_address = get_client_ip()
            log = Log(
                username='Unknown',
                action=f'Unauthorized access to {request.path}',
                ip_address=ip_address,
                status='Denied',
                reason='Not logged in'
            )
            db.session.add(log)
            db.session.commit()

# Specific error handlers for clean logging
@app.errorhandler(404)
def not_found_error(_):
    ip_address = get_client_ip()
    username = session.get('username', 'Unknown')

    log = Log(
        username=username,
        action='Page not found',
        ip_address=ip_address,
        status='Failed',
        reason='Page not found'
    )
    db.session.add(log)
    db.session.commit()

    return render_template('error.html', message="Page not found"), 404

@app.errorhandler(429)
def rate_limit_error(_):
    ip_address = get_client_ip()
    username = session.get('username', 'Unknown')

    log = Log(
        username=username,
        action='Rate limit exceeded',
        ip_address=ip_address,
        status='Failed',
        reason='Too many attempts'
    )
    db.session.add(log)
    db.session.commit()

    return render_template('error.html',
        message="Too many attempts. Please wait 15 minutes before trying again."), 429

# Global error handler for other exceptions
@app.errorhandler(Exception)
def log_exception(e):
    ip_address = get_client_ip()
    username = session.get('username', 'Unknown')

    # Determine reason based on error type
    if isinstance(e, HTTPException):
        if e.code == 404:
            reason = 'Page not found'  # Should be caught by 404 handler above
        elif e.code == 429:
            reason = 'Too many attempts'  # Should be caught by 429 handler above
        else:
            reason = f'HTTP {e.code} error'
    else:
        reason = 'Application error'

    log = Log(
        username=username,
        action='Application error',
        ip_address=ip_address,
        status='Failed',
        reason=reason
    )
    db.session.add(log)
    db.session.commit()

    # Handle rate limit errors specifically (catch any that bypass specific handler)
    if 'RateLimitExceeded' in type(e).__name__:
        return render_template('error.html',
            message="Too many attempts. Please wait 15 minutes before trying again."), 429

    # Handle other HTTP errors
    if isinstance(e, HTTPException):
        return render_template('error.html',
            message=str(e)), e.code

    # Generic server error
    return render_template('error.html',
        message="Something went wrong. Please try again."), 500

from routes.auth import auth
from routes.camera import camera
from routes.logs import logs

app.register_blueprint(auth)
app.register_blueprint(camera)
app.register_blueprint(logs)

with app.app_context():
    db.create_all()

@app.route('/')
def index():
    if 'username' in session:
        return redirect(url_for('camera.dashboard'))
    return redirect(url_for('auth.login'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=True)