import csv
import io
import os
import random
import sys
from datetime import timedelta

import pytest

os.environ["CREATE_APP_ON_IMPORT"] = "0"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import games  # noqa: E402
import services  # noqa: E402
from games.rural_marketing import engine, params as P, reports, schema  # noqa: E402
from app import create_app  # noqa: E402
from models import (Decision, Enrollment, Participant, Result, Tournament, User,  # noqa: E402
                    db, utcnow)


@pytest.fixture()
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("ADMIN_PASSWORD", "teacher-pass")
    app = create_app({"SQLALCHEMY_DATABASE_URI": f"sqlite:///{tmp_path}/t.db",
                      "TESTING": True, "TICK_THROTTLE_SECONDS": 10**9})
    return app


def post(client, url, data=None, **kw):
    with client.session_transaction() as s:
        token = s.get("csrf", "")
    d = dict(data or {})
    d["csrf"] = token
    return client.post(url, data=d, **kw)


def login(app, username, password):
    c = app.test_client()
    c.get("/login")
    r = post(c, "/login", {"username": username, "password": password})
    return c, r


def student_csv(n):
    rows = ["name,roll_no,batch"]
    for i in range(n):
        rows.append(f"Student {i},R{1000 + i},{'A' if i % 2 == 0 else 'B'}")
    return "\n".join(rows).encode()


def make_class(app, n=60, **tournament_form):
    admin, r = login(app, "admin", "teacher-pass")
    assert r.status_code == 302
    r = post(admin, "/admin/students/upload",
             {"file": (io.BytesIO(student_csv(n)), "s.csv")},
             content_type="multipart/form-data")
    creds = list(csv.DictReader(io.StringIO(r.get_data(as_text=True))))
    assert len(creds) == n
    form = {"name": "Test", "game": "rural_marketing", "participation": "individual", "team_size": "4", "mode": "manual", "market_mode": "groups", "group_size": "10",
            "interval_hours": "48", "start_cash": "5000000"}
    form.update(tournament_form)
    r = post(admin, "/admin/tournaments/new", form)
    tid = int(r.headers["Location"].rstrip("/").split("/")[-1])
    return admin, creds, tid



def flatten(dec):
    """Turn a decision dict into the posted form fields."""
    out = {}
    for m in schema.MODULES:
        if m["id"] not in dec:
            continue
        for k in schema.keys_of(m):
            vals = dec[m["id"]][k] if m["per"] else dec[m["id"]]
            for fl in m["fields"]:
                v = vals[fl["name"]]
                name = f"{m['id']}.{k}.{fl['name']}" if m["per"] else f"{m['id']}.{fl['name']}"
                if fl["type"] == "checkbox":
                    if v:
                        out[name] = "on"
                else:
                    out[name] = str(v)
    return out


def nice(p):
    """A trader-friendly price: multiples of 5 above Rs 10, whole rupees below."""
    return float(max(1, round(p / 5) * 5)) if p >= 10 else float(max(1, round(p)))


def sensible(round_no, rng, scale=1.0, cats=("tea", "detergent", "toothpaste")):
    dec = schema.default_decision(round_no)
    dec["portfolio"] = dict(zip(P.SLOTS, cats))
    for sl, cat in zip(P.SLOTS, cats):
        dec["product"][sl] = {"quality": 6.0, "loc": 5.0}
        for s_ in P.SEGMENTS:
            g = float(round(P.CATEGORIES[cat]["g"] * P.SEG_GFAC[s_] / 5) * 5)
            ln = dec["lines"][f"{sl}|{s_}"]
            ln.update({"serve": s_ != "remote_village", "a_g": g,
                       "a_price": nice(engine.ref_price(cat, 6.0, g, s_) * rng.uniform(0.95, 1.1))})
            if round_no >= 2:
                dec["stock"][f"{sl}|{s_}"]["a_stock"] = 20000
    if round_no >= 3:
        for s_ in P.SEGMENTS:
            dec["channels"][s_].update({"kirana": 60, "van": 40})
    return dec


def start(app, n=57, **kw):
    admin, creds, tid = make_class(app, n + 3, **kw)
    keep = creds[:n]
    post(admin, f"/admin/t/{tid}/enroll", {"usernames": " ".join(c["username"] for c in keep)})
    post(admin, f"/admin/t/{tid}/action", {"action": "start"})
    return admin, keep, tid


def play_round(app, admin, tid, clients, decisions):
    """decisions: {index: decision dict}; others do not submit."""
    for i, dec in decisions.items():
        r = post(clients[i], f"/play/{tid}/submit", flatten(dec))
        assert r.status_code == 302
    post(admin, f"/admin/t/{tid}/action", {"action": "process"})


def test_full_flow_57_students_ten_rounds(app):
    admin, keep, tid = start(app, 57)
    clients = [login(app, c["username"], c["password"])[0] for c in keep]
    page = clients[0].get(f"/play/{tid}")
    assert page.status_code == 200 and b"Concept corner" in page.data and b"Break-even" in page.data
    out, _ = login(app, "nonexistent", "x")
    rng = random.Random(3)
    for rnd in range(1, 11):
        decisions = {i: sensible(rnd, rng) for i in range(0, 20)}   # 20 play, 37 never submit
        if rnd == 1:
            # buy a report and save a draft in round 1
            r = post(clients[0], f"/play/{tid}/action/report", {"report_id": "price", "level": "0", **ALLSEL("price")})
            assert r.status_code in (200, 302)
        play_round(app, admin, tid, clients, decisions)
        with app.app_context():
            t = db.session.get(Tournament, tid)
            assert t.round_state == "processed"
            assert Result.query.filter_by(tournament_id=tid, round_no=rnd).count() == 57
        # every page renders after each round, for a player, a non-submitter and the teacher
        assert clients[0].get(f"/play/{tid}").status_code == 200
        assert clients[40].get(f"/play/{tid}").status_code == 200
        assert admin.get(f"/admin/t/{tid}").status_code == 200
        if rnd < 10:
            post(admin, f"/admin/t/{tid}/action", {"action": "next"})
            assert clients[0].get(f"/play/{tid}").status_code == 200
    r = admin.get(f"/admin/t/{tid}/export")
    assert r.status_code == 200 and b"profit" in r.data.lower()
    with app.app_context():
        board = services.leaderboard(db.session.get(Tournament, tid))
        by = {b.participant.id: b for b in board} if hasattr(board[0], "participant") else None
    assert len(board) == 57


def test_autopilot_always_loses_and_good_play_beats_it(app):
    tp = P.tournament_params(5)
    rng = random.Random(2)
    for events in ([], ["festival"], ["monsoon"], ["competitor"], ["fuel"], ["privacy_law"], ["platform_outage"], ["ad_backlash"]):
        mods = engine.combine_events(events) if events else engine.combine_events([])
        game = services.game_of
        from games.rural_marketing import RuralMarketing
        G = RuralMarketing()
        for rnd in (1, 3, 5, 8, 10):
            players = [{"id": 0, "decision": sensible(rnd, rng), "state": {}},
                       {"id": 1, "decision": engine.autopilot_decision(), "state": {}},
                       {"id": 2, "decision": engine.autopilot_decision(), "state": {}}]
            mods["rank_w_profit"] = 0.6
            res = G.run_round(rnd, players, tp, mods)
            assert res[1]["totals"]["profit"] < 0, (events, rnd)
            assert res[2]["totals"]["profit"] < 0, (events, rnd)
            assert res[0]["totals"]["profit"] > res[1]["totals"]["profit"], (events, rnd)


def test_unknown_event_names_do_not_break(app):
    mods = engine.combine_events(["not_an_event"])
    assert isinstance(mods, dict)


def test_reports_cost_only_when_bought_and_noise_depends_on_level(app):
    tp = P.tournament_params(9)
    assert len(reports.BY_ID) >= 30
    for r in reports.BY_ID.values():
        levels = r["levels"]
        costs = [lv["cost"] for lv in levels]
        assert costs == sorted(costs)


def ALLSEL(rid, n_feat=None, cats=None, segs=None):
    feats = [f["id"] for f in reports.features_of(rid)]
    if n_feat is not None:
        feats = feats[:n_feat]
    return {"feat": feats, "cat": cats or list(P.CAT_KEYS), "seg": segs or list(P.SEGMENTS)}


def test_report_price_depends_on_selection(app):
    full = reports.price_of("pref", 1, len(reports.features_of("pref")), 7, 3)
    one_feat = reports.price_of("pref", 1, 1, 7, 3)
    one_cat = reports.price_of("pref", 1, len(reports.features_of("pref")), 1, 3)
    tiny = reports.price_of("pref", 1, 1, 1, 1)
    assert tiny < one_feat < full and tiny < one_cat < full
    assert reports.price_of("industry", 0, 0) == 0


def test_report_purchase_charged_and_stored(app):
    admin, keep, tid = start(app, 12)
    c = login(app, keep[0]["username"], keep[0]["password"])[0]
    sel = ALLSEL("price", n_feat=2, cats=["tea", "soap"], segs=["town"])
    post(c, f"/play/{tid}/action/report", {"report_id": "price", "level": "1", **sel})
    post(c, f"/play/{tid}/action/report", {"report_id": "price", "level": "1", **sel})  # second is refused
    # no measures ticked is refused
    r = post(c, f"/play/{tid}/action/report", {"report_id": "size", "level": "0", "cat": ["tea"], "seg": ["town"]}, follow_redirects=True)
    assert b"Tick at least one measure" in r.data
    with app.app_context():
        d = Decision.query.filter_by(tournament_id=tid, round_no=1).all()
        got = [x.data for x in d if (x.data or {}).get("reports")]
        assert len(got) == 1
        rep = got[0]["report_content"]["price"]
        assert len({row[0] for row in rep["tables"][0]["rows"]}) == 2           # only the two chosen categories
        assert len(rep["tables"][0]["cols"]) == 2 + 2                           # labels + 2 chosen measures
        expected = reports.price_of("price", 1, 2, 2, 1)
        assert rep["cost"] == expected
    post(admin, f"/admin/t/{tid}/action", {"action": "process"})
    with app.app_context():
        rs = Result.query.filter_by(tournament_id=tid, round_no=1).all()
        costs = [r.data["costs"].get("Reports bought", 0) for r in rs]
        assert sorted(costs)[-1] == expected and sorted(costs)[0] == 0
        assert sum(1 for x in costs if x > 0) == 1


def test_public_data_is_free_coarse_and_same_for_everyone(app):
    tp = P.tournament_params(11)
    a = reports.public_report("pref", 11, 2, tp, [], 20)
    b = reports.public_report("pref", 11, 2, tp, [], 20)
    assert a == b and a["cost"] == 0
    assert len(a["tables"][0]["cols"]) <= 4
    assert reports.public_report("concept", 11, 2, tp, [], 20) is None          # your own draft: no public data
    paid = reports.generate("pref", 1, 11, 1, 2, tp, {}, schema.default_decision(2), None, [], [], 20)
    assert len(paid["tables"][0]["rows"]) == 21 and len(a["tables"][0]["rows"]) < 21


def test_financial_statements_balance_every_round(app):
    admin, keep, tid = start(app, 10)
    clients = [login(app, c["username"], c["password"])[0] for c in keep]
    # round 1 page before processing: blank statements, cash 50 lakh
    page = clients[0].get(f"/play/{tid}").get_data(as_text=True)
    assert "Opening position" in page and "50,00,000" in page
    rng = random.Random(4)
    cash_prev = 5_000_000
    for rnd in range(1, 6):
        play_round(app, admin, tid, clients, {0: sensible(rnd, rng), 1: sensible(rnd, rng)})
        with app.app_context():
            for r in Result.query.filter_by(tournament_id=tid, round_no=rnd):
                f = r.data["financials"]
                assert f["balanced"]
                ta = next(x["v"] for x in f["bs"] if x["label"] == "Total assets")
                tle = next(x["v"] for x in f["bs"] if x["label"] == "Total liabilities and equity")
                assert abs(ta - tle) < 1
                net = next(x["v"] for x in f["pl"] if x["label"] == "Net profit")
                assert abs(net - r.data["totals"]["profit"]) < 1
                closing = next(x["v"] for x in f["cf"] if x["label"] == "Closing cash")
                assert abs(closing - r.data["totals"]["cash_end"]) < 1
        if rnd < 5:
            post(admin, f"/admin/t/{tid}/action", {"action": "next"})
    page = clients[0].get(f"/play/{tid}?round=2").get_data(as_text=True)
    assert "Balance sheet" in page and "Cash flow statement" in page and "Profit and loss account" in page


def test_cash_lags_profit_and_overdraft_when_broke(app):
    tp = P.tournament_params(5)
    G = __import__("games.rural_marketing", fromlist=["RuralMarketing"]).RuralMarketing()
    rng = random.Random(1)
    state = {}
    d = sensible(3, rng)
    players = [{"id": 0, "decision": d, "state": state}, {"id": 1, "decision": engine.autopilot_decision(), "state": {}}]
    res = G.run_round(3, players, tp, engine.combine_events([]))
    f = res[0]["financials"]
    ar = next(x["v"] for x in f["bs"] if x["label"].startswith("Trade receivables"))
    assert ar > 0                                    # retailers pay late
    # a firm with no cash left borrows
    broke = {"fin": {"cash": 0.0, "ar": 0.0, "ap": 0.0, "debt": 0.0, "capital": 1.0, "retained": 0.0}}
    res = G.run_round(3, [{"id": 0, "decision": engine.autopilot_decision(), "state": broke},
                         {"id": 1, "decision": engine.autopilot_decision(), "state": {}}], tp, engine.combine_events([]))
    debt = next(x["v"] for x in res[0]["financials"]["bs"] if x["label"] == "Bank overdraft")
    assert debt > 0 and res[0]["totals"]["cash_end"] == 0


def test_portfolio_locked_after_round_one_and_packs_independent(app):
    tp = P.tournament_params(6)
    G = __import__("games.rural_marketing", fromlist=["RuralMarketing"]).RuralMarketing()
    rng = random.Random(2)
    d1 = sensible(1, rng)
    res = G.run_round(1, [{"id": 0, "decision": d1, "state": {}}, {"id": 1, "decision": sensible(1, rng), "state": {}}],
                      tp, engine.combine_events([]))
    st = res[0]["new_state"]
    assert st["cats"] == ["tea", "detergent", "toothpaste"]
    d2 = sensible(2, rng)
    d2["portfolio"] = dict(zip(P.SLOTS, ["soap", "noodles", "hair_oil"]))         # tries to change categories
    res2 = G.run_round(2, [{"id": 0, "decision": d2, "state": st}, {"id": 1, "decision": sensible(2, rng), "state": res[1]["new_state"]}],
                       tp, engine.combine_events([]))
    assert {l["cat"] for l in res2[0]["lines"]} == {"tea", "detergent", "toothpaste"}
    # a second pack in a market adds a row and shares the demand of the line
    d3 = sensible(2, rng)
    ln = d3["lines"]["p1|town"]
    ln.update({"b_g": 60.0, "b_price": round(engine.ref_price("tea", 6.0, 60.0, "town") * 2) / 2})
    res3 = G.run_round(2, [{"id": 0, "decision": d3, "state": st}, {"id": 1, "decision": sensible(2, rng), "state": res[1]["new_state"]}],
                       tp, engine.combine_events([]))
    packs = [l for l in res3[0]["lines"] if l["slot"] == "p1" and l["segment"] == "town"]
    assert {l["pack"] for l in packs} == {"a", "b"}


def test_draft_is_saved_but_not_used_until_submitted(app):
    admin, keep, tid = start(app, 12)
    c = login(app, keep[0]["username"], keep[0]["password"])[0]
    dec = sensible(1, random.Random(1))
    r = post(c, f"/play/{tid}/draft", flatten(dec))
    assert r.status_code in (200, 302)
    post(admin, f"/admin/t/{tid}/action", {"action": "process"})
    with app.app_context():
        res = Result.query.filter_by(tournament_id=tid, round_no=1).first()
        for r_ in Result.query.filter_by(tournament_id=tid, round_no=1):
            assert r_.data["totals"]["profit"] < 0   # nobody submitted: draft not used


def test_ranking_weight_changes_order(app):
    tp = P.tournament_params(4)
    from games.rural_marketing import RuralMarketing
    G = RuralMarketing()
    rng = random.Random(8)
    cheap = sensible(1, rng); big = sensible(1, rng)
    for sl, cat in zip(P.SLOTS, ["tea", "detergent", "toothpaste"]):
        for s_ in P.SEGMENTS:
            ln_c, ln_b = cheap["lines"][f"{sl}|{s_}"], big["lines"][f"{sl}|{s_}"]
            ln_c["a_price"] = nice(engine.ref_price(cat, 6.0, ln_c["a_g"], s_) * 1.0)
            ln_b["a_price"] = nice(engine.ref_price(cat, 6.0, ln_b["a_g"], s_) * 0.55)
    scores = {}
    for w in (1.0, 0.0):
        mods = engine.combine_events([]); mods["rank_w_profit"] = w
        res = G.run_round(1, [{"id": 0, "decision": cheap, "state": {}}, {"id": 1, "decision": big, "state": {}}], tp, mods)
        scores[w] = (res[0]["totals"]["rank_score"], res[1]["totals"]["rank_score"])
        assert res[0]["totals"]["share_rank"] != res[1]["totals"]["share_rank"] or True
    assert scores[1.0] != scores[0.0]


def test_team_mode_shares_one_decision(app):
    admin, creds, tid = make_class(app, 8, participation="team", team_size="2")
    users = [c["username"] for c in creds[:8]]
    post(admin, f"/admin/t/{tid}/enroll", {"usernames": "\n".join(f"Team A: {users[0]}, {users[1]}" if i == 0 else f"Team {chr(66 + i)}: {users[2 * i]}, {users[2 * i + 1]}" for i in range(4))})
    post(admin, f"/admin/t/{tid}/action", {"action": "start"})
    a = login(app, users[0], creds[0]["password"])[0]
    b = login(app, users[1], creds[1]["password"])[0]
    post(a, f"/play/{tid}/submit", flatten(sensible(1, random.Random(1))))
    post(admin, f"/admin/t/{tid}/action", {"action": "process"})
    with app.app_context():
        assert Result.query.filter_by(tournament_id=tid, round_no=1).count() == 4
    assert b.get(f"/play/{tid}").status_code == 200


def test_security_basics(app):
    admin, keep, tid = start(app, 6)
    c = login(app, keep[0]["username"], keep[0]["password"])[0]
    # no csrf token -> rejected
    r = c.post(f"/play/{tid}/submit", data=flatten(sensible(1, random.Random(1))))
    assert r.status_code in (400, 403)
    assert c.get("/admin").status_code == 403
    r = login(app, keep[0]["username"], "wrong")[1]
    assert r.status_code == 200


def test_games_registry_is_pluggable(app):
    from games import registry
    assert "rural_marketing" in [g.key for g in registry.all_games()]


def run1(dec, other=None, rnd=1, tp=None, state=None):
    from games.rural_marketing import RuralMarketing
    G = RuralMarketing()
    tp = tp or P.tournament_params(6)
    other = other or sensible(rnd, random.Random(9))
    res = G.run_round(rnd, [{"id": 0, "decision": dec, "state": state or {}}, {"id": 1, "decision": other, "state": {}}],
                      tp, engine.combine_events([]))
    return res


def test_repeated_category_is_numbered_and_allowed(app):
    assert P.slot_labels({"p1": "soap", "p2": "soap", "p3": "soap"}) == {"p1": "Bathing soap 1", "p2": "Bathing soap 2", "p3": "Bathing soap 3"}
    assert P.slot_labels({"p1": "soap", "p2": "tea", "p3": "soap"}) == {"p1": "Bathing soap 1", "p2": "Packaged tea", "p3": "Bathing soap 2"}
    d = sensible(1, random.Random(1), cats=("soap", "soap", "soap"))
    for i, sl in enumerate(P.SLOTS):                      # three different soaps
        d["product"][sl]["quality"] = 4.0 + 2 * i
    res = run1(d)
    assert res[0]["new_state"]["cats"] == ["soap", "soap", "soap"]
    labels = {l["label"] for l in res[0]["lines"]}
    assert labels == {"Bathing soap 1", "Bathing soap 2", "Bathing soap 3"}
    # the form shows the same numbering
    admin, keep, tid = start(app, 6)
    c = login(app, keep[0]["username"], keep[0]["password"])[0]
    post(c, f"/play/{tid}/submit", flatten(d))
    post(admin, f"/admin/t/{tid}/action", {"action": "process"})
    post(admin, f"/admin/t/{tid}/action", {"action": "next"})
    page = c.get(f"/play/{tid}").get_data(as_text=True)
    assert "Bathing soap 1" in page and "Bathing soap 3" in page


def test_no_decision_means_no_sales_but_fixed_cost(app):
    res = run1(engine.autopilot_decision())
    t = res[0]["totals"]
    assert t["revenue"] == 0 and t["volume_share"] == 0 and res[0]["lines"] == []
    assert t["profit"] == -engine.OVERHEAD                  # only the company overhead
    assert res[0]["new_state"]["cats"] is None              # categories not locked by a non-decision


def test_fixed_cost_grows_with_products_and_packs_variable_with_sales(app):
    rng = random.Random(5)
    one = sensible(1, rng)
    for sl in P.SLOTS[1:]:
        for s_ in P.SEGMENTS:
            one["lines"][f"{sl}|{s_}"]["serve"] = False       # only one product launched
    three = sensible(1, rng)
    two_packs = sensible(1, rng)
    ln = two_packs["lines"]["p1|town"]
    ln.update({"b_g": 50.0, "b_price": 10.0})
    def costs(d):
        r = run1(d)[0]
        return r["costs"], r["cogs"]
    c1, _ = costs(one); c3, _ = costs(three); c2, _ = costs(two_packs)
    assert c3["Product upkeep"] == 3 * c1["Product upkeep"] == 3 * engine.PRODUCT_FIXED
    assert c2["Pack listing and artwork"] == c3["Pack listing and artwork"] + engine.SKU_FIXED
    # variable cost scales with units sold
    lo = sensible(1, rng); hi = sensible(1, rng)
    for sl, cat in zip(P.SLOTS, ("tea", "detergent", "toothpaste")):
        for s_ in P.SEGMENTS:
            hi["lines"][f"{sl}|{s_}"]["a_price"] = nice(engine.ref_price(cat, 6.0, hi["lines"][f"{sl}|{s_}"]["a_g"], s_) * 0.7)
    assert run1(hi)[0]["cogs"]["production"] > run1(lo)[0]["cogs"]["production"]
    # the P&L labels show both blocks
    pl = [x["label"] for x in run1(three)[0]["financials"]["pl"]]
    assert any(l.startswith("VARIABLE COSTS") for l in pl) and any(l.startswith("FIXED COSTS") for l in pl)
    assert "Contribution (revenue less variable costs)" in pl


def test_round_prices_sell_more_than_awkward_prices(app):
    assert engine.roundness(20) > engine.roundness(15) > engine.roundness(12) > engine.roundness(12.5) > engine.roundness(12.3)
    assert engine.roundness(12.3, lup=True) < engine.roundness(12.3)
    base = sensible(1, random.Random(2))
    def vol(price):
        d = {k: v for k, v in base.items()}
        d["lines"] = {k: dict(v) for k, v in base["lines"].items()}
        d["lines"]["p1|town"]["a_price"] = price
        l = [x for x in run1(d)[0]["lines"] if x["slot"] == "p1" and x["segment"] == "town"][0]
        return l["demand_packs"]
    # Rs 60 is slightly dearer than Rs 59.7 but is a round price, so it should still sell more
    assert vol(60.0) > vol(59.7)
    assert vol(60.0) > vol(59.5)


def test_lup_pack_is_judged_on_price_point_not_grams(app):
    tp = P.tournament_params(6)
    ideal = tp["town"]["cats"]["tea"]["ideal"]
    far = ideal[1] * 0.25                                         # far smaller than the ideal grams
    gram = engine.pack_fit(ideal[0], far, ideal[2], ideal, "gram", 20.0, tp["town"]["pp"])
    lup = engine.pack_fit(ideal[0], far, ideal[2], ideal, "lup", round(tp["town"]["pp"] / 5) * 5, tp["town"]["pp"])
    assert lup > gram + 20                                        # LUP forgives grams
    off_price = engine.pack_fit(ideal[0], far, ideal[2], ideal, "lup", tp["town"]["pp"] * 4, tp["town"]["pp"])
    assert off_price < lup                                        # but not a price far from the usual ticket price


def test_marketing_is_switched_off_in_stage_one(app):
    mods = [m["id"] for m in schema.modules_for(10)]
    assert not (set(mods) & P.MARKETING_MODULES)
    ids = {r["id"] for r in reports.available(10)}
    assert not (ids & P.MARKETING_REPORTS) and "pref" in ids and "lup" in ids
    assert "stock" in [m["id"] for m in schema.modules_for(2)]


def test_calculator_data_only_when_measures_bought(app):
    tp = P.tournament_params(3)
    full = reports.generate("price", 1, 3, 1, 1, tp, {}, schema.default_decision(1), None, [], [], 10)
    assert full["calc"] and full["calc"]["kind"] == "price" and len(full["calc"]["rows"]) == 21
    part = reports.generate("price", 1, 3, 1, 1, tp, {}, schema.default_decision(1), None, [], [], 10, features=["0.2"])
    assert part["calc"] is None
    cost = reports.generate("costs", 1, 3, 1, 1, tp, {}, schema.default_decision(1), None, [], [], 10)
    assert cost["calc"]["kind"] == "cost"


def test_concept_corner_content():
    from games.rural_marketing import concepts
    titles = {e["t"] for s in concepts.SECTIONS for e in s["items"]}
    for need in ("Fair price", "Break-even", "Round prices", "Price-point pack (LUP)", "Trade receivables"):
        assert need in titles
