"""Game-independent tournament logic: teams, start, process (manual or automatic),
next round, events, leaderboard. Each game supplies its own rules through games.<key>."""
import random
from datetime import timedelta

import games
from models import (Decision, Enrollment, EventLog, Participant, Result,
                    Tournament, db, utcnow)


class GameError(Exception):
    pass


def game_of(t):
    return games.get(t.game_key)


def active_events(t, round_no):
    return [e.key for e in EventLog.query.filter_by(tournament_id=t.id, round_no=round_no)]


# ---------- teams and start ----------

def _form_units(t, enrolled, rng):
    """Return a list of (label, [enrollments]) - one per competing company."""
    if t.participation != "team":
        return [("", [en]) for en in enrolled]
    labelled, loose = {}, []
    for en in enrolled:
        if en.team_label:
            labelled.setdefault(en.team_label, []).append(en)
        else:
            loose.append(en)
    units = [(label, members) for label, members in labelled.items()]
    rng.shuffle(loose)
    size = max(2, t.team_size)
    chunks = [loose[i:i + size] for i in range(0, len(loose), size)]
    # a leftover single student joins the previous automatic team instead of playing alone
    if len(chunks) > 1 and len(chunks[-1]) == 1:
        chunks[-2].extend(chunks.pop())
    units += [("", c) for c in chunks]
    return units


def start_tournament(t):
    if t.status != "draft":
        raise GameError("Tournament has already started.")
    game = game_of(t)
    enrolled = Enrollment.query.filter_by(tournament_id=t.id).all()
    rng = random.Random(t.seed)
    units = _form_units(t, enrolled, rng)
    if len(units) < 2:
        raise GameError("You need at least 2 competing " +
                        ("teams" if t.participation == "team" else "students") + " to start.")
    rng.shuffle(units)
    n_groups = max(1, round(len(units) / max(2, t.group_size))) if t.market_mode == "groups" else 1
    prefix = "Team" if t.participation == "team" else "Player"
    for i, (label, members) in enumerate(units):
        p = Participant(tournament_id=t.id, alias=label or f"{prefix} {i + 1:03d}",
                        group_no=i % n_groups, cash=float(t.start_cash),
                        state={"fin": {"cash": float(t.start_cash), "ar": 0.0, "ap": 0.0, "debt": 0.0,
                                       "capital": float(t.start_cash), "retained": 0.0}})
        db.session.add(p)
        db.session.flush()
        for en in members:
            en.participant_id = p.id
    t.status = "active"
    _open_round(t, 1)
    db.session.commit()


def _open_round(t, round_no, deadline=None):
    t.current_round = round_no
    t.round_state = "open"
    if t.mode == "auto":
        t.deadline = deadline or utcnow() + timedelta(hours=t.interval_hours)
    elif deadline:
        t.deadline = deadline


# ---------- decisions ----------

def get_or_create_decision(t, participant_id, round_no, user_id=None):
    d = Decision.query.filter_by(tournament_id=t.id, participant_id=participant_id,
                                 round_no=round_no).first()
    if not d:
        d = Decision(tournament_id=t.id, participant_id=participant_id, round_no=round_no,
                     data=game_of(t).default_decision(round_no), submitted=False,
                     edited_by=user_id)
        db.session.add(d)
        db.session.flush()
    return d


def _effective_decision(t, participant_id, round_no):
    """Submitted decision, or the game's punishing default for a non-submitter."""
    d = Decision.query.filter_by(tournament_id=t.id, participant_id=participant_id,
                                 round_no=round_no).first()
    if d and d.submitted:
        return d.data, True
    return game_of(t).unsubmitted_decision(d.data if d else None, round_no), False


# ---------- processing ----------

def process_round(t):
    """Run the current round for every market group and store the results."""
    if t.status != "active" or t.round_state != "open":
        raise GameError("There is no open round to process.")
    rnd = t.current_round
    if rnd not in game_of(t).implemented_rounds:
        raise GameError(f"Round {rnd} is not built yet.")
    # Claim the round atomically so two workers can never process it twice.
    claimed = Tournament.query.filter_by(id=t.id, status="active", round_state="open").update(
        {"round_state": "processing"})
    db.session.commit()
    if not claimed:
        raise GameError("This round is already being processed.")
    try:
        _process_claimed(t, rnd)
    except Exception:
        db.session.rollback()
        Tournament.query.filter_by(id=t.id).update({"round_state": "open"})
        db.session.commit()
        raise


def _process_claimed(t, rnd):
    game = game_of(t)
    events = active_events(t, rnd)
    mods = game.combine_events(events)
    mods["rank_w_profit"] = (t.rank_w_profit if t.rank_w_profit is not None else 60) / 100.0
    tparams = game.tournament_params(t.seed)
    groups = {}
    for p in Participant.query.filter_by(tournament_id=t.id):
        groups.setdefault(p.group_no, []).append(p)
    for members in groups.values():
        players, submitted = [], {}
        for p in members:
            dec, sub = _effective_decision(t, p.id, rnd)
            players.append({"id": p.id, "decision": dec, "state": p.state or {}})
            submitted[p.id] = sub
        out = game.run_round(rnd, players, tparams, mods)
        for p in members:
            res = out[p.id]
            res["events"] = events
            dec_used = dict(next(x["decision"] for x in players if x["id"] == p.id))
            dec_used.pop("report_content", None)      # keep results small
            res["decision"] = dec_used
            p.state = res.pop("new_state", p.state)
            res["submitted"] = submitted[p.id]
            res["debrief"] = game.debrief(res, rnd, submitted[p.id])
            existing = Result.query.filter_by(tournament_id=t.id, participant_id=p.id,
                                              round_no=rnd).first()
            if existing:
                existing.data = res
            else:
                db.session.add(Result(tournament_id=t.id, participant_id=p.id,
                                      round_no=rnd, data=res))
            p.cash = res["totals"].get("cash_end", (p.cash or 0) + res["totals"]["profit"])
    t.round_state = "processed"
    if rnd >= t.total_rounds:
        t.status = "finished"
    db.session.commit()


def open_next_round(t, deadline=None):
    if t.status != "active" or t.round_state != "processed":
        raise GameError("Process the current round before opening the next one.")
    nxt = t.current_round + 1
    if nxt > t.total_rounds:
        raise GameError("All rounds are finished.")
    if nxt not in game_of(t).implemented_rounds:
        raise GameError(f"Round {nxt} is not built yet.")
    _open_round(t, nxt, deadline)
    db.session.commit()


# ---------- events ----------

def trigger_event(t, key):
    if key not in game_of(t).events:
        raise GameError("Unknown event.")
    rnd = t.current_round
    if t.status != "active" or t.round_state != "open":
        raise GameError("Events can only be added to the round that is currently open.")
    if not EventLog.query.filter_by(tournament_id=t.id, round_no=rnd, key=key).first():
        db.session.add(EventLog(tournament_id=t.id, round_no=rnd, key=key))
        db.session.commit()


def remove_event(t, key):
    if t.round_state != "open":
        raise GameError("Events can only be removed while the round is open.")
    EventLog.query.filter_by(tournament_id=t.id, round_no=t.current_round, key=key).delete()
    db.session.commit()


# ---------- automatic rounds ----------

def tick():
    """Automatic rounds: process any open round whose deadline has passed, then open the next.
    Safe to call often; it does nothing when there is nothing due."""
    now = utcnow()
    due = Tournament.query.filter(
        Tournament.status == "active", Tournament.mode == "auto",
        Tournament.round_state == "open", Tournament.deadline <= now).all()
    done = 0
    for t in due:
        try:
            deadline = t.deadline
            process_round(t)
            done += 1
            nxt = t.current_round + 1
            if (t.status == "active" and nxt <= t.total_rounds
                    and nxt in game_of(t).implemented_rounds):
                _open_round(t, nxt, deadline + timedelta(hours=t.interval_hours))
                db.session.commit()
        except GameError:
            db.session.rollback()
    return done


class Standing:
    """One company's position in the tournament: cumulative profit and average market share
    combined into one rank score."""
    def __init__(self, p):
        self.id, self.alias, self.group_no, self.cash = p.id, p.alias, p.group_no, p.cash
        self.cum_profit, self.avg_share, self.rounds = 0.0, 0.0, 0
        self.rank_score, self.profit_rank, self.share_rank, self.rank = 0.0, 0, 0, 0


def leaderboard(t):
    """Tournament standings ranked by profit AND market share (weights set per tournament)."""
    parts = Participant.query.filter_by(tournament_id=t.id).all()
    st = {p.id: Standing(p) for p in parts}
    for r in Result.query.filter_by(tournament_id=t.id).all():
        s_ = st.get(r.participant_id)
        if s_:
            s_.cum_profit += r.data["totals"]["profit"]
            s_.avg_share += r.data["totals"].get("volume_share", 0.0)
            s_.rounds += 1
    rows = list(st.values())
    for s_ in rows:
        s_.avg_share = s_.avg_share / s_.rounds if s_.rounds else 0.0
    n = len(rows)
    w = (t.rank_w_profit if t.rank_w_profit is not None else 60) / 100.0

    def pct(sorted_rows):
        return {s_.id: (1 - i / (n - 1)) if n > 1 else 1.0 for i, s_ in enumerate(sorted_rows)}
    by_profit = sorted(rows, key=lambda s_: -s_.cum_profit)
    by_share = sorted(rows, key=lambda s_: -s_.avg_share)
    pp, ps = pct(by_profit), pct(by_share)
    for i, s_ in enumerate(by_profit, 1):
        s_.profit_rank = i
    for i, s_ in enumerate(by_share, 1):
        s_.share_rank = i
    for s_ in rows:
        s_.rank_score = w * pp[s_.id] + (1 - w) * ps[s_.id]
    rows.sort(key=lambda s_: (-s_.rank_score, -s_.cum_profit))
    for i, s_ in enumerate(rows, 1):
        s_.rank = i
    return rows


def members_by_participant(t):
    """{participant_id: [User, ...]}"""
    out = {}
    for en in Enrollment.query.filter_by(tournament_id=t.id).all():
        if en.participant_id:
            out.setdefault(en.participant_id, []).append(en.user)
    return out
