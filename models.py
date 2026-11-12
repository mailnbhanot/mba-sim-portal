from datetime import datetime, timezone

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(10), nullable=False, default="student")  # admin | student
    batch = db.Column(db.String(60), default="", index=True)
    created_at = db.Column(db.DateTime, default=utcnow)


class Tournament(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    status = db.Column(db.String(10), default="draft")        # draft | active | finished
    round_state = db.Column(db.String(10), default="open")    # open | processed
    current_round = db.Column(db.Integer, default=0)
    total_rounds = db.Column(db.Integer, default=10)
    game_key = db.Column(db.String(40), nullable=False, default="rural_marketing")
    participation = db.Column(db.String(10), default="individual")  # individual | team
    team_size = db.Column(db.Integer, default=4)
    rank_w_profit = db.Column(db.Integer, default=60)         # % weight of profit in the ranking; rest is market share
    mode = db.Column(db.String(10), default="manual")         # manual | auto
    market_mode = db.Column(db.String(10), default="single")  # single | groups
    group_size = db.Column(db.Integer, default=10)
    interval_hours = db.Column(db.Integer, default=48)
    deadline = db.Column(db.DateTime, nullable=True)          # UTC
    seed = db.Column(db.Integer, nullable=False)
    start_cash = db.Column(db.Integer, default=5_000_000)
    created_at = db.Column(db.DateTime, default=utcnow)


class Participant(db.Model):
    """One competing company: a single student, or a team of students."""
    id = db.Column(db.Integer, primary_key=True)
    tournament_id = db.Column(db.Integer, db.ForeignKey("tournament.id"), index=True)
    alias = db.Column(db.String(60), default="")
    group_no = db.Column(db.Integer, default=0)
    cash = db.Column(db.Float, default=0.0)
    state = db.Column(db.JSON, default=dict)   # carries brand, customers etc. into later rounds


class Enrollment(db.Model):
    """A student allowed into a tournament. participant_id is set when the tournament starts."""
    id = db.Column(db.Integer, primary_key=True)
    tournament_id = db.Column(db.Integer, db.ForeignKey("tournament.id"), index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), index=True)
    team_label = db.Column(db.String(60), default="")   # optional team name set by the teacher
    participant_id = db.Column(db.Integer, db.ForeignKey("participant.id"), nullable=True, index=True)
    user = db.relationship("User")
    participant = db.relationship("Participant")
    __table_args__ = (db.UniqueConstraint("tournament_id", "user_id"),)


class Decision(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    tournament_id = db.Column(db.Integer, db.ForeignKey("tournament.id"), index=True)
    participant_id = db.Column(db.Integer, db.ForeignKey("participant.id"), index=True)
    edited_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    round_no = db.Column(db.Integer, nullable=False)
    data = db.Column(db.JSON, default=dict)
    submitted = db.Column(db.Boolean, default=False)
    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow)
    __table_args__ = (db.UniqueConstraint("tournament_id", "participant_id", "round_no"),)


class Result(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    tournament_id = db.Column(db.Integer, db.ForeignKey("tournament.id"), index=True)
    participant_id = db.Column(db.Integer, db.ForeignKey("participant.id"), index=True)
    round_no = db.Column(db.Integer, nullable=False)
    data = db.Column(db.JSON, default=dict)
    reflection = db.Column(db.Text, default="")
    __table_args__ = (db.UniqueConstraint("tournament_id", "participant_id", "round_no"),)


class EventLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    tournament_id = db.Column(db.Integer, db.ForeignKey("tournament.id"), index=True)
    round_no = db.Column(db.Integer, nullable=False)
    key = db.Column(db.String(40), nullable=False)
    created_at = db.Column(db.DateTime, default=utcnow)
