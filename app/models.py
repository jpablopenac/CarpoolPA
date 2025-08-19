from datetime import datetime, date
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from . import db, login_manager

# Constants
DAYS = ["lunes", "martes", "miercoles", "jueves", "viernes"]
IDA_SLOTS = ["8:20", "9:40", "11:00", "12:20"]
VUELTA_SLOTS = ["13:30", "16:00", "17:20", "18:40"]


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    volunteer_second_day = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    preferences = db.relationship("Preference", backref="user", cascade="all, delete-orphan")

    def set_password(self, password: str):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


class Week(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    start_date = db.Column(db.Date, nullable=False, unique=True)  # Monday
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Preference(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    week_id = db.Column(db.Integer, db.ForeignKey("week.id"), nullable=False)

    day = db.Column(db.String(16), nullable=False)  # lunes..viernes
    ida_slot = db.Column(db.String(16), nullable=True)
    vuelta_slot = db.Column(db.String(16), nullable=True)

    flex_ida = db.Column(db.Boolean, default=False)
    flex_vuelta = db.Column(db.Boolean, default=False)
    can_drive = db.Column(db.Boolean, default=False)

    # Roles after optimization
    role_ida = db.Column(db.String(16), nullable=True)   # conductor/pasajero/None
    role_vuelta = db.Column(db.String(16), nullable=True)

    # Assignment frozen by optimization (for viewing)
    assigned_ida_slot = db.Column(db.String(16), nullable=True)
    assigned_vuelta_slot = db.Column(db.String(16), nullable=True)

    week = db.relationship("Week", backref=db.backref("preferences", cascade="all, delete-orphan"))

    __table_args__ = (
        db.UniqueConstraint("user_id", "week_id", "day", name="uq_user_week_day"),
    )


def get_or_create_week(monday_date: date) -> Week:
    week = Week.query.filter_by(start_date=monday_date).first()
    if not week:
        week = Week(start_date=monday_date)
        db.session.add(week)
        db.session.commit()
    return week
