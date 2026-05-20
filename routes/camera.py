from flask import Blueprint, render_template, Response, redirect, url_for, session, request
from extensions import db
from models.log import Log
import cv2

camera = Blueprint('camera', __name__)

# Camera stream URL - set to None until hardware is available
# When hardware arrives, replace None with your stream URL:
# Examples:
#   Hikvision : "rtsp://192.168.1.10:554/Streaming/Channels/101"
#   Dahua     : "rtsp://192.168.1.10:554/cam/realmonitor?channel=1&subtype=0"
#   Generic   : "rtsp://192.168.1.10:554/stream1"
#   Phone app : "http://your_phone_ip:8080/video"
#   Webcam    : 0
STREAM_URL = None


def generate_frames():
    if STREAM_URL is None:
        return

    cap = cv2.VideoCapture(STREAM_URL)
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

    camera_ready = STREAM_URL is not None
    return render_template('dashboard.html', camera_ready=camera_ready)


@camera.route('/video_feed')
def video_feed():
    if 'username' not in session:
        return redirect(url_for('auth.login'))

    if STREAM_URL is None:
        return "Camera not configured yet.", 503

    return Response(
        generate_frames(),
        mimetype='multipart/x-mixed-replace; boundary=frame'
    )
