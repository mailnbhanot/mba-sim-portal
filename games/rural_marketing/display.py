"""Turns an engine result into tables and plain-language notes for the results page."""
from . import params as P

T = lambda title, cols, rows, note="": {"title": title, "cols": cols, "rows": rows, "note": note}

ROUND_INFO = {
    1: {"unit": "Unit I", "co": "CO1", "title": "Choose categories, design products, set packs and prices",
        "intro": "Pick three of the seven categories to launch. Design each product (quality, localisation), then for every market choose "
                 "up to two pack sizes in grams and their prices. Each segment has a hidden ideal and only buys a pack that passes the "
                 "acceptance threshold. You start with Rs 50 lakh cash and your statements are blank until Round 1 is processed. "
                 "Free public data and paid reports are in the left menu.",
        "reflect": "Which reports did you buy and which one changed your design most? If a segment rejected your product, what would you change and what would it cost?"},
    2: {"unit": "Unit I", "co": "CO1", "title": "Production planning and fixing your range",
        "intro": "Stage 1 has no marketing. Use this round to decide how many of each pack to produce, and to fix what Round 1 got wrong: packs that were rejected, prices that did not cover cost, "
                 "and awkward prices. Unsold packs are cleared at half cost and you cannot sell what you did not make.",
        "reflect": "Which media gave you the best return and why? How did rivals' spending change what your money bought?"},
    3: {"unit": "Unit I", "co": "CO1", "title": "Technology-enabled distribution",
        "intro": "Build your channel mix per segment. Better coverage sells more but costs more to serve. Retailers pay late, so cash lags profit. Last-mile capacity is shared.",
        "reflect": "How did your stock decision compare with real demand? What did you learn about cost to serve against availability?"},
    4: {"unit": "Unit II", "co": "CO2", "title": "Rural business models",
        "intro": "Recruit SHG entrepreneurs and franchise outlets, tie up with farmer groups and decide on aggregator platforms. The SHG pool is shared, and partners take time to pay back.",
        "reflect": "Which partner model paid back fastest for each segment? Would you stay capital-light or control more yourself next time?"},
    5: {"unit": "Unit III", "co": "CO3", "title": "AI-enabled CRM: acquire or retain",
        "intro": "Balance acquisition and retention, invest in a customer data platform and choose your privacy compliance. New customers come from a shared pool; weak privacy is fined.",
        "reflect": "What were your CAC, churn and lifetime value? Was your acquisition to retention balance right for your numbers?"},
    6: {"unit": "Unit III", "co": "CO3", "title": "Cross-sell, upsell and personalisation",
        "intro": "Design your own add-on offer, choose which customer groups to target, and decide how much AI personalisation and how many messages to use. Over-contacting hurts trust for everyone.",
        "reflect": "Which customer groups responded to your offer and why? Where did you cross the line between personalisation and intrusion?"},
    7: {"unit": "Unit IV", "co": "CO4", "title": "Segmentation, targeting and positioning with data",
        "intro": "Choose where your brand sits on price and benefit. Segments differ; crowding near rivals splits customers, while an empty space is an opportunity.",
        "reflect": "What did the data tell you about each segment? How did you decide to differ from your rivals?"},
    8: {"unit": "Unit IV", "co": "CO4", "title": "Digital metrics and machine learning",
        "intro": "Split your digital budget, invest in an ML model sized to your data and decide how tightly to target. Digital costs rise when many students use the same channel.",
        "reflect": "Which metrics (CTR, CPA, ROAS, AUC) drove your decisions? When was the ML model worth its cost?"},
    9: {"unit": "Unit V", "co": "CO5", "title": "Neuromarketing and ethical persuasion",
        "intro": "Create your advertisement. Each segment responds to a different mix of emotion, reason and local story. Pre-test it with a survey, eye tracking or EEG, and decide how far to push persuasion.",
        "reflect": "How did your pre-test results compare with the real response? Where is the ethical line, and who pays when the market crosses it?"},
    10: {"unit": "Unit VI", "co": "CO6", "title": "Experiential and immersive marketing",
         "intro": "Design experiences by blending physical and digital touchpoints. Digital touchpoints fail where smartphones are scarce, novelty fades when rivals copy you, and this is the last round.",
         "reflect": "Which touchpoints worked in which segment? Looking back over 10 rounds, which three decisions mattered most and which course outcome does each show?"},
}


def _line_label(l):
    return f"{l['pack'].upper()}: {l['grams']:g} g{' LUP' if l.get('type') == 'lup' else ''}"


def build(res, round_no):
    segs, mods, lines = res["segments"], res["modules"], res.get("lines", [])
    tables = []
    rows = [[l["label"], P.SEG_SHORT[l["segment"]], _line_label(l), l["price"], l["fair_price"], l["unit_cost"],
             l["unit_contrib"], l["fit"], l["accept"], l["packs_sold"], l["revenue"], l["contribution"]] for l in lines]
    tables.append(T("Your packs", [("Product", "text"), ("Segment", "text"), ("Pack", "text"), ("Price (Rs)", "d1"),
                                   ("Fair price (Rs)", "d1"), ("Cost per pack incl. delivery (Rs)", "d2"),
                                   ("Contribution per pack (Rs)", "d2"), ("Fit (0-100)", "d1"), ("Consumers accept", "pct"),
                                   ("Packs sold", "num"), ("Revenue", "inr"), ("Pack contribution", "inr")], rows,
                    "Consumers accept a pack only above a fit score of about 45. Below it most shoppers walk past, whatever your price. "
                    "Contribution is after production and delivery but before shared fixed costs."))
    bycat = {}
    for l in lines:
        c = bycat.setdefault(l["label"], {"rev": 0.0, "con": 0.0, "packs": 0.0})
        c["rev"] += l["revenue"]
        c["con"] += l["contribution"]
        c["packs"] += l["packs_sold"]
    tables.append(T("Your products", [("Category", "text"), ("Packs sold", "num"), ("Revenue", "inr"), ("Contribution", "inr")],
                    [[k, v["packs"], v["rev"], v["con"]] for k, v in bycat.items()],
                    "Each product also carries Rs 40,000 upkeep, localisation upkeep and Rs 6,000 for every pack on sale, every quarter."))
    rows = []
    for s in P.SEGMENTS:
        r = segs[s]
        if r["serve"]:
            rows.append([P.SEG_SHORT[s], r["packs_sold"], r["revenue"], r["contribution"], r["share"]])
    tables.append(T("Your markets", [("Segment", "text"), ("Packs sold", "num"), ("Revenue", "inr"), ("Contribution", "inr"),
                                     ("Your share of segment volume", "pct")], rows))
    rows = []
    for s in P.SEGMENTS:
        r = segs[s]
        if r["serve"]:
            rows.append([P.SEG_SHORT[s], r["avail"], r["adeff"], r["uplift"]])
    tables.append(T("What lifted your sales", [("Segment", "text"), ("Shops reached", "pct"), ("Advertising effect", "pct"),
                                               ("Marketing uplift on volume", "d2")], rows))
    if any(l["stock"] is not None for l in lines):
        rows = [[l["label"], P.SEG_SHORT[l["segment"]], _line_label(l), l["demand_packs"], l["stock"], l["packs_sold"],
                 l["unsold"], l["unmet"]] for l in lines if l["stock"] is not None]
        cong = ", ".join(f"{P.SEG_SHORT[s]} x{res['market'].get(s, {}).get('congestion', 1.0):.2f}" for s in P.SEGMENTS)
        tables.append(T("Stock against demand", [("Product", "text"), ("Segment", "text"), ("Pack", "text"), ("Demand (packs)", "num"),
                                                  ("Produced", "num"), ("Sold", "num"), ("Unsold (cleared at half cost)", "num"),
                                                  ("Lost sales", "num")], rows, f"Last-mile congestion: {cong}."))
    if "digital" in mods:
        m = mods["digital"]
        tables.append(T("Digital campaign results", [("Channel", "text"), ("Spend", "inr"), ("Impressions", "num"), ("Clicks", "num"),
                                                      ("CTR (%)", "d2"), ("Conversions", "d1"), ("Cost per conversion", "inr"), ("Cost per click", "d1")],
                        [[r[0], r[1], r[2], r[3], r[4] * 100, r[5], r[6] or 0, r[7] or 0] for r in m["rows"]],
                        f"Model accuracy (AUC) was {m['auc']:.2f}. Targeting effect on conversions: x{m['tf']:.2f}."))
    if "crm" in mods:
        m = mods["crm"]
        tables.append(T("Customers and CRM", [("Measure", "text"), ("Value", "d2")], [
            ["Customers at start", m["n0"]], ["New customers acquired", m["newc"]], ["Churn this quarter", m["churn"]],
            ["Opt-outs from messages", m["opt_out"]], ["Customers at end", m["n1"]], ["Cost to acquire one (Rs)", m["cac"]],
            ["Customer lifetime value (Rs)", m["clv"]], ["Lifetime value / acquisition cost", m["clv_cac"]],
            ["Your privacy level / required", f"{m['priv']:.0f} / {m['req_priv']:.0f}"]]))
    if "offer" in mods:
        m = mods["offer"]
        tables.append(T("Offer results by customer group", [("Group", "text"), ("Customers", "num"), ("Targeted", "text"), ("Fit (0-100)", "d1"),
                                                              ("Acceptance", "pct"), ("Take-up", "pct"), ("Buyers", "num"), ("Profit from offer", "inr")],
                        [[r[0], r[1], "Yes" if r[2] else "No", r[3], r[4], r[5], r[6], r[7]] for r in m["rows"]],
                        f"Add-on price Rs {m['padd']:.0f}, cost Rs {m['cadd']:.0f}."))
    if "position" in mods:
        m = mods["position"]
        tables.append(T("Positioning", [("Segment", "text"), ("Match with segment ideal", "pct"), ("Effect on sales (index)", "d2")],
                        m["rows"], f"Crowding by rivals near your position: {m['crowd']:.2f}."))
    if "creative" in mods:
        m = mods["creative"]
        tables.append(T("Advertisement response", [("Segment", "text"), ("Engagement (0-100)", "d1"), ("Consumers like it", "pct"),
                                                    ("Memory encoding", "pct"), ("Ad score", "d2"), ("Ad power multiplier", "d2")], m["rows"]))
    if "experience" in mods:
        m = mods["experience"]
        tables.append(T("Experience results", [("Segment", "text"), ("Experience score", "pct"), ("Effect after flop test", "pct")], m["rows"],
                        f"Physical and digital synergy x{m['synergy']:.2f}. Below about 20% a touchpoint flops."))
    return tables


def notes(res, round_no, submitted):
    lines = res.get("lines", [])
    out = []
    if not submitted:
        out.append("You did not submit a decision, so no product was designed and nothing was sold. You still paid your company overhead. "
                   "Not deciding is never safe.")
    rej, border, below, waste, lost, offround = [], [], [], [], [], []
    for l in lines:
        tag = f"{l['label']} {_line_label(l)} in {P.SEG_SHORT[l['segment']]}"
        if l["accept"] < 0.35:
            rej.append(f"{tag} (fit {l['fit']:.0f})")
        elif l["accept"] < 0.7:
            border.append(f"{tag} ({l['accept'] * 100:.0f}%)")
        if l.get("roundness", 0) < 0:
            offround.append(f"{tag} at Rs {l['price']:g}")
        if l["unit_contrib"] <= 0:
            below.append(f"{tag} (cost Rs {l['unit_cost']:.1f} against price Rs {l['price']:.1f})")
        if l["stock"] is not None:
            if l["unsold"] > 0.15 * max(1.0, l["stock"]):
                waste.append(f"{tag}: {l['unsold']:,.0f} packs")
            if l["unmet"] > 0.1 * max(1.0, l["demand_packs"]):
                lost.append(f"{tag}: about {l['unmet']:,.0f} packs")
    if rej:
        out.append("Consumers rejected these packs (fit below the threshold of about 45), but you still paid their costs. "
                   "A concept test would have shown this: " + "; ".join(rej[:6]) + ("; and more." if len(rej) > 6 else "."))
    if border:
        out.append("Borderline acceptance: " + "; ".join(border[:5]) + ". A closer match to what the segment wants would lift sales a lot.")
    if below:
        out.append("Sold below unit cost including delivery, so more volume only means more loss: " + "; ".join(below[:5]) + ".")
    if offround:
        out.append("Awkward prices that need change from traders sold less (round prices such as 5, 10, 20, 25 sell better): " + "; ".join(offround[:5]) + ".")
    if waste:
        out.append("Produced more than you sold (cleared at half cost): " + "; ".join(waste[:5]) + ".")
    if lost:
        out.append("Lost sales because you did not produce enough: " + "; ".join(lost[:5]) + ".")
    fin = res.get("financials")
    if fin:
        cfo = next(x["v"] for x in fin["cf"] if x["label"] == "Cash from operations")
        net = res["totals"]["profit"]
        if net > 0 and cfo < 0.5 * net:
            out.append("Your cash from operations was much lower than your profit because retailers pay late and you pay suppliers later. Watch the cash flow statement.")
        debt = next(x["v"] for x in fin["bs"] if x["label"] == "Bank overdraft")
        if debt > 0:
            out.append(f"You ran out of cash and the bank overdraft is now Rs {debt:,.0f}. It costs 3% interest every quarter.")
    mods = res["modules"]
    if "crm" in mods and mods["crm"]["clv_cac"] < 3:
        out.append(f"Lifetime value was only {mods['crm']['clv_cac']:.1f} times acquisition cost. A rule of thumb is at least 3.")
    if "crm" in mods and mods["crm"]["priv"] < mods["crm"]["req_priv"]:
        out.append("Your privacy compliance was below the required level. You were fined and market trust fell.")
    if "offer" in mods and mods["offer"]["opt_out"] > 0:
        out.append(f"Too many messages: about {mods['offer']['opt_out']:,.0f} customers opted out, and trust for the whole market fell.")
    if "creative" in mods and mods["creative"]["avg_like"] < 0.35:
        out.append("Consumers did not like your advertisement, so it had little power and hurt your brand.")
    if "creative" in mods and mods["creative"]["manip"] > 7:
        out.append("Your advertisement used heavy manipulation. You were fined and your brand was damaged.")
    if "experience" in mods and max((r[2] for r in mods["experience"]["rows"]), default=0) < 0.05:
        out.append("Your experiences flopped: the touchpoints did not suit the segments you aimed at (for example digital touchpoints in remote villages).")
    t = res["totals"]
    out.append(f"Ranking this round combines profit (rank {t['profit_rank']}) and market share (rank {t['share_rank']}). "
               "Chasing profit alone or share alone does not win.")
    return out
