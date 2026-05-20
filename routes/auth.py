from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from extensions import db, limiter
from models.user import User
from models.log import Log
import bcrypt

auth = Blueprint('auth', __name__)

@auth.route('/register', methods=['GET', 'POST'])
@limiter.limit("3 per hour")
def register():
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password']
        confirm  = request.form['confirm_password']

        if password != confirm:
            log = Log(
                username=username or 'unknown',
                action='Registration attempt',
                ip_address=request.remote_addr,
                status='Failed',
                reason='Passwords do not match'
            )
            db.session.add(log)
            db.session.commit()
            flash('Passwords do not match!')
            return redirect(url_for('auth.register'))

        if len(password) < 8:
            log = Log(
                username=username or 'unknown',
                action='Registration attempt',
                ip_address=request.remote_addr,
                status='Failed',
                reason='Password too short'
            )
            db.session.add(log)
            db.session.commit()
            flash('Password must be at least 8 characters!')
            return redirect(url_for('auth.register'))

        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            log = Log(
                username=username,
                action='Registration attempt',
                ip_address=request.remote_addr,
                status='Failed',
                reason='Username already exists'
            )
            db.session.add(log)
            db.session.commit()
            flash('Username already exists!')
            return redirect(url_for('auth.register'))

        hashed_password = bcrypt.hashpw(
            password.encode('utf-8'),
            bcrypt.gensalt()
        ).decode('utf-8')

        new_user = User(username=username, password=hashed_password)
        db.session.add(new_user)

        log = Log(
            username=username,
            action='Registered an account',
            ip_address=request.remote_addr,
            status='Success'
        )
        db.session.add(log)
        db.session.commit()

        flash('Registration successful! Please login.')
        return redirect(url_for('auth.login'))

    return render_template('register.html')


@auth.route('/login', methods=['GET', 'POST'])
@limiter.limit("5 per 15 minutes")
def login():
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password']

        user = User.query.filter_by(username=username).first()

        if user and bcrypt.checkpw(
            password.encode('utf-8'),
            user.password.encode('utf-8')
        ):
            session['username'] = username

            log = Log(
                username=username,
                action='Logged in',
                ip_address=request.remote_addr,
                status='Success'
            )
            db.session.add(log)
            db.session.commit()

            return redirect(url_for('camera.dashboard'))
        else:
            # Determine reason for failure
            if not user:
                reason = 'User not found'
            else:
                reason = 'Wrong password'

            log = Log(
                username=username or 'unknown',
                action='Login attempt',
                ip_address=request.remote_addr,
                status='Failed',
                reason=reason
            )
            db.session.add(log)
            db.session.commit()

            flash('login failed')
            return redirect(url_for('auth.login'))

    return render_template('login.html')


@auth.route('/logout')
def logout():
    username = session.get('username')

    if username:
        log = Log(
            username=username,
            action='Logged out',
            ip_address=request.remote_addr,
            status='Success'
        )
        db.session.add(log)
        db.session.commit()

    session.pop('username', None)
    return redirect(url_for('auth.login'))
