import csv
import io
import os
import random
import re
import secrets
import time
from datetime import datetime, timedelta, timezone
from functools import wraps

from flask import (Flask, Response, abort, flash, g, redirect, render_template,
                   request, session, url_for)
from werkzeug.security import check_password_hash, generate_password_hash

import games
import services
from models import (Decision, Enrollment, EventLog, Participant, Result,
                    Tournament, User, db, utcnow)

IST = timezone(timedelta(hours=5, minutes=30))  # India has no daylight saving
PW_METHOD = "pbkdf2:sha256:30000"
PW_ALPHABET = "abcdefghjkmnpqrstuvwxyzACDEFGHJKLMNPQRTUVWXYZ2346789"


def create_app(config=None):
    app = Flask(__name__)
    db_url = os.environ.get("DATABASE_URL", "sqlite:///sim.db")
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)
    app.config.update(
        SQLALCHEMY_DATABASE_URI=db_url,
        SECRET_KEY=os.environ.get("SECRET_KEY", "dev-only-change-me"),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=bool(os.environ.get("SECURE_COOKIES")),
        TICK_SECRET=os.environ.get("TICK_SECRET", ""),
        MAX_CONTENT_LENGTH=2 * 1024 * 1024,
        TICK_THROTTLE_SECONDS=20,
    )
    if config:
        app.config.update(config)
    db.init_app(app)
    with app.app_context():
        db.create_all()
        _bootstrap_admin()
    register_filters(app)
    register_routes(app)
    return app


def _bootstrap_admin():
    if User.query.filter_by(role="admin").first():
        return
    username = os.environ.get("ADMIN_USERNAME", "admin")
    password = os.environ.get("ADMIN_PASSWORD")
    if not password:
        return
    db.session.add(User(username=username, name="Teacher", role="admin",
                        password_hash=generate_password_hash(password, method=PW_METHOD)))
    db.session.commit()


# ---------- template helpers ----------

def inr(value, decimals=0):
    """Indian digit grouping: 12,34,567."""
    if value is None:
        return "-"
    neg = value < 0
    value = abs(float(value))
    whole = int(value) if decimals == 0 else int(value)
    if decimals == 0:
        whole = int(round(value))
        frac = ""
    else:
        frac = f"{value - int(value):.{decimals}f}"[1:]
    s = str(whole)
    if len(s) > 3:
        head, tail = s[:-3], s[-3:]
        parts = []
        while len(head) > 2:
            parts.insert(0, head[-2:])
            head = head[:-2]
        if head:
            parts.insert(0, head)
        s = ",".join(parts + [tail])
    return ("-" if neg else "") + "Rs " + s + frac


def register_filters(app):
    app.jinja_env.filters["inr"] = inr
    app.jinja_env.filters["pct"] = lambda v, d=0: "-" if v is None else f"{v * 100:.{d}f}%"
    app.jinja_env.filters["num"] = lambda v: "-" if v is None else f"{int(round(v)):,}"

    def ist(dt):
        if not dt:
            return "-"
        return dt.replace(tzinfo=timezone.utc).astimezone(IST).strftime("%d %b %Y, %I:%M %p IST")
    app.jinja_env.filters["ist"] = ist
    app.jinja_env.filters["ist_input"] = lambda dt: (
        dt.replace(tzinfo=timezone.utc).astimezone(IST).strftime("%Y-%m-%dT%H:%M") if dt else "")
    app.jinja_env.globals.update(all_games=games.all_games, game_of=services.game_of)


# ---------- auth helpers ----------

_login_failures = {}   # username -> [timestamps]; in memory is enough for a single instance


def _locked_out(username):
    now = time.time()
    attempts = [t for t in _login_failures.get(username, []) if now - t < 900]
    _login_failures[username] = attempts
    return len(attempts) >= 10


def login_required(role=None):
    def deco(fn):
        @wraps(fn)
        def wrapper(*a, **kw):
            if not g.user:
                return redirect(url_for("login", next=request.path))
            if role and g.user.role != role:
                abort(403)
            return fn(*a, **kw)
        return wrapper
    return deco


def new_password(n=8):
    return "".join(secrets.choice(PW_ALPHABET) for _ in range(n))


def make_username(base, taken):
    base = re.sub(r"[^a-z0-9._-]", "", base.lower().strip().replace(" ", "."))[:40] or "student"
    name, i = base, 1
    while name in taken:
        i += 1
        name = f"{base}{i}"
    taken.add(name)
    return name


def csv_response(rows, header, filename):
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(header)
    w.writerows(rows)
    return Response(buf.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": f"attachment; filename={filename}"})


def parse_ist_datetime(text):
    """datetime-local input (IST) -> naive UTC."""
    dt = datetime.strptime(text, "%Y-%m-%dT%H:%M").replace(tzinfo=IST)
    return dt.astimezone(timezone.utc).replace(tzinfo=None)


# ---------- routes ----------

def register_routes(app):
    last_tick = {"t": 0.0}

    @app.before_request
    def load_user():
        g.user = db.session.get(User, session["uid"]) if session.get("uid") else None
        if "csrf" not in session:
            session["csrf"] = secrets.token_hex(16)
        if request.method == "POST":
            if request.path == "/tick":
                return
            token = request.form.get("csrf", "")
            if not secrets.compare_digest(token, session["csrf"]):
                abort(400, "Form expired. Go back, refresh the page and try again.")
        now = time.time()
        if now - last_tick["t"] > app.config["TICK_THROTTLE_SECONDS"]:
            last_tick["t"] = now
            services.tick()

    @app.context_processor
    def inject():
        return {"csrf": session.get("csrf", ""), "me": g.get("user")}

    @app.route("/tick", methods=["GET", "POST"])
    def tick():
        """Ping this from a free cron service so automatic rounds close on time even
        when nobody is using the site."""
        secret = app.config["TICK_SECRET"]
        if not secret or request.args.get("key") != secret:
            abort(404)
        return {"processed": services.tick()}

    @app.route("/")
    def index():
        if not g.user:
            return redirect(url_for("login"))
        return redirect(url_for("admin_home" if g.user.role == "admin" else "student_home"))

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if request.method == "POST":
            username = request.form.get("username", "").strip().lower()
            password = request.form.get("password", "")
            if _locked_out(username):
                flash("Too many failed attempts. Try again in 15 minutes.", "error")
                return render_template("login.html"), 429
            user = User.query.filter_by(username=username).first()
            if user and check_password_hash(user.password_hash, password):
                session.clear()
                session["uid"] = user.id
                session["csrf"] = secrets.token_hex(16)
                nxt = request.args.get("next", "")
                return redirect(nxt if nxt.startswith("/") and not nxt.startswith("//")
                                else url_for("index"))
            _login_failures.setdefault(username, []).append(time.time())
            flash("Wrong username or password.", "error")
        return render_template("login.html")

    @app.route("/logout", methods=["POST"])
    def logout():
        session.clear()
        return redirect(url_for("login"))

    # ===== teacher =====

    @app.route("/admin")
    @login_required("admin")
    def admin_home():
        tournaments = Tournament.query.order_by(Tournament.created_at.desc()).all()
        counts = {t.id: Enrollment.query.filter_by(tournament_id=t.id).count() for t in tournaments}
        n_students = User.query.filter_by(role="student").count()
        return render_template("admin_home.html", tournaments=tournaments, counts=counts,
                               n_students=n_students)

    @app.route("/admin/students")
    @login_required("admin")
    def admin_students():
        q = request.args.get("q", "").strip().lower()
        batch = request.args.get("batch", "")
        query = User.query.filter_by(role="student")
        if q:
            query = query.filter(db.or_(User.username.contains(q), User.name.ilike(f"%{q}%")))
        if batch:
            query = query.filter_by(batch=batch)
        total = query.count()
        students = query.order_by(User.batch, User.username).limit(300).all()
        batches = [b[0] for b in db.session.query(User.batch).filter(
            User.role == "student").distinct().order_by(User.batch) if b[0]]
        return render_template("admin_students.html", students=students, total=total,
                               batches=batches, q=q, batch=batch)

    @app.route("/admin/students/upload", methods=["POST"])
    @login_required("admin")
    def admin_upload_students():
        f = request.files.get("file")
        default_batch = request.form.get("batch", "").strip()
        if not f:
            flash("Choose a CSV file first.", "error")
            return redirect(url_for("admin_students"))
        text = f.read().decode("utf-8-sig", errors="replace")
        reader = csv.DictReader(io.StringIO(text))
        if not reader.fieldnames:
            flash("The file is empty.", "error")
            return redirect(url_for("admin_students"))
        cols = {c.strip().lower(): c for c in reader.fieldnames}
        name_col = cols.get("name")
        id_col = cols.get("roll_no") or cols.get("username") or cols.get("roll") or cols.get("id")
        batch_col = cols.get("batch") or cols.get("section")
        if not name_col:
            flash("The CSV needs a 'name' column (optional: roll_no, batch).", "error")
            return redirect(url_for("admin_students"))
        taken = {u[0] for u in db.session.query(User.username).all()}
        out, created = [], 0
        for row in reader:
            name = (row.get(name_col) or "").strip()
            if not name:
                continue
            ident = (row.get(id_col) or "").strip() if id_col else ""
            username = make_username(ident or name, taken)
            batch = (row.get(batch_col) or "").strip() if batch_col else ""
            batch = batch or default_batch
            pw = new_password()
            db.session.add(User(username=username, name=name, role="student", batch=batch,
                                password_hash=generate_password_hash(pw, method=PW_METHOD)))
            out.append([username, pw, name, batch])
            created += 1
        db.session.commit()
        if not created:
            flash("No students found in the file.", "error")
            return redirect(url_for("admin_students"))
        return csv_response(out, ["username", "password", "name", "batch"],
                            f"credentials_{created}_students.csv")

    @app.route("/admin/students/reset", methods=["POST"])
    @login_required("admin")
    def admin_reset_passwords():
        """Reset passwords for a batch, or for specific usernames, and download the new ones."""
        usernames = [u.strip().lower() for u in re.split(r"[\s,;]+", request.form.get("usernames", "")) if u.strip()]
        batch = request.form.get("batch", "")
        query = User.query.filter_by(role="student")
        if usernames:
            query = query.filter(User.username.in_(usernames))
        elif batch:
            query = query.filter_by(batch=batch)
        else:
            flash("Pick a batch or paste usernames.", "error")
            return redirect(url_for("admin_students"))
        out = []
        for u in query.all():
            pw = new_password()
            u.password_hash = generate_password_hash(pw, method=PW_METHOD)
            out.append([u.username, pw, u.name, u.batch])
        db.session.commit()
        if not out:
            flash("No matching students.", "error")
            return redirect(url_for("admin_students"))
        return csv_response(out, ["username", "password", "name", "batch"], "new_passwords.csv")

    @app.route("/admin/tournaments/new", methods=["GET", "POST"])
    @login_required("admin")
    def admin_tournament_new():
        if request.method == "POST":
            name = request.form.get("name", "").strip() or "Tournament"
            game_key = request.form.get("game", "")
            try:
                game = games.get(game_key)
            except KeyError:
                flash("Choose a game.", "error")
                return redirect(url_for("admin_tournament_new"))
            t = Tournament(
                name=name, game_key=game.key, total_rounds=game.total_rounds,
                participation="team" if request.form.get("participation") == "team" else "individual",
                team_size=max(2, min(12, int(request.form.get("team_size") or 4))),
                mode=request.form.get("mode") if request.form.get("mode") in ("manual", "auto") else "manual",
                market_mode="groups" if request.form.get("market_mode") == "groups" else "single",
                group_size=max(3, min(60, int(request.form.get("group_size") or 10))),
                interval_hours=max(1, min(24 * 14, int(request.form.get("interval_hours") or 48))),
                rank_w_profit=max(0, min(100, int(request.form.get("rank_w_profit") or 60))),
                start_cash=max(500_000, int(request.form.get("start_cash") or 5_000_000)),
                seed=random.randint(1, 10**9),
            )
            db.session.add(t)
            db.session.commit()
            return redirect(url_for("admin_tournament", tid=t.id))
        return render_template("admin_tournament_new.html")

    def _tournament_or_404(tid):
        t = db.session.get(Tournament, tid)
        if not t:
            abort(404)
        return t

    @app.route("/admin/t/<int:tid>")
    @login_required("admin")
    def admin_tournament(tid):
        t = _tournament_or_404(tid)
        game = services.game_of(t)
        enrolled = (Enrollment.query.filter_by(tournament_id=t.id)
                    .join(User, User.id == Enrollment.user_id).order_by(User.batch, User.username).all())
        submitted = set()
        if t.status == "active":
            submitted = {d.participant_id for d in Decision.query.filter_by(
                tournament_id=t.id, round_no=t.current_round, submitted=True)}
        batches = [b[0] for b in db.session.query(User.batch).filter(
            User.role == "student").distinct().order_by(User.batch) if b[0]]
        events = services.active_events(t, t.current_round) if t.current_round else []
        board = services.leaderboard(t) if t.status != "draft" else []
        members = services.members_by_participant(t) if t.status != "draft" else {}
        return render_template(
            "admin_tournament.html", t=t, game=game, enrolled=enrolled, submitted=submitted,
            batches=batches, events=events, board=board, members=members, EVENTS=game.events,
            n_groups=len({p.group_no for p in board}),
            next_built=(t.current_round + 1) in game.implemented_rounds)

    def _parse_teams(text):
        """Lines like 'Team Alpha: user1, user2, user3' -> {label: [usernames]}"""
        out = {}
        for line in text.splitlines():
            if ":" not in line:
                continue
            label, names = line.split(":", 1)
            label = label.strip()[:60]
            users = [u.strip().lower() for u in re.split(r"[\s,;]+", names) if u.strip()]
            if label and users:
                out.setdefault(label, []).extend(users)
        return out

    @app.route("/admin/t/<int:tid>/enroll", methods=["POST"])
    @login_required("admin")
    def admin_enroll(tid):
        t = _tournament_or_404(tid)
        if t.status != "draft":
            flash("Enrolment is closed once the tournament starts.", "error")
            return redirect(url_for("admin_tournament", tid=tid))
        users = []
        batch = request.form.get("batch", "")
        if batch == "__all__":
            users = User.query.filter_by(role="student").all()
        elif batch:
            users = User.query.filter_by(role="student", batch=batch).all()
        names = [u.strip().lower() for u in re.split(r"[\s,;]+", request.form.get("usernames", "")) if u.strip()]
        if names:
            users += User.query.filter(User.role == "student", User.username.in_(names)).all()
        teams = _parse_teams(request.form.get("teams", "")) if t.participation == "team" else {}
        label_of = {}
        for label, usernames in teams.items():
            for u in User.query.filter(User.role == "student", User.username.in_(usernames)).all():
                users.append(u)
                label_of[u.id] = label
        have = {e.user_id: e for e in Enrollment.query.filter_by(tournament_id=t.id)}
        added = 0
        for u in users:
            if u.id not in have:
                en = Enrollment(tournament_id=t.id, user_id=u.id, team_label=label_of.get(u.id, ""))
                db.session.add(en)
                have[u.id] = en
                added += 1
            elif u.id in label_of:
                have[u.id].team_label = label_of[u.id]
        db.session.commit()
        flash(f"Enrolled {added} students.", "ok")
        return redirect(url_for("admin_tournament", tid=tid))

    @app.route("/admin/t/<int:tid>/unenroll", methods=["POST"])
    @login_required("admin")
    def admin_unenroll(tid):
        t = _tournament_or_404(tid)
        if t.status == "draft":
            Enrollment.query.filter_by(tournament_id=t.id, user_id=int(request.form["user_id"])).delete()
            db.session.commit()
        return redirect(url_for("admin_tournament", tid=tid))

    @app.route("/admin/t/<int:tid>/action", methods=["POST"])
    @login_required("admin")
    def admin_action(tid):
        t = _tournament_or_404(tid)
        action = request.form.get("action")
        try:
            if action == "start":
                services.start_tournament(t)
                flash("Tournament started. Round 1 is open.", "ok")
            elif action == "process":
                services.process_round(t)
                flash(f"Round {t.current_round} processed. Results are visible to students.", "ok")
            elif action == "next":
                dl = request.form.get("deadline")
                services.open_next_round(t, parse_ist_datetime(dl) if dl else None)
                flash(f"Round {t.current_round} is open.", "ok")
            elif action == "event":
                services.trigger_event(t, request.form.get("event", ""))
                flash("Event added to this round.", "ok")
            elif action == "remove_event":
                services.remove_event(t, request.form.get("event", ""))
            elif action == "settings":
                t.mode = "auto" if request.form.get("mode") == "auto" else "manual"
                t.interval_hours = max(1, min(24 * 14, int(request.form.get("interval_hours") or t.interval_hours)))
                if request.form.get("rank_w_profit"):
                    t.rank_w_profit = max(0, min(100, int(request.form["rank_w_profit"])))
                dl = request.form.get("deadline")
                if dl:
                    t.deadline = parse_ist_datetime(dl)
                elif t.mode == "auto" and t.round_state == "open" and not t.deadline and t.status == "active":
                    t.deadline = utcnow() + timedelta(hours=t.interval_hours)
                if t.mode == "manual":
                    t.deadline = None
                db.session.commit()
                flash("Settings saved.", "ok")
            elif action == "extend":
                hours = int(request.form.get("hours") or 24)
                base = max(t.deadline or utcnow(), utcnow())
                t.deadline = base + timedelta(hours=hours)
                db.session.commit()
                flash(f"Deadline extended by {hours} hours.", "ok")
        except services.GameError as e:
            flash(str(e), "error")
        except ValueError:
            flash("Check the numbers or date you entered.", "error")
        return redirect(url_for("admin_tournament", tid=tid))

    @app.route("/admin/t/<int:tid>/export")
    @login_required("admin")
    def admin_export(tid):
        """One row per company (student or team) per round. The game decides the columns
        through the generic fields below plus the raw decision and result as JSON."""
        import json
        t = _tournament_or_404(tid)
        members = services.members_by_participant(t)
        parts = {p.id: p for p in Participant.query.filter_by(tournament_id=t.id)}
        rows = []
        for r in Result.query.filter_by(tournament_id=t.id).order_by(Result.round_no).all():
            p = parts[r.participant_id]
            m = members.get(p.id, [])
            tot = r.data["totals"]
            rows.append([
                r.round_no, p.alias, p.group_no + 1,
                "; ".join(u.username for u in m), "; ".join(u.name for u in m),
                "yes" if r.data.get("submitted") else "no (autopilot)",
                round(tot["revenue"]) if "revenue" in tot else "", round(tot["profit"]),
                round(tot["volume_share"], 4) if "volume_share" in tot else "",
                tot["group_rank"], round(p.cash), r.reflection.replace("\n", " "),
                json.dumps(r.data.get("decision", {}), separators=(",", ":")),
            ])
        header = ["round", "company", "market_group", "usernames", "names", "submitted",
                  "revenue", "profit", "volume_share", "group_rank", "cash_now", "reflection",
                  "decision_json"]
        return csv_response(rows, header, f"tournament_{t.id}_results.csv")

    # ===== student =====

    def _mine_or_403(tid):
        """The tournament, my enrolment and the company (student or team) I play for."""
        t = db.session.get(Tournament, tid)
        en = Enrollment.query.filter_by(tournament_id=tid, user_id=g.user.id).first() if t else None
        if not t or not en or t.status == "draft" or not en.participant_id:
            abort(403)
        return t, en, db.session.get(Participant, en.participant_id)

    @app.route("/student")
    @login_required("student")
    def student_home():
        rows = (db.session.query(Tournament, Participant)
                .join(Enrollment, Enrollment.tournament_id == Tournament.id)
                .join(Participant, Participant.id == Enrollment.participant_id)
                .filter(Enrollment.user_id == g.user.id, Tournament.status != "draft")
                .order_by(Tournament.created_at.desc()).all())
        waiting = (db.session.query(Tournament).join(Enrollment, Enrollment.tournament_id == Tournament.id)
                   .filter(Enrollment.user_id == g.user.id, Tournament.status == "draft").all())
        return render_template("student_home.html", rows=rows, waiting=waiting)

    def _play_context(t, en, me_p, view_round):
        game = services.game_of(t)
        ctx = {"t": t, "en": en, "me_p": me_p, "game": game, "view_round": view_round,
               "mates": [e.user for e in Enrollment.query.filter_by(participant_id=me_p.id)]}
        past = [r.round_no for r in Result.query.filter_by(tournament_id=t.id, participant_id=me_p.id)
                .order_by(Result.round_no)]
        ctx["past"] = past
        ctx["is_open"] = t.status == "active" and t.round_state == "open" and view_round == t.current_round
        if ctx["is_open"]:
            mine = Decision.query.filter_by(tournament_id=t.id, participant_id=me_p.id,
                                            round_no=t.current_round).first()
            dec = mine.data if mine else game.default_decision(t.current_round)
            ctx["dec"] = dec
            ctx["submitted"] = bool(mine and mine.submitted)
            ctx["edited_by"] = db.session.get(User, mine.edited_by) if mine and mine.edited_by else None
            ctx["events"] = services.active_events(t, t.current_round)
            ctx["template"] = game.form_template(t.current_round)
            ctx.update(game.form_context(t, me_p, dec, t.current_round))
        else:
            res = Result.query.filter_by(tournament_id=t.id, participant_id=me_p.id,
                                         round_no=view_round).first()
            ctx["res"] = res
            if res:
                ids = [p.id for p in Participant.query.filter_by(tournament_id=t.id, group_no=me_p.group_no)]
                alias = {p.id: p.alias for p in Participant.query.filter(Participant.id.in_(ids))}
                group_res = {r.participant_id: r.data for r in Result.query.filter(
                    Result.tournament_id == t.id, Result.round_no == view_round,
                    Result.participant_id.in_(ids))}
                ctx["group_rows"] = sorted(
                    [(alias[pid], d, pid == me_p.id) for pid, d in group_res.items()],
                    key=lambda r: r[1]["totals"]["group_rank"])
                ctx["template"] = game.results_template(view_round)
                ctx["question"] = game.reflection_question(view_round)
        ctx.update(game.side_context(t, me_p, ctx.get("dec"), t.current_round if ctx["is_open"] else view_round,
                                     view_round, ctx["is_open"]))
        board = services.leaderboard(t)
        ctx["board"] = board[:10]
        ctx["board_pos"] = next((i for i, b in enumerate(board, 1) if b.id == me_p.id), None)
        ctx["board_n"] = len(board)
        return ctx

    @app.route("/play/<int:tid>")
    @login_required("student")
    def play(tid):
        t, en, me_p = _mine_or_403(tid)
        game = services.game_of(t)
        try:
            view_round = int(request.args.get("round", t.current_round))
        except ValueError:
            view_round = t.current_round
        ctx = _play_context(t, en, me_p, view_round)
        return render_template("play.html", **ctx, **game.template_globals())

    @app.route("/play/<int:tid>/action/<name>", methods=["POST"])
    @login_required("student")
    def game_action(tid, name):
        t, en, me_p = _mine_or_403(tid)
        if not (t.status == "active" and t.round_state == "open"):
            flash("This round is closed.", "error")
            return redirect(url_for("play", tid=tid))
        d = services.get_or_create_decision(t, me_p.id, t.current_round, g.user.id)
        new, msg, cat = services.game_of(t).handle_action(
            name, request.form, t, me_p, d.data, t.current_round)
        if new is not None:
            d.data = new
            d.edited_by = g.user.id
            db.session.commit()
        flash(msg, cat)
        return redirect(url_for("play", tid=tid) + "#p-reports")

    @app.route("/play/<int:tid>/submit", methods=["POST"])
    @login_required("student")
    def submit_decision(tid):
        t, en, me_p = _mine_or_403(tid)
        if not (t.status == "active" and t.round_state == "open"):
            flash("This round is closed.", "error")
            return redirect(url_for("play", tid=tid))
        d = services.get_or_create_decision(t, me_p.id, t.current_round, g.user.id)
        d.data = services.game_of(t).parse_form(request.form, t.current_round, d.data)
        d.submitted = True
        d.edited_by = g.user.id
        db.session.commit()
        flash("Decisions submitted. You can change them until the round closes."
              + (" Anyone on your team can edit them; the last submission counts."
                 if t.participation == "team" else ""), "ok")
        return redirect(url_for("play", tid=tid))

    @app.route("/play/<int:tid>/draft", methods=["POST"])
    @login_required("student")
    def save_draft(tid):
        """Save the form without submitting. Drafts are used by report tests, never by the round."""
        t, en, me_p = _mine_or_403(tid)
        if not (t.status == "active" and t.round_state == "open"):
            flash("This round is closed.", "error")
            return redirect(url_for("play", tid=tid))
        d = services.get_or_create_decision(t, me_p.id, t.current_round, g.user.id)
        d.data = services.game_of(t).parse_form(request.form, t.current_round, d.data)
        d.edited_by = g.user.id
        db.session.commit()
        flash("Draft saved. It is NOT submitted yet: only a submission counts when the round closes."
              if not d.submitted else "Changes saved and submitted.", "ok" if d.submitted else "error")
        return redirect(url_for("play", tid=tid))

    @app.route("/play/<int:tid>/reflect/<int:round_no>", methods=["POST"])
    @login_required("student")
    def reflect(tid, round_no):
        t, en, me_p = _mine_or_403(tid)
        res = Result.query.filter_by(tournament_id=t.id, participant_id=me_p.id, round_no=round_no).first()
        if not res:
            abort(404)
        res.reflection = request.form.get("reflection", "")[:2000]
        db.session.commit()
        flash("Reflection saved.", "ok")
        return redirect(url_for("play", tid=tid, round=round_no))

    @app.errorhandler(403)
    def forbidden(e):
        return render_template("error.html", code=403,
                               msg="You do not have access to this page."), 403

    @app.errorhandler(400)
    def bad_request(e):
        return render_template("error.html", code=400, msg=getattr(e, "description", "Bad request")), 400

    @app.errorhandler(404)
    def not_found(e):
        return render_template("error.html", code=404, msg="Page not found."), 404


app = create_app() if os.environ.get("CREATE_APP_ON_IMPORT", "1") == "1" else None

if __name__ == "__main__":
    app.run(debug=True)
