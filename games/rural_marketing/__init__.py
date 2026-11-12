"""MKTM679 Emerging Dimensions of Marketing: all 10 rounds.

Round by round: rural marketing mix (1-3), rural business models (4), AI-enabled CRM (5-6),
data-driven analytics (7-8), neuromarketing (9), experiential and immersive marketing (10).
"""
from ..base import Game
from ..registry import register
from . import concepts, display, engine, params, reports, schema


class RuralMarketing(Game):
    key = "rural_marketing"
    title = "Emerging Dimensions of Marketing"
    course_code = "MKTM679"
    summary = ("Run a packaged-goods company in rural and semi-urban India over 10 quarters. You design the "
               "product, buy the research you need, and win or lose by whether consumers accept it.")
    total_rounds = 10
    implemented_rounds = set(range(1, 11))
    events = engine.EVENTS

    # ----- rules -----
    def tournament_params(self, seed):
        return params.tournament_params(seed)

    def combine_events(self, keys):
        return engine.combine_events(keys)

    def default_decision(self, round_no):
        return engine.autopilot_decision()

    def unsubmitted_decision(self, saved, round_no):
        dec = engine.autopilot_decision()
        dec["reports"] = dict((saved or {}).get("reports") or {})
        return dec

    def parse_form(self, form, round_no, saved):
        saved = saved or {}
        dec = schema.parse(form, round_no, saved if saved.get("_draft") else None)
        dec["_draft"] = True
        dec["reports"] = dict(saved.get("reports") or {})
        dec["report_content"] = dict(saved.get("report_content") or {})
        return dec

    def run_round(self, round_no, players, tparams, mods):
        results = engine.run_round(round_no, players, tparams, mods)
        extra = {p["id"]: reports.cost_of(p["decision"].get("reports")) for p in players}
        results = engine.finalize(results, extra, mods.get("rank_w_profit", 0.6))
        for p in players:
            res = results[p["id"]]
            res["display"] = {"tables": display.build(res, round_no)}
        return results

    def debrief(self, result, round_no, submitted):
        return display.notes(result, round_no, submitted)

    def reflection_question(self, round_no):
        return display.ROUND_INFO[round_no]["reflect"]

    # ----- screens -----
    def form_template(self, round_no):
        return "game_form.html"

    def results_template(self, round_no):
        return "game_results.html"

    def template_globals(self):
        return {"EVENTS": engine.EVENTS, "ROUND_INFO": display.ROUND_INFO, "OVERHEAD": params.OVERHEAD, "SEG_FIXED": params.SEG_FIXED,
                "SEGMENTS": params.SEGMENTS, "SEG_LABEL": params.SEG_LABEL, "SEG_SHORT": params.SEG_SHORT,
                "PER": schema.PER}

    # ----- data the screens and reports need -----
    def _group_context(self, t, participant, round_no):
        from models import Decision, Participant, Result
        mates = Participant.query.filter_by(tournament_id=t.id, group_no=participant.group_no).all()
        ids = [m.id for m in mates]
        prev_own, prev_group = None, []
        if round_no > 1:
            rows = {r.participant_id: r.data for r in Result.query.filter(
                Result.tournament_id == t.id, Result.round_no == round_no - 1, Result.participant_id.in_(ids))}
            prev_own = rows.get(participant.id)
            for m in mates:
                if m.id in rows:
                    prev_group.append({"alias": m.alias, "result": rows[m.id], "decision": rows[m.id].get("decision", {}),
                                       "state": m.state or {}})
        rivals = [d.data for d in Decision.query.filter(
            Decision.tournament_id == t.id, Decision.round_no == round_no, Decision.participant_id.in_(ids),
            Decision.participant_id != participant.id) if d.data.get("_draft")]
        return prev_own, prev_group, rivals, len(mates)

    def _saved_and_last(self, t, participant, round_no):
        from models import Decision
        saved = Decision.query.filter_by(tournament_id=t.id, participant_id=participant.id, round_no=round_no).first()
        saved = saved.data if saved and saved.data.get("_draft") else None
        last = None
        if round_no > 1:
            prev = Decision.query.filter_by(tournament_id=t.id, participant_id=participant.id,
                                            round_no=round_no - 1, submitted=True).first()
            last = prev.data if prev else None
        return saved, last

    def form_context(self, t, participant, decision, round_no):
        saved, last = self._saved_and_last(t, participant, round_no)
        state = participant.state or {}
        values = schema.prefill(round_no, saved, last, state.get("last_lines"))
        locked = state.get("cats")
        cats = dict(zip(params.SLOTS, locked)) if locked else None
        mods = []
        for m in schema.modules_for(round_no):
            if m["id"] == "portfolio" and locked:
                continue
            keys, labels = schema.PER[m["per"]] if m["per"] else ([None], {})
            labels = dict(labels)
            if cats and m["per"] == "slot":
                labels = {sl: f"{sl.upper()}: {params.slot_labels(cats)[sl]}" for sl in params.SLOTS}
            if cats and m["per"] == "line":
                sn = params.slot_labels(cats)
                labels = {f"{sl}|{s}": f"{sn[sl]} in {params.SEG_SHORT[s]}" for sl in params.SLOTS for s in params.SEGMENTS}
            mods.append({"m": m, "keys": keys, "labels": labels, "values": values[m["id"]],
                         "new": m["round"] == round_no})
        cat_names = params.slot_labels(cats) if cats else {sl: None for sl in params.SLOTS}
        return {"modules": mods, "info": display.ROUND_INFO[round_no], "values": values, "has_draft": saved is not None,
                "locked_cats": cats, "cat_options": [(k, params.CAT_LABEL[k]) for k in params.CAT_KEYS],
                "cat_names": cat_names, "seg_short": params.SEG_SHORT, "slots": params.SLOTS}

    def side_context(self, t, participant, decision, round_no, view_round, is_open):
        """Everything the left-hand panels need: statements, free public data, paid report shop, purchases."""
        from models import Decision, Result
        prev_own, prev_group, rivals, n = self._group_context(t, participant, round_no)
        tp = params.tournament_params(t.seed)
        # financial statements: the round being viewed, else the latest processed round, else the opening position
        res = Result.query.filter_by(tournament_id=t.id, participant_id=participant.id).order_by(Result.round_no.desc())
        fin, fin_round = None, None
        for r in res:
            if r.round_no <= view_round and r.data.get("financials"):
                fin, fin_round = r.data["financials"], r.round_no
                break
        if fin is None:
            fin = engine.zero_financials(t.start_cash)
        public = [pr for pr in (reports.public_report(rid, t.seed, round_no, tp, prev_group, n)
                                for rid in reports.BY_ID) if pr]
        bought = (decision or {}).get("reports") or {} if is_open else {}
        content = (decision or {}).get("report_content") or {} if is_open else {}
        groups = {}
        for r in reports.available(round_no):
            feats = reports.features_of(r["id"])
            groups.setdefault(r["group"], []).append({
                "id": r["id"], "title": r["title"], "desc": r["desc"], "scope": r["scope"], "public": r["public"],
                "levels": r["levels"], "features": feats, "bought": r["id"] in bought,
                "bought_level": (bought.get(r["id"]) or {}).get("level") if isinstance(bought.get(r["id"]), dict) else None})
        archive = []
        for d in Decision.query.filter(Decision.tournament_id == t.id, Decision.participant_id == participant.id,
                                       Decision.round_no < round_no).order_by(Decision.round_no):
            for rc in (d.data.get("report_content") or {}).values():
                archive.append(rc)
        pubmap = {p["id"]: p for p in public}
        calcs = {}
        for rc in list(archive) + list((content or {}).values()):      # newest purchase wins
            if rc.get("calc"):
                calcs[rc["calc"]["kind"]] = rc["calc"]
        return {"fin": fin, "fin_round": fin_round, "public_reports": public, "pubmap": pubmap,
                "report_groups": groups, "report_now": list(content.values()), "report_archive": archive,
                "report_spent": reports.cost_of(bought),
                "report_consts": {"scale": reports.SCOPE_COST_SCALE, "ncat": len(params.CAT_KEYS), "nseg": len(params.SEGMENTS)},
                "cat_labels": params.CAT_LABEL, "seg_labels": params.SEG_SHORT,
                "concepts": concepts.SECTIONS, "price_calc": calcs.get("price"), "cost_calc": calcs.get("cost"), "lup_pp": None}

    def handle_action(self, name, form, t, participant, data, round_no):
        if name != "report":
            return None, "Unknown action.", "error"
        rid = form.get("report_id", "")
        try:
            li = int(form.get("level", 0))
        except ValueError:
            li = 0
        r = reports.BY_ID.get(rid)
        if not r or r["round"] > round_no or not (0 <= li < len(r["levels"])):
            return None, "That report is not available.", "error"
        data = dict(data)
        bought = dict(data.get("reports") or {})
        if rid in bought:
            return None, "You already bought that report this round.", "error"
        all_feats = [f["id"] for f in reports.features_of(rid)]
        feats = [x for x in form.getlist("feat") if x in all_feats]
        if all_feats and not feats:
            return None, "Tick at least one measure to include in the report.", "error"
        has_cat, has_seg = r["scope"] in ("cat", "catseg"), r["scope"] in ("seg", "catseg")
        cats = [x for x in form.getlist("cat") if x in params.CAT_KEYS] if has_cat else None
        segs = [x for x in form.getlist("seg") if x in params.SEGMENTS] if has_seg else None
        if has_cat and not cats:
            return None, "Choose at least one category.", "error"
        if has_seg and not segs:
            return None, "Choose at least one segment.", "error"
        saved, last = self._saved_and_last(t, participant, round_no)
        dec = schema.prefill(round_no, saved, last, (participant.state or {}).get("last_lines"))
        prev_own, prev_group, rivals, n = self._group_context(t, participant, round_no)
        tp = params.tournament_params(t.seed)
        content = reports.generate(rid, li, t.seed, participant.id, round_no, tp, participant.state or {}, dec,
                                   prev_own, prev_group, rivals, n, features=feats if all_feats else None, cats=cats, segs=segs)
        if not saved and r["id"] in ("concept", "pricetest", "offertest", "adtest"):
            content["note"] = "No saved draft was found, so this tested the default form values. " + content.get("note", "")
        bought[rid] = {"level": li, "cost": content["cost"], "features": feats, "cats": cats, "segs": segs}
        data["reports"] = bought
        data["report_content"] = {**(data.get("report_content") or {}), rid: content}
        return data, f"Bought: {r['title']} ({r['levels'][li]['name']}, Rs {content['cost']:,.0f}). The cost is charged when the round is processed.", "ok"


register(RuralMarketing())
