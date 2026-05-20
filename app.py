import os
from dotenv import load_dotenv
from flask import request
from models.log import Log
from extensions import db, limiter
from werkzeug.exceptions import HTTPException

load_dotenv()

from flask import Flask, redirect, url_for, session, render_template

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'fallback-secret-key')
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

limiter.init_app(app)
db.init_app(app)

# Logging middleware for unauthorized access
@app.before_request
def log_unauthorized_access():
    # Skip logging for static files and auth routes to avoid noise
    if request.endpoint and ('static' in request.endpoint or
                           request.endpoint.startswith('auth.')):
        return

    # Check if user is trying to access protected routes without login
    if 'username' not in session and request.endpoint:
        # Allow access to login and register pages
        if request.endpoint not in ['auth.login', 'auth.register', 'auth.logout']:
            ip_address = request.remote_addr
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
def not_found_error(e):
    ip_address = request.remote_addr
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
def rate_limit_error(e):
    ip_address = request.remote_addr
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
    ip_address = request.remote_addr
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