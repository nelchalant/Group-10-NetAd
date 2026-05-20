from flask import Blueprint, render_template, Response, redirect, url_for, session, request, flash
from extensions import db
from models.log import Log
from models.camera import CameraConfig
import cv2

camera = Blueprint('camera', __name__)


def get_stream_url():
    """Get the camera stream URL from the database, creating a default config if none exists."""
    config = CameraConfig.query.first()
    if config is None:
        config = CameraConfig()
        db.session.add(config)
        db.session.commit()
    return config.stream_url


def generate_frames():
    stream_url = get_stream_url()
    if stream_url is None:
        return

    cap = cv2.VideoCapture(stream_url)
    while True:
        success, frame = cap.read()
        if not success:
            break
        ret, buffer = cv2.imencode('.jpg', frame)
        frame = buffer.tobytes()
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
    cap.release()


@camera.route('/dashboard')
def dashboard():
    if 'username' not in session:
        return redirect(url_for('auth.login'))

    log = Log(
        username=session['username'],
        action='Viewed camera feed',
        ip_address=request.remote_addr,
        status='Success'
    )
    db.session.add(log)
    db.session.commit()

    camera_ready = get_stream_url() is not None
    return render_template('dashboard.html', camera_ready=camera_ready)


@camera.route('/video_feed')
def video_feed():
    if 'username' not in session:
        return redirect(url_for('auth.login'))

    stream_url = get_stream_url()
    if stream_url is None:
        return "Camera not configured yet.", 503

    return Response(
        generate_frames(),
        mimetype='multipart/x-mixed-replace; boundary=frame'
    )


@camera.route('/configure', methods=['GET', 'POST'])
def configure_camera():
    if 'username' not in session:
        return redirect(url_for('auth.login'))
    # Optionally restrict to admin users; for now any logged-in user can configure
    config = CameraConfig.query.first()
    if config is None:
        config = CameraConfig()
        db.session.add(config)
        db.session.commit()

    if request.method == 'POST':
        stream_url = request.form.get('stream_url', '').strip()
        if stream_url == '':
            stream_url = None
        config.stream_url = stream_url
        db.session.commit()
        flash('Camera configuration saved.')
        return redirect(url_for('camera.dashboard'))

    return render_template('configure_camera.html', current_url=config.stream_url or '')
