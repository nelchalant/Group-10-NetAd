from extensions import db
from datetime import datetime, timezone, timedelta

class CameraConfig(db.Model):
    __tablename__ = 'camera_config'
    id = db.Column(db.Integer, primary_key=True)
    stream_url = db.Column(db.Text, nullable=True)  # RTSP or HTTP URL
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone(timedelta(hours=8))), onupdate=lambda: datetime.now(timezone(timedelta(hours=8))))

    def __repr__(self):
        return f'<CameraConfig {self.stream_url}>'