"""Market engine for MKTM679 (all 10 rounds). Pure functions, no database.

Idea in one paragraph: students CREATE a product (quality, pack size in grams, localisation) and
set prices. Each segment secretly has an ideal product. A product is scored 0-100 for fit; consumers
only buy if the fit passes an acceptance threshold (a smooth cut-off at 45). Among accepted
products, demand is split by relative price and fit; marketing, distribution, partners, CRM,
positioning, digital, creative and experience levers lift a firm's own volume. Several effects are
shared across students (price level, ad crowding, 3PL capacity, SHG pool, acquisition cost,
digital auction, trust), so one student's decision changes everyone's result.
"""
import math

from .params import (AP_SHARE, AR_SHARE, CATEGORIES, CAT_KEYS, DEFAULT_CATS, OVERDRAFT_RATE, PACK_FIXED_COST,  # noqa: F401
                     PACK_FIXED_PRICE, PACKS, PRODUCT_FIXED, SKU_FIXED, SLOTS, START_CASH, slot_labels,
                     CH, CHANNELS, DIGITAL, DIGITAL_CPM, DIGITAL_CTR, DIGITAL_CVR,  # noqa: F401
                     DIGITAL_K, DIGITAL_R, GROWTH, MEDIA, MEDIA_K, MEDIA_R, OVERHEAD, PRICE_MAX,
                     PRICE_MIN, REACH_CAP, RFM, SEG, SEG_FIXED, SEG_SHORT, SEGMENTS, TAU, THETA,
                     TOUCH, TOUCH_DIGITAL, TOUCH_K, TOUCH_PHYSICAL, TOUCH_W, new_state)


UMBRELLA = 2.0     # brand-level promotion is spread over a three-product portfolio


def sig(x):
    return 1.0 / (1.0 + math.exp(-max(-30.0, min(30.0, x))))


def clamp(x, lo, hi):
    return max(lo, min(hi, x))


def get(d, *path, default=0.0):
    for k in path:
        if not isinstance(d, dict) or k not in d:
            return default
        d = d[k]
    return d


# ---------- product, price, fit ----------

def unit_cost(cat, q, grams, loc):
    c = CATEGORIES[cat]
    return grams * (0.040 + 0.0105 * q) * c["pm"] * c["k"] * (1 + 0.02 * loc) + PACK_FIXED_COST


def ref_price(cat, q, grams, seg):
    return grams * (0.075 + 0.019 * q) * SEG[seg]["pm"] * CATEGORIES[cat]["pm"] + PACK_FIXED_PRICE


def dist_cost(seg, grams):
    return SEG[seg]["dist"] * 1.2 * (grams / 100.0) ** 0.7


def fit_score(q, grams, loc, ideal, gtol=0.5):
    z = ((q - ideal[0]) / 2.0) ** 2 + (math.log(max(grams, 1.0) / ideal[1]) / gtol) ** 2 + ((loc - ideal[2]) / 2.5) ** 2
    return 100.0 * math.exp(-0.5 * z)


def roundness(price, lup=False):
    """Traders like prices that need no change: Rs 10, 20, 25 are best, then other multiples of 5, then whole rupees."""
    p = round(price, 2)
    if p >= 10 and abs(p % 10) < 1e-9:
        r = 1.0
    elif p >= 5 and abs(p % 5) < 1e-9:
        r = 0.8
    elif abs(p % 1) < 1e-9:
        r = 0.35
    elif abs((p * 2) % 1) < 1e-9:
        r = 0.0
    else:
        r = -0.4
    if lup and r < 0.8:
        r -= 0.6        # a price-point pack must sit on a coin-friendly price
    return r


def pack_fit(q, grams, loc, ideal, ptype="gram", price=None, pp=None):
    """Fit of one pack. A gram pack is judged on its grams. A price-point pack is judged mainly on the price point
    and its value, so grams matter much less, but the price must be near the segment's usual ticket price."""
    if ptype == "lup":
        f = fit_score(q, grams, loc, ideal, gtol=1.4)
        if price and pp:
            aff = math.exp(-0.5 * (math.log(price / pp) / 0.6) ** 2)
            f *= 0.4 + 0.6 * aff
        return f
    return fit_score(q, grams, loc, ideal)


def acceptance(fit):
    return sig((fit - THETA) / TAU)


def line_keys():
    return [f"{sl}|{s}" for sl in SLOTS for s in SEGMENTS]


def autopilot_decision():
    """Used when a student or team submits nothing. No product was designed, so nothing is sold,
    but the company still pays its fixed overhead."""
    return {"_auto": True}


def cats_of(dec, st):
    """The three categories a firm sells: locked after round 1."""
    if st.get("cats"):
        return dict(zip(SLOTS, st["cats"]))
    port = dec.get("portfolio") or {}
    return {sl: (port.get(sl) if port.get(sl) in CATEGORIES else dflt) for sl, dflt in zip(SLOTS, DEFAULT_CATS)}


def packs_of(dec, slot, seg):
    """Active packs of one product in one segment: [{'k','g','price','w'}]."""
    ln = (dec.get("lines") or {}).get(f"{slot}|{seg}")
    if not ln or not ln.get("serve", False):
        return []
    out = []
    for k in PACKS:
        g, pr = float(ln.get(k + "_g", 0.0) or 0.0), float(ln.get(k + "_price", 0.0) or 0.0)
        if g > 0 and pr > 0:
            w = get(dec, "push", f"{slot}|{seg}", k + "_w", default=50.0)
            tp_ = ln.get(k + "_type", "gram")
            out.append({"k": k, "g": g, "price": pr, "w": max(0.0, float(w)), "type": tp_ if tp_ in ("gram", "lup") else "gram"})
    return out


def _norm(weights):
    tot = sum(weights.values())
    if tot <= 0:
        return None
    return {k: v / tot for k, v in weights.items()}


def _focus(dec):
    f = _norm({s: max(0.0, float(get(dec, "focus", s, "share", default=0.0))) for s in SEGMENTS})
    return f or {s: 1.0 / len(SEGMENTS) for s in SEGMENTS}


# ---------- main round ----------

def run_round(round_no, players, tparams, mods):
    """players: [{"id", "decision", "state"}] for ONE market. Returns {id: result}."""
    n = len(players)
    wp = mods.get("rank_w_profit", 0.6)
    growth = GROWTH ** (round_no - 1)
    P = {}
    for p in players:
        st = {**new_state(), **(p.get("state") or {})}
        dec = p["decision"]
        cats = cats_of(dec, st)
        prod = {sl: {"q": float(get(dec, "product", sl, "quality", default=5.0)), "loc": float(get(dec, "product", sl, "loc", default=0.0))}
                for sl in SLOTS}
        P[p["id"]] = {"dec": dec, "st": st, "cats": cats, "labels": slot_labels(cats), "prod": prod, "focus": _focus(dec), "cost": {}, "m": {}}
    others = lambda pid: [x for x in P if x != pid]

    # ----- shared aggregates -----
    def spend_x(pid, section, key):      # lakhs of rupees aimed at each segment
        return {s: max(0.0, float(get(P[pid]["dec"], section, key, "spend", default=0.0))) * P[pid]["focus"][s] / 1e5 / UMBRELLA
                for s in SEGMENTS}
    media_x = {pid: {m: spend_x(pid, "media", m) for m in MEDIA} for pid in P}
    dig_x = {pid: {c: spend_x(pid, "digital", c) for c in DIGITAL} for pid in P}
    touch_x = {pid: {k: spend_x(pid, "experience", k) for k in TOUCH} for pid in P}

    # ----- per-player effects that do not depend on volume -----
    for pid, d in P.items():
        dec, st = d["dec"], d["st"]
        # media (Round 2): reach with diminishing returns and crowding from rivals' spend
        ad_media = {s: 0.0 for s in SEGMENTS}
        if "media" in dec:
            for si, s in enumerate(SEGMENTS):
                miss = 1.0
                for m in MEDIA:
                    x = media_x[pid][m][s]
                    crowd = 1.0 + 0.4 * sum(media_x[o][m][s] for o in others(pid)) / max(1, n - 1)
                    miss *= 1 - MEDIA_R[m][si] * (1 - math.exp(-MEDIA_K[m] * x / crowd))
                ad_media[s] = 1 - miss
            d["cost"]["Media and promotion"] = sum(float(get(dec, "media", m, "spend")) for m in MEDIA)
        d["ad_media"] = ad_media

        # digital + ML (Round 8)
        ad_dig = {s: 0.0 for s in SEGMENTS}
        dig_tab = []
        if "digital" in dec:
            ml = max(0.0, float(get(dec, "digital_g", "ml")))
            tg = clamp(float(get(dec, "digital_g", "targeting")), 0, 10)
            ab = clamp(float(get(dec, "digital_g", "abtests")), 0, 5)
            pts = st["customers"] if st["customers"] else sum(st["last_packs"].values()) / 3.0
            dataq = min(1.0, pts / 20000.0)
            auc = 0.5 + 0.32 * (1 - math.exp(-ml / 70000.0)) * (0.35 + 0.65 * dataq) * (0.6 + 0.4 * st["data"])
            over = max(0.0, ml / 100000.0 - 2.0 * dataq)
            auc = clamp(auc - 0.06 * over, 0.5, 0.9)
            tf = (1 + 3 * (auc - 0.5) * tg / 10.0) * (1 - 0.04 * tg) * (1 + 0.04 * min(3, ab))
            outage = mods.get("digital_mult", 1.0)
            tot_imp = tot_clk = tot_conv = tot_sp = 0.0
            for ci, c in enumerate(DIGITAL):
                sp = max(0.0, float(get(dec, "digital", c, "spend")))
                crowd = 1.0 + 0.5 * sum(max(0.0, float(get(P[o]["dec"], "digital", c, "spend"))) for o in P) / max(1, n) / 1e5
                imp = sp / DIGITAL_CPM[c] * 1000.0 / crowd
                clk = imp * DIGITAL_CTR[c] * (1 + 3 * (auc - 0.5)) * outage
                conv = clk * DIGITAL_CVR[c] * tf
                tot_imp += imp; tot_clk += clk; tot_conv += conv; tot_sp += sp
                dig_tab.append([DIGITAL_LABEL_[c], sp, imp, clk, (clk / imp if imp else 0), conv,
                                (sp / conv if conv else None), (sp / clk if clk else None)])
            for si, s in enumerate(SEGMENTS):
                miss = 1.0
                for c in DIGITAL:
                    x = dig_x[pid][c][s]
                    crowd = 1.0 + 0.5 * sum(dig_x[o][c][s] for o in P) / max(1, n)
                    miss *= 1 - DIGITAL_R[c][si] * (1 - math.exp(-DIGITAL_K[c] * x / crowd))
                ad_dig[s] = clamp((1 - miss) * tf * outage, 0.0, 1.0)
            d["cost"]["Digital campaigns"] = tot_sp
            d["cost"]["ML model and A/B tests"] = ml + 20000.0 * ab
            d["m"]["digital"] = {"auc": auc, "tf": tf, "rows": dig_tab, "impressions": tot_imp,
                                 "clicks": tot_clk, "conversions": tot_conv, "spend": tot_sp, "ml": ml,
                                 "targeting": tg, "abtests": ab}
        d["ad_dig"] = ad_dig

        # creative (Round 9)
        cmult = {s: 1.0 for s in SEGMENTS}
        manip = 0.0
        if "creative" in dec:
            cr = dec["creative"]
            emo, rat, cue, story = (float(get(cr, k)) for k in ("emotion", "rational", "brand_cue", "story"))
            manip = clamp(float(get(cr, "manipulation")), 0, 10)
            prodn = max(0.0, float(get(cr, "production")))
            pq = 1 - math.exp(-prodn / 150000.0)
            mem = math.exp(-0.5 * ((cue - 6.0) / 3.0) ** 2)
            rows, liked = [], []
            for s in SEGMENTS:
                ie = tparams[s]["ad_ideal"]
                fit_ad = 100 * math.exp(-0.5 * (((emo - ie[0]) / 2.5) ** 2 + ((rat - ie[1]) / 2.5) ** 2 + ((story - ie[2]) / 2.5) ** 2))
                score = fit_ad / 100.0 * (0.6 + 0.4 * mem) * (0.7 + 0.3 * pq)
                cmult[s] = max(0.2, 0.35 + 1.3 * score)
                like = sig((fit_ad - 40.0) / 10.0)
                liked.append(like)
                rows.append([SEG_SHORT[s], fit_ad, like, mem, score, cmult[s]])
            d["cost"]["Ad production"] = prodn
            d["m"]["creative"] = {"rows": rows, "manip": manip, "avg_like": sum(liked) / len(liked)}
        d["cmult"], d["manip"] = cmult, manip

        # positioning (Round 7)
        d["pos"] = {s: 0.0 for s in SEGMENTS}
        if "position" in dec:
            pp, bn = float(get(dec, "position", "price_pos")), float(get(dec, "position", "benefit"))
            moved = 0.0
            if st["position"]:
                moved = math.hypot(pp - st["position"][0], bn - st["position"][1])
            d["cost"]["Positioning communication"] = 40000.0 + 25000.0 * moved
            d["position_now"] = (pp, bn)

        # product upkeep, reformulation and localisation upkeep (per launched product)
        live = [sl for sl in SLOTS if any(packs_of(dec, sl, s_) for s_ in SEGMENTS)]
        n_packs = sum(len(packs_of(dec, sl, s_)) for sl in SLOTS for s_ in SEGMENTS)
        d["live"] = live
        d["cost"]["Product upkeep"] = PRODUCT_FIXED * len(live)
        d["cost"]["Pack listing and artwork"] = SKU_FIXED * n_packs
        d["cost"]["Localisation upkeep"] = sum(20000.0 * d["prod"][sl]["loc"] for sl in live)
        reform = 0.0
        for sl in live:
            old = (st.get("products") or {}).get(sl)
            if old:
                reform += 100000.0 * (abs(d["prod"][sl]["q"] - old[0]) / 10.0 + abs(d["prod"][sl]["loc"] - old[1]) / 10.0)
        d["cost"]["Product reformulation"] = reform

    # positioning scores need every rival's position
    for pid, d in P.items():
        if "position_now" not in d:
            continue
        pp, bn = d["position_now"]
        crowds = [math.exp(-0.5 * ((pp - P[o]["position_now"][0]) ** 2 + (bn - P[o]["position_now"][1]) ** 2) / 1.5 ** 2)
                  for o in others(pid) if "position_now" in P[o]]
        crowd = sum(crowds) / len(crowds) if crowds else 0.25
        rows = []
        for s in SEGMENTS:
            ip = tparams[s]["pos_ideal"]
            match = math.exp(-0.5 * (((pp - ip[0]) / 2.0) ** 2 + ((bn - ip[1]) / 2.0) ** 2))
            d["pos"][s] = 1.0 * (match - 0.45) - 0.9 * (crowd - 0.25)
            rows.append([SEG_SHORT[s], match, d["pos"][s]])
        d["m"]["position"] = {"rows": rows, "crowd": crowd, "pos": (pp, bn)}

    # experience (Round 10): novelty fades as more rivals use the same touchpoint
    for pid, d in P.items():
        d["exp"] = {s: 0.0 for s in SEGMENTS}
        dec = d["dec"]
        if "experience" in dec:
            integ = clamp(float(get(dec, "exp_g", "integration")), 0, 10)
            story = clamp(float(get(dec, "exp_g", "story")), 0, 10)
            used = {k for k in TOUCH if float(get(dec, "experience", k, "spend")) > 0}
            syn = 1 + 0.25 * integ / 10.0 if (used & TOUCH_PHYSICAL) and (used & TOUCH_DIGITAL) else 1.0
            rows = []
            for si, s in enumerate(SEGMENTS):
                tot = 0.0
                for k in TOUCH:
                    adopt = sum(1 for o in others(pid) if float(get(P[o]["dec"], "experience", k, "spend")) > 0) / max(1, n - 1)
                    novelty = 1.0 / (1.0 + 2.0 * adopt)
                    tot += TOUCH_W[k][si] * (1 - math.exp(-TOUCH_K[k] * touch_x[pid][k][s])) * novelty
                score = min(1.0, tot * syn * (0.85 + 0.03 * story))
                eff = score * sig((score - 0.2) / 0.07)
                d["exp"][s] = eff
                rows.append([SEG_SHORT[s], score, eff])
            d["cost"]["Experiential marketing"] = sum(float(get(dec, "experience", k, "spend")) for k in TOUCH)
            d["m"]["experience"] = {"rows": rows, "synergy": syn}

    # ----- CRM (Round 5): customers, churn, loyalty -----
    acq_all = [max(0.0, float(get(P[x]["dec"], "crm", "acquisition"))) for x in P if "crm" in P[x]["dec"]]
    mean_acq = sum(acq_all) / max(1, n)
    req_priv = 5.0 + mods.get("privacy_req_bump", 0.0)
    overcontact, shortfalls = [], []
    for pid, d in P.items():
        dec, st = d["dec"], d["st"]
        d["lam"] = st["loyalty"]
        if "crm" in dec:
            a = max(0.0, float(get(dec, "crm", "acquisition")))
            r = max(0.0, float(get(dec, "crm", "retention")))
            cdp = clamp(float(get(dec, "crm", "cdp")), 0, 10)
            priv = clamp(float(get(dec, "crm", "privacy")), 0, 10)
            n0 = st["customers"] if st["customers"] else max(1000.0, sum(st["last_packs"].values()) / 3.0)
            cac = 150.0 * (1 + 0.8 * mean_acq / 150000.0) * (1 - 0.15 * st["data"])
            newc = a / cac
            poach = clamp(0.08 * (sum(max(0.0, float(get(P[o]["dec"], "crm", "acquisition"))) for o in others(pid)) / max(1, n - 1)) / 150000.0, 0, 0.15)
            churn = clamp(0.35 * math.exp(-(r / n0) / 40.0) + poach, 0.04, 0.5)
            n1 = n0 * (1 - churn) + newc
            d["crm"] = {"n0": n0, "n1": n1, "cac": cac, "newc": newc, "churn": churn, "poach": poach,
                        "retention": r, "acq": a, "cdp": cdp, "priv": priv}
            d["lam"] = n1 / (n1 + 20000.0)
            short = max(0.0, req_priv - priv)
            shortfalls.append(short / 10.0)
            d["cost"]["Customer acquisition"] = a
            d["cost"]["Customer retention"] = r
            d["cost"]["Customer data platform"] = 15000.0 * cdp
            d["cost"]["Privacy compliance"] = 8000.0 * priv
            if short > 0:
                d["cost"]["Privacy fine"] = 30000.0 * short
            d["data_new"] = clamp(0.75 * st["data"] + 0.09 * cdp, 0, 1)
        if "offer" in dec:
            overcontact.append(max(0.0, float(get(dec, "offer", "frequency")) - 4) / 8.0)

    # ----- partners (Round 4): SHG pool is shared and allocated by commitment -----
    partner_add = {pid: {s: 0.0 for s in SEGMENTS} for pid in P}
    fpo_eff, agg_share = {}, {}
    mean_agg = sum(clamp(float(get(P[x]["dec"], "partner_g", "aggregator")), 0, 60) for x in P) / max(1, n)
    if any("partners" in P[x]["dec"] for x in P):
        for si, s in enumerate(SEGMENTS):
            req = {pid: max(0.0, float(get(P[pid]["dec"], "partners", s, "shg"))) for pid in P}
            wt = {pid: req[pid] * (1 + max(0.0, float(get(P[pid]["dec"], "partners", s, "incentive"))) / 1500.0) for pid in P}
            pool = 6.0 * n
            tot_req, tot_wt = sum(req.values()), sum(wt.values())
            for pid, d in P.items():
                if "partners" not in d["dec"]:
                    continue
                got = req[pid] if tot_req <= pool else min(req[pid], pool * wt[pid] / tot_wt)
                shg = d["st"]["shg"][s] * 0.85 + got
                fr_req = max(0.0, float(get(d["dec"], "partners", s, "franchise")))
                fr = d["st"]["franchise"][s] * 0.95 + fr_req
                inc = max(0.0, float(get(d["dec"], "partners", s, "incentive")))
                d.setdefault("partners", {})[s] = {"req": req[pid], "got": got, "shg": shg, "fr": fr, "fr_new": fr_req}
                partner_add[pid][s] = clamp(0.22 * [0.6, 1.0, 1.0][si] * (1 - math.exp(-shg / 12.0))
                                            + 0.18 * [1.0, 0.8, 0.4][si] * (1 - math.exp(-fr / 10.0)), 0, 0.5)
                d["cost"]["SHG training and incentives"] = d["cost"].get("SHG training and incentives", 0.0) + 3000.0 * got + inc * shg
                d["cost"]["Franchise set-up"] = d["cost"].get("Franchise set-up", 0.0) + 20000.0 * fr_req
        for pid, d in P.items():
            if "partner_g" in d["dec"]:
                fp = max(0.0, float(get(d["dec"], "partner_g", "fpo")))
                fpo_eff[pid] = 1 - math.exp(-fp / 200000.0)
                agg_share[pid] = clamp(float(get(d["dec"], "partner_g", "aggregator")), 0, 60)
                d["cost"]["FPO tie-up"] = fp
    commission = 0.08 + 0.10 * mean_agg / 60.0

    # ----- channels and segment sales (two passes for 3PL congestion) -----
    cong = {s: 1.0 for s in SEGMENTS}
    stock_mode = round_no >= 2
    pack_out = {pid: {} for pid in P}      # (slot, seg, pack) -> numbers
    firm_seg = {pid: {} for pid in P}      # seg -> availability, uplift, ad effect
    seg_info = {}
    trust0 = next(iter(P.values()))["st"]["trust"]
    dmult = lambda s_: mods.get("demand_mult", {}).get(s_, 1.0)
    for _pass in range(2):
        tpl_load = {s: 0.0 for s in SEGMENTS}
        for si, s in enumerate(SEGMENTS):
            sp, tp = SEG[s], tparams[s]
            lines = {pid: {sl: packs_of(P[pid]["dec"], sl, s) for sl in SLOTS} for pid in P}
            active = [pid for pid in P if any(lines[pid][sl] for sl in SLOTS)]
            availd, distm, up_f, ad_f = {}, {}, {}, {}
            for pid in active:
                d = P[pid]
                if "channels" in d["dec"]:
                    w = _norm({c: max(0.0, float(get(d["dec"], "channels", s, c))) for c in CHANNELS}) or {"kirana": 1.0}
                    cov = 0.0
                    cmult = 0.0
                    for c in CHANNELS:
                        wc = w.get(c, 0.0)
                        cv = CH[c]["cov"][si]
                        cs = CH[c]["cost"][si]
                        if c == "tpl":
                            cv = cv / (cong[s] ** 0.7)
                            cs = cs * cong[s] ** 0.5
                        cov += wc * cv
                        cmult += wc * cs
                    dev = 1 + 0.25 * (1 - math.exp(-max(0.0, float(get(d["dec"], "channels", s, "invest"))) / 120000.0))
                    av = min(0.98, cov * dev)
                    d["tpl_w_" + s] = w.get("tpl", 0.0)
                else:
                    av, cmult = sp["a0"], 1.0
                    d["tpl_w_" + s] = 0.0
                av = 1 - (1 - av) * (1 - partner_add[pid][s]) * (1 - 0.15 * (agg_share.get(pid, 0.0) / 60.0) * [1.0, 0.6, 0.3][si])
                availd[pid], distm[pid] = min(0.98, av), cmult
                ad = 1 - (1 - d["ad_media"][s]) * (1 - d["ad_dig"][s])
                ad = clamp(ad * d["cmult"][s], 0.0, 1.0)
                fp = fpo_eff.get(pid, 0.0)
                ad_f[pid] = ad
                up_f[pid] = math.exp(1.3 * ad + 0.8 * (availd[pid] - sp["a0"]) + 0.010 * (d["st"]["brand"] - 20.0)
                                     + 0.6 * d["lam"] + 0.5 * d["pos"][s] + 0.9 * d["exp"][s]
                                     + (0.15 * fp if si > 0 else 0.0) + 0.03 * d["manip"])
            # every pack on offer, grouped by category
            offers = {}
            for pid in active:
                d = P[pid]
                for sl in SLOTS:
                    cat = d["cats"][sl]
                    for pk in lines[pid][sl]:
                        pr = d["prod"][sl]
                        rp = ref_price(cat, pr["q"], pk["g"], s)
                        pk = {**pk, "price": clamp(pk["price"], PRICE_MIN * rp, PRICE_MAX * rp)}
                        fit = pack_fit(pr["q"], pk["g"], pr["loc"], tp["cats"][cat]["ideal"], pk["type"], pk["price"], tp["pp"])
                        offers.setdefault(cat, {}).setdefault(pid, []).append(
                            {**pk, "slot": sl, "pi": pk["price"] / rp, "fit": fit, "acc": acceptance(fit), "rp": rp,
                             "round": roundness(pk["price"], pk["type"] == "lup")})
            wbar = {}
            for pid in active:
                ws = [pk["w"] for sl in SLOTS for pk in lines[pid][sl]]
                wbar[pid] = (sum(ws) / len(ws)) if ws and sum(ws) > 0 else 1.0
            cat_info = {}
            for cat, byf in offers.items():
                allp = [pk for lst in byf.values() for pk in lst]
                mean_pi = sum(pk["pi"] for pk in allp) / len(allp)
                cw = tp["cats"][cat]
                size = (tp["base"] * n * cw["w"] * growth * dmult(s) * (mean_pi ** -sp["eps"]) * (0.55 + 0.45 * trust0))
                beta = cw["beta"] * mods.get("beta_mult", 1.0)
                for pk in allp:
                    pk["e"] = math.exp(-beta * math.log(pk["pi"] / mean_pi) + math.log(max(pk["fit"], 5.0) / 50.0)
                                       + (0.45 if pk["type"] == "lup" else 0.2) * pk["round"])
                firm_e = {}
                for pid, lst in byf.items():
                    es = sorted((pk["e"] for pk in lst), reverse=True)
                    firm_e[pid] = es[0] + (0.25 * es[1] if len(es) > 1 else 0.0)
                tot = sum(firm_e.values()) or 1.0
                cap = REACH_CAP * tp["base"] * cw["w"] * (7.0 / 3.0) * growth * dmult(s)
                for pid, lst in byf.items():
                    d = P[pid]
                    avgw = sum(pk["w"] for pk in lst) / len(lst)
                    le = clamp((avgw / wbar[pid]) ** 0.5, 0.5, 1.8) if avgw > 0 else 0.5
                    inner = [pk["e"] * ((pk["w"] / avgw) ** 0.8 if avgw > 0 else 1.0) for pk in lst]
                    itot = sum(inner) or 1.0
                    acc_line = sum(i / itot * pk["acc"] for i, pk in zip(inner, lst))
                    vol = min(size * firm_e[pid] / tot * acc_line * up_f[pid] * le, cap)
                    for i, pk in zip(inner, lst):
                        v = vol * i / itot
                        tpl_load[s] += v * d["tpl_w_" + s]
                        pack_out[pid][(pk["slot"], s, pk["k"])] = {
                            "eq": v, "pi": pk["pi"], "fit": pk["fit"], "acc": pk["acc"], "share": firm_e[pid] / tot,
                            "cat": cat, "g": pk["g"], "price": pk["price"], "rp": pk["rp"], "w": pk["w"], "type": pk["type"], "round": pk["round"]}
                cat_info[cat] = {"mean_pi": mean_pi, "size": size, "firms": len(byf)}
            for pid in active:
                firm_seg[pid][s] = {"avail": availd[pid], "dist_mult": distm[pid], "up": up_f[pid], "ad": ad_f[pid]}
            seg_info[s] = {"cats": cat_info, "firms": len(active)}
        for si, s in enumerate(SEGMENTS):
            cap = 0.5 * tparams[s]["base"] * n * growth
            cong[s] = max(1.0, tpl_load[s] / cap) if cap else 1.0
            if s in seg_info:
                seg_info[s]["congestion"] = cong[s]

    # ----- costs, profit per player -----
    seg_total_eq = {s: sum(po["eq"] for pid in P for (sl, ss, k), po in pack_out[pid].items() if ss == s) for s in SEGMENTS}
    group_vol = 0.0
    for pid, d in P.items():
        dec = d["dec"]
        lines_out = []
        res_segs = {s: {"serve": False, "price_index": None, "fit": None, "accept": None, "avail": None, "adeff": 0.0,
                        "uplift": None, "share": 0.0, "demand_packs": 0.0, "packs_sold": 0.0, "stock": None,
                        "unsold": 0.0, "unmet": 0.0, "revenue": 0.0, "var_cost": 0.0, "contribution": 0.0,
                        "_eq": 0.0, "_pi": 0.0, "_fit": 0.0, "_acc": 0.0} for s in SEGMENTS}
        revenue = var_cost = vol_total = prod_cost = dist_total = 0.0
        for (sl, s, k), o in sorted(pack_out[pid].items(), key=lambda x: (SLOTS.index(x[0][0]), SEGMENTS.index(x[0][1]), x[0][2])):
            cat, pr, fs = d["cats"][sl], d["prod"][sl], firm_seg[pid][s]
            demand_packs = o["eq"] * CATEGORIES[cat]["g"] / o["g"]
            if stock_mode and "stock" in dec:
                stock = max(0.0, float(get(dec, "stock", f"{sl}|{s}", k + "_stock")))
                sold, produced = min(demand_packs, stock), stock
            else:
                stock, sold, produced = None, demand_packs, demand_packs
            fpo_cut = 0.05 * fpo_eff.get(pid, 0.0)
            ucost = unit_cost(cat, pr["q"], o["g"], pr["loc"]) * (1 - fpo_cut)
            dist = dist_cost(s, o["g"]) * fs["dist_mult"] * mods.get("dist_mult", 1.0)
            rev = sold * o["price"]
            comm = 0.0
            if pid in agg_share:
                comm += rev * agg_share[pid] / 100.0 * commission
            if "partners" in dec and s in dec["partners"]:
                comm += rev * 0.05 * (1 - math.exp(-d["partners"][s]["fr"] / 10.0))
            pc = produced * ucost - 0.5 * (produced - sold) * ucost      # leftovers cleared at 50% of cost
            dc = sold * dist + comm
            sold_eq = o["eq"] * (sold / demand_packs if demand_packs else 0.0)
            lines_out.append({
                "slot": sl, "cat": cat, "label": d["labels"][sl], "type": o["type"], "roundness": o["round"],
                "segment": s, "pack": k, "grams": o["g"], "price": o["price"], "fair_price": o["rp"],
                "price_index": o["pi"], "fit": o["fit"], "accept": o["acc"], "weight": o["w"],
                "demand_packs": demand_packs, "stock": stock, "packs_sold": sold,
                "unsold": (produced - sold) if stock is not None else 0.0,
                "unmet": max(0.0, demand_packs - sold) if stock is not None else 0.0,
                "revenue": rev, "var_cost": pc + dc, "contribution": rev - pc - dc,
                "unit_cost": ucost + dist, "unit_contrib": o["price"] - ucost - dist, "cm_pct": (o["price"] - ucost - dist) / o["price"]})
            rs = res_segs[s]
            rs["serve"] = True
            rs["demand_packs"] += demand_packs
            rs["packs_sold"] += sold
            rs["unsold"] += lines_out[-1]["unsold"]
            rs["unmet"] += lines_out[-1]["unmet"]
            rs["revenue"] += rev
            rs["var_cost"] += pc + dc
            rs["adeff"], rs["uplift"], rs["avail"] = fs["ad"], fs["up"], fs["avail"]
            rs["_eq"] += sold_eq
            rs["_pi"] += o["pi"] * demand_packs
            rs["_fit"] += o["fit"] * o["eq"]
            rs["_acc"] += o["acc"] * o["eq"]
            if stock is not None:
                rs["stock"] = (rs["stock"] or 0.0) + stock
            revenue += rev
            var_cost += pc + dc
            prod_cost += pc
            dist_total += dc
            vol_total += sold_eq
        for s in SEGMENTS:
            rs = res_segs[s]
            if rs["serve"]:
                rs["price_index"] = rs["_pi"] / rs["demand_packs"] if rs["demand_packs"] else None
                eqs = sum(o["eq"] for (sl, ss, k), o in pack_out[pid].items() if ss == s)
                rs["fit"] = rs["_fit"] / eqs if eqs else None
                rs["accept"] = rs["_acc"] / eqs if eqs else None
                rs["share"] = rs["_eq"] / seg_total_eq[s] if seg_total_eq[s] else 0.0
                rs["contribution"] = rs["revenue"] - rs["var_cost"]
            for kx in ("_eq", "_pi", "_fit", "_acc"):
                rs.pop(kx)
        if "channels" in dec:
            d["cost"]["Channel development"] = sum(max(0.0, float(get(dec, "channels", s_, "invest"))) for s_ in SEGMENTS)
        d["vol_total"] = vol_total
        group_vol += vol_total
        d["revenue"], d["var_cost"], d["res_segs"], d["lines_out"] = revenue, var_cost, res_segs, lines_out
        d["cogs_prod"], d["cogs_dist"] = prod_cost, dist_total

    # ----- offers (Round 6) and CRM economics, then trust, state, rank -----
    for pid, d in P.items():
        dec, st = d["dec"], d["st"]
        anc_rev = anc_cost = 0.0
        opt_out_total = 0.0
        if "offer" in dec and "crm" in d:
            of = dec["offer"]
            prem, disc = clamp(float(get(of, "premium")), 0, 10), clamp(float(get(of, "discount")), 0, 40)
            pers_b, freq = max(0.0, float(get(of, "personal"))), clamp(float(get(of, "frequency")), 0, 12)
            pers_eff = (1 - math.exp(-pers_b / 100000.0)) * (0.5 + 0.5 * st["data"])
            fat = 1 - math.exp(-0.10 * max(0.0, freq - 2))
            B = 60.0
            padd = B * (0.6 + 0.08 * prem) * (1 - disc / 100.0)
            cadd = B * (0.30 + 0.045 * prem)
            rows = []
            for g in RFM:
                rp = tparams["rfm"][g]
                ng = d["crm"]["n1"] * rp["share"]
                targeted = bool(get(of, "target_" + g, default=False))
                fit_o = 100 * math.exp(-0.5 * (((prem - rp["ideal"][0]) / 2.5) ** 2 + ((disc - rp["ideal"][1]) / 10.0) ** 2))
                acc_o = sig((fit_o - 45.0) / 10.0)
                if targeted:
                    attach = clamp(rp["attach"] * acc_o * (1 + 0.6 * pers_eff) * (1 - fat) * st["trust"], 0, 0.9)
                    buyers = ng * attach
                    opt = min(0.2 * ng, ng * 0.012 * max(0.0, freq - 4) ** 2)
                    anc_rev += buyers * padd
                    anc_cost += buyers * cadd + ng * 3 * freq * 0.5
                    opt_out_total += opt
                else:
                    attach, buyers, opt = 0.0, 0.0, 0.0
                rows.append([RFM_LABEL_[g], ng, targeted, fit_o, acc_o, attach, buyers, buyers * (padd - cadd)])
            d["cost"]["Personalisation (AI)"] = pers_b
            d["m"]["offer"] = {"rows": rows, "padd": padd, "cadd": cadd, "freq": freq, "opt_out": opt_out_total,
                               "pers_eff": pers_eff}
        d["anc_rev"], d["anc_cost"], d["opt_out"] = anc_rev, anc_cost, opt_out_total

    # trust is shared by the whole market
    manips = [d["manip"] for d in P.values() if "creative" in d["dec"]]
    mean_manip = sum(manips) / len(manips) if manips else 0.0
    trust_prev = next(iter(P.values()))["st"]["trust"]
    trust = clamp(trust_prev + 0.03 - 0.05 * max(0.0, mean_manip - 3.5)
                  - 0.06 * (sum(overcontact) / len(overcontact) if overcontact else 0.0)
                  - 0.05 * (sum(shortfalls) / len(shortfalls) if shortfalls else 0.0)
                  - mods.get("trust_hit", 0.0), 0.5, 1.0)

    for pid, d in P.items():
        dec, st = d["dec"], d["st"]
        costs = {k: v for k, v in d["cost"].items() if v}
        costs["Company overhead"] = OVERHEAD
        costs["Segment fixed costs"] = SEG_FIXED * sum(1 for r in d["res_segs"].values() if r["serve"])
        if d["manip"] > 7:
            costs["Regulator fine (manipulative ads)"] = 50000.0 * (d["manip"] - 7)
        profit = d["revenue"] + d["anc_rev"] - d["var_cost"] - d["anc_cost"] - sum(costs.values())
        d["costs_pre_reports"] = costs
        d["profit_pre_reports"] = profit
        # state for the next round
        brand = 0.85 * st["brand"]
        brand += 12.0 * (sum(max(r["adeff"], 0) for r in d["res_segs"].values() if r["serve"]) / max(1, sum(1 for r in d["res_segs"].values() if r["serve"])))
        if "creative" in dec:
            brand += -4.0 if d["m"]["creative"]["avg_like"] < 0.35 else 0.0
            brand -= 6.0 if d["manip"] > 7 else 0.0
        if "experience" in dec:
            brand += 10.0 * sum(d["exp"].values()) / 3.0
        ns = dict(st)
        ns.update({
            "brand": clamp(brand, 0, 100), "trust": trust,
            "cats": st["cats"] if st.get("cats") else ([d["cats"][sl] for sl in SLOTS] if not dec.get("_auto") else None),
            "products": {sl: [d["prod"][sl]["q"], d["prod"][sl]["loc"]] for sl in SLOTS if sl in d["live"]} or st.get("products") or {},
            "last_lines": {f"{l['slot']}|{l['segment']}|{l['pack']}": l["packs_sold"] for l in d["lines_out"]},
            "last_packs": {s: float(r.get("packs_sold") or 0.0) for s, r in d["res_segs"].items()},
            "loyalty": d["lam"] + (0.25 * sum(d["exp"].values()) / 3.0 * (1 - d["lam"]) if "experience" in dec else 0.0),
        })
        if "position_now" in d:
            ns["position"] = list(d["position_now"])
        if "partners" in d:
            ns["shg"] = {s: d["partners"][s]["shg"] for s in SEGMENTS if s in d["partners"]}
            ns["franchise"] = {s: d["partners"][s]["fr"] for s in SEGMENTS if s in d["partners"]}
        if "crm" in d:
            c = d["crm"]
            n1 = max(0.0, c["n1"] - d["opt_out"])
            contrib = d["revenue"] - d["var_cost"]
            m = contrib / n1 if n1 else 0.0
            clv = m * (1 - c["churn"]) / (c["churn"] + 0.02)
            ns.update({"customers": n1, "churn": c["churn"], "cac": c["cac"], "clv": clv, "data": d["data_new"],
                       "loyalty": n1 / (n1 + 20000.0)})
            d["m"]["crm"] = {**c, "n1": n1, "clv": clv, "clv_cac": clv / c["cac"] if c["cac"] else 0.0,
                             "req_priv": req_priv, "opt_out": d["opt_out"]}
        d["new_state"] = ns

    return _finish(P, group_vol, wp, n, round_no, seg_info, trust, mods)


def _finish(P, group_vol, wp, n, round_no, seg_info, trust, mods):
    """Reports and reports' costs are added by the caller through apply_report_costs()."""
    results = {}
    for pid, d in P.items():
        results[pid] = {
            "round": round_no, "segments": d["res_segs"], "modules": d["m"],
            "costs": d["costs_pre_reports"], "profit_before_reports": d["profit_pre_reports"],
            "revenue_core": d["revenue"], "revenue_ancillary": d["anc_rev"], "var_cost": d["var_cost"] + d["anc_cost"],
            "lines": d["lines_out"], "cogs": {"production": d["cogs_prod"], "distribution": d["cogs_dist"], "ancillary": d["anc_cost"]},
            "vol_total": d["vol_total"], "new_state": d["new_state"], "trust": trust,
            "market": seg_info,
        }
    results["__group__"] = {"group_vol": group_vol, "wp": wp}
    return results


# fixed costs shown on the profit and loss account, grouped by what makes them grow
PL_FIXED = [
    ("Company overhead", ["Company overhead"], "company"),
    ("Product upkeep (per product launched)", ["Product upkeep"], "product"),
    ("Pack listing and artwork (per pack on sale)", ["Pack listing and artwork"], "product"),
    ("Localisation upkeep (per product)", ["Localisation upkeep"], "product"),
    ("Product reformulation", ["Product reformulation"], "product"),
    ("Market fixed costs (per segment served)", ["Segment fixed costs"], "market"),
    ("Marketing and promotion", ["Media and promotion", "Digital campaigns", "ML model and A/B tests", "Ad production",
                                 "Positioning communication", "Experiential marketing"], "programme"),
    ("Distribution and partner network", ["Channel development", "SHG training and incentives", "Franchise set-up", "FPO tie-up"], "programme"),
    ("Customer and data programmes", ["Customer acquisition", "Customer retention", "Customer data platform",
                                      "Privacy compliance", "Personalisation (AI)"], "programme"),
    ("Research: reports bought", ["Reports bought"], "research"),
    ("Fines", ["Privacy fine", "Regulator fine (manipulative ads)"], "fines"),
]


def build_financials(r, fin0, round_no):
    """P&L, balance sheet and cash flow for one round. Returns (statements, new fin state, net profit)."""
    costs = r["costs"]
    rev, anc = r["revenue_core"], r["revenue_ancillary"]
    cg = r["cogs"]
    var_total = cg["production"] + cg["distribution"] + cg["ancillary"]
    contribution = rev + anc - var_total
    fixed_rows = [(label, sum(costs.get(k, 0.0) for k in keys)) for label, keys, _grp in PL_FIXED]
    listed = {k for _l, keys, _g in PL_FIXED for k in keys}
    other = sum(v for k, v in costs.items() if k not in listed)
    if other:
        fixed_rows.append(("Other fixed costs", other))
    opex = sum(v for _, v in fixed_rows)
    ebit = contribution - opex
    interest = OVERDRAFT_RATE * fin0["debt"]
    net = ebit - interest
    ar1, ap1 = AR_SHARE * rev, AP_SHARE * cg["production"]
    d_ar, d_ap = ar1 - fin0["ar"], ap1 - fin0["ap"]
    cfo = net - d_ar + d_ap
    pre = fin0["cash"] + cfo
    if pre < 0:
        borrow, repay, cash1 = -pre, 0.0, 0.0
    else:
        borrow, repay = 0.0, min(fin0["debt"], pre)
        cash1 = pre - repay
    debt1 = fin0["debt"] + borrow - repay
    retained1 = fin0["retained"] + net
    cap_in = fin0["capital"] if round_no == 1 else 0.0
    open_cash = 0.0 if round_no == 1 else fin0["cash"]
    pl = [("Sales revenue", rev, "n"), ("Add-on offer revenue", anc, "n"), ("Total revenue", rev + anc, "t"),
          ("VARIABLE COSTS (grow with sales)", None, "h"),
          ("Production cost (net of clearance recovery)", -cg["production"], "n"),
          ("Delivery and commissions", -cg["distribution"], "n"),
          ("Cost of add-on offers", -cg["ancillary"], "n"), ("Total variable costs", -var_total, "t"),
          ("Contribution (revenue less variable costs)", contribution, "t"),
          ("FIXED COSTS (grow with products, packs and markets)", None, "h")]
    pl += [(label, -v, "n") for label, v in fixed_rows]
    pl += [("Total fixed costs", -opex, "t"), ("Operating profit", ebit, "t"),
           ("Interest on overdraft", -interest, "n"), ("Net profit", net, "t")]
    bs = [("Cash", cash1, "n"), ("Trade receivables (retailers pay next quarter)", ar1, "n"), ("Total assets", cash1 + ar1, "t"),
          ("Trade payables (suppliers paid next quarter)", ap1, "n"), ("Bank overdraft", debt1, "n"),
          ("Total liabilities", ap1 + debt1, "t"), ("Share capital", fin0["capital"], "n"),
          ("Retained earnings", retained1, "n"), ("Total equity", fin0["capital"] + retained1, "t"),
          ("Total liabilities and equity", ap1 + debt1 + fin0["capital"] + retained1, "t")]
    cf = [("Net profit", net, "n"), ("Increase in receivables", -d_ar, "n"), ("Increase in payables", d_ap, "n"),
          ("Cash from operations", cfo, "t"), ("Cash from investing (no fixed assets in this game)", 0.0, "n"),
          ("Share capital introduced", cap_in, "n"), ("Overdraft drawn", borrow, "n"), ("Overdraft repaid", -repay, "n"),
          ("Cash from financing", cap_in + borrow - repay, "t"), ("Opening cash", open_cash, "n"),
          ("Closing cash", cash1, "t")]
    cum = dict(fin0.get("cum_pl") or {})
    for label, v, _k in pl:
        if v is not None:
            cum[label] = cum.get(label, 0.0) + v
    fin1 = {"cash": cash1, "ar": ar1, "ap": ap1, "debt": debt1, "capital": fin0["capital"], "retained": retained1, "cum_pl": cum}
    stm = {"pl": [{"label": l, "v": v, "kind": k, "cum": cum.get(l)} for l, v, k in pl],
           "bs": [{"label": l, "v": v, "kind": k} for l, v, k in bs],
           "cf": [{"label": l, "v": v, "kind": k} for l, v, k in cf],
           "balanced": abs((cash1 + ar1) - (ap1 + debt1 + fin0["capital"] + retained1)) < 1.0}
    return stm, fin1, net


def zero_financials(start_cash):
    """The opening position shown before any round has been processed: no trading, only the starting cash."""
    r = {"costs": {}, "revenue_core": 0.0, "revenue_ancillary": 0.0,
         "cogs": {"production": 0.0, "distribution": 0.0, "ancillary": 0.0}}
    fin0 = {"cash": float(start_cash), "ar": 0.0, "ap": 0.0, "debt": 0.0, "capital": float(start_cash), "retained": 0.0}
    stm, _fin1, _net = build_financials(r, fin0, 1)
    return stm


def finalize(results, extra_costs, wp):
    """Add report costs, build the financial statements, then compute totals, market share and the composite rank."""
    ids = [k for k in results if k != "__group__"]
    gv = sum(results[i]["vol_total"] for i in ids)
    for pid in ids:
        r = results[pid]
        extra = float(extra_costs.get(pid, 0.0))
        if extra:
            r["costs"]["Reports bought"] = extra
        fin0 = {**new_state()["fin"], **(r["new_state"].get("fin") or {})}
        stm, fin1, net = build_financials(r, fin0, r["round"])
        r["financials"] = stm
        r["new_state"]["fin"] = fin1
        profit = net
        revenue = r["revenue_core"] + r["revenue_ancillary"]
        r["totals"] = {"revenue": revenue, "profit": profit, "volume_share": (r["vol_total"] / gv) if gv else 0.0,
                       "cost_total": revenue - profit, "cash_end": fin1["cash"]}
    def pr(key):
        order = sorted(ids, key=lambda i: -results[i]["totals"][key])
        return {pid: (1 - k / max(1, len(order) - 1)) if len(order) > 1 else 1.0 for k, pid in enumerate(order)}
    prof, shr = pr("profit"), pr("volume_share")
    scored = {pid: wp * prof[pid] + (1 - wp) * shr[pid] for pid in ids}
    order = sorted(ids, key=lambda i: -scored[i])
    prank = {pid: k + 1 for k, pid in enumerate(sorted(ids, key=lambda i: -results[i]["totals"]["profit"]))}
    srank = {pid: k + 1 for k, pid in enumerate(sorted(ids, key=lambda i: -results[i]["totals"]["volume_share"]))}
    for k, pid in enumerate(order, 1):
        t = results[pid]["totals"]
        t.update({"group_rank": k, "group_size": len(ids), "rank_score": scored[pid],
                  "profit_rank": prank[pid], "share_rank": srank[pid]})
        results[pid]["new_state"]["last_profit"] = t["profit"]
    return results


DIGITAL_LABEL_ = {"video": "Vernacular video", "whatsapp": "WhatsApp campaigns", "social": "Social media", "search": "Search"}
RFM_LABEL_ = {"champions": "Champions", "loyal": "Loyal regulars", "at_risk": "At risk", "new": "New customers"}


# ---------- events the teacher can trigger ----------
EVENTS = {
    "monsoon": {"label": "Monsoon failure", "desc": "Rural demand down 20%, delivery cost up 15%.", "suits": "1-4",
                "demand_mult": {"large_village": 0.8, "remote_village": 0.8}, "dist_mult": 1.15},
    "competitor": {"label": "New low-price competitor", "desc": "Customers become more price sensitive (x1.3).",
                   "suits": "1-3, 7", "beta_mult": 1.3},
    "festival": {"label": "Festival season", "desc": "Demand up 25% in all segments.", "suits": "2-6",
                 "demand_mult": {s: 1.25 for s in SEGMENTS}},
    "fuel": {"label": "Fuel price spike", "desc": "Delivery and van costs up 20%.", "suits": "3-4", "dist_mult": 1.2},
    "privacy_law": {"label": "Data-privacy law", "desc": "Required privacy compliance level rises by 2.",
                    "suits": "5-6", "privacy_req_bump": 2.0},
    "platform_outage": {"label": "Platform outage", "desc": "Digital campaigns deliver 50% fewer clicks.",
                        "suits": "8", "digital_mult": 0.5},
    "ad_backlash": {"label": "Backlash against manipulative ads", "desc": "Market trust drops by 0.08 (more if ads were manipulative).",
                    "suits": "9", "trust_hit": 0.08},
}


def combine_events(keys):
    mods = {"demand_mult": {s: 1.0 for s in SEGMENTS}, "dist_mult": 1.0, "beta_mult": 1.0,
            "digital_mult": 1.0, "privacy_req_bump": 0.0, "trust_hit": 0.0}
    for key in keys:
        ev = EVENTS.get(key)
        if not ev:
            continue
        for seg, m in ev.get("demand_mult", {}).items():
            mods["demand_mult"][seg] *= m
        mods["dist_mult"] *= ev.get("dist_mult", 1.0)
        mods["beta_mult"] *= ev.get("beta_mult", 1.0)
        mods["digital_mult"] *= ev.get("digital_mult", 1.0)
        mods["privacy_req_bump"] += ev.get("privacy_req_bump", 0.0)
        mods["trust_hit"] += ev.get("trust_hit", 0.0)
    return mods
