from extensions import db
from datetime import datetime

class Log(db.Model):
    __tablename__ = 'logs'
    id        = db.Column(db.Integer, primary_key=True)
    username  = db.Column(db.String(80), nullable=False)
    action    = db.Column(db.String(255), nullable=False)
    ip_address = db.Column(db.String(45), nullable=True)  # IPv4 or IPv6
    status    = db.Column(db.String(20), nullable=False, default='Success')  # Success, Failed, Denied
    reason    = db.Column(db.String(255), nullable=True)  # Reason for failure
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<Log {self.username} - {self.action} [{self.status}]>'
