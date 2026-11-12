"""The report library. Students buy the reports they think are worth the money and design
their own decisions from them. Every report has 2 or 3 accuracy levels (cheap and noisy, or
expensive and precise). Noise is seeded per student, report and round, so re-buying does not help.

A report generator receives ctx and an accuracy sd and returns
    {"note": str, "tables": [{"title", "cols": [(label, fmt)], "rows": [[...]]}]}
fmt is one of: text, inr, num, pct, d1, d2.
"""
import math
import random

from . import params as P
from .engine import (acceptance, fit_score, pack_fit, ref_price, roundness, unit_cost)

BASIC, DETAILED = 0, 1


def lv(*pairs):
    return [{"name": n, "cost": c, "sd": sd} for n, c, sd in pairs]


def T(title, cols, rows):
    return {"title": title, "cols": cols, "rows": rows}


class Ctx:
    """What a generator may use."""
    def __init__(self, rng, sd, tp, state, dec, prev_own, prev_group, rivals_now, n, round_no, seed):
        self.rng, self.sd, self.tp, self.state, self.dec = rng, sd, tp, state, dec
        self.prev_own, self.prev_group, self.rivals_now = prev_own, prev_group, rivals_now
        self.n, self.round_no, self.seed = n, round_no, seed
        self.cats, self.segs = list(P.CAT_KEYS), list(P.SEGMENTS)

    def nz(self, v):
        """Multiplicative noise."""
        return v * (1 + max(-0.6, min(0.6, self.rng.gauss(0, self.sd))))

    def nzp(self, v, scale=1.0):
        """Additive noise on a score measured in points."""
        return v + self.rng.gauss(0, self.sd * scale)


# ================= UNIT I: consumers, price, market (category aware) =================

def _my_cats(c):
    from .engine import cats_of
    return cats_of(c.dec or {}, c.state or {})


def r_industry(c):
    return {"note": "Free public overview. It tells you what to look for, not the answers.",
            "tables": [T("What the trade press says", [("Topic", "text"), ("Observation", "text")], [
                ["Categories", "Seven categories are open. Each differs in size by segment, price level, margin and what shoppers want."],
                ["Packs", "Shoppers compare pack sizes and prices. Small packs cost more per gram to make but suit low incomes."],
                ["Pricing", "Customers compare prices across brands. Very low prices can still lose money."],
                ["Acceptance", "A pack that misses what a segment wants is not bought at any price."],
                ["Cash", "Retailers pay late and suppliers are paid late. Profit is not the same as cash."]])]}


def r_pref(c):
    rows = []
    for cat in c.cats:
        for s in c.segs:
            i = c.tp[s]["cats"][cat]["ideal"]
            rows.append([P.CAT_LABEL[cat], P.SEG_SHORT[s], c.nzp(i[0], 1.0), c.nz(i[1]), c.nzp(i[2], 1.5)])
    return {"note": "Average ideal product reported by shoppers. Real ideals can differ by the error shown.",
            "tables": [T("Preferred product by category and segment",
                         [("Category", "text"), ("Segment", "text"), ("Quality (1-10)", "d1"),
                          ("Pack size (g)", "num"), ("Localisation (0-10)", "d1")], rows)]}


def r_price(c):
    rows = []
    for cat in c.cats:
        for s in c.segs:
            cm = P.CATEGORIES[cat]
            per100 = 100 * 0.075 * P.SEG[s]["pm"] * cm["pm"]
            perq = 100 * 0.019 * P.SEG[s]["pm"] * cm["pm"]
            rows.append([P.CAT_LABEL[cat], P.SEG_SHORT[s], c.nz(c.tp[s]["cats"][cat]["beta"]),
                         c.nz(per100 + 5 * perq), c.nz(perq), c.nz(P.PACK_FIXED_PRICE)])
    return {"note": "Fair price = grams/100 x (price per 100 g at quality 5 + extra per quality point x (quality - 5)) + packaging. "
                    "Price sensitivity: a price 10% below the average wins roughly sensitivity x 10 percent more share. "
                    "Prices are accepted between 40% and 200% of fair.",
            "tables": [T("Price perception", [("Category", "text"), ("Segment", "text"), ("Price sensitivity", "d2"),
                                              ("Fair price per 100 g at quality 5 (Rs)", "d2"),
                                              ("Extra per quality point per 100 g (Rs)", "d2"),
                                              ("Packaging element per pack (Rs)", "d2")], rows)]}


def _rivals_in(c, cat):
    n = 0
    for a in c.prev_group:
        if cat in ((a.get("state") or {}).get("cats") or []):
            n += 1
    return n


def r_size(c):
    g = P.GROWTH
    rows = []
    for cat in c.cats:
        for s in c.segs:
            rows.append([P.CAT_LABEL[cat], P.SEG_SHORT[s], c.nz(c.tp[s]["base"] * c.tp[s]["cats"][cat]["w"] * c.n),
                         (g - 1) * 100, c.n, _rivals_in(c, cat) if c.prev_group else None])
    return {"note": "Category volume per quarter in the segment, in typical packs, summed over all firms in your market. "
                    "'Firms in category last round' counts rivals that sold the category (blank in Round 1).",
            "tables": [T("Market size and growth", [("Category", "text"), ("Segment", "text"), ("Category volume (typical packs)", "num"),
                                                    ("Growth per quarter (%)", "d1"), ("Firms in your market", "num"),
                                                    ("Firms in category last round", "num")], rows)]}


def r_costs(c):
    rows = []
    for cat in c.cats:
        for q in (1, 3, 5, 7, 9):
            u = unit_cost(cat, q, 100.0, 0.0) - P.PACK_FIXED_COST
            rows.append([P.CAT_LABEL[cat], q, c.nz(u), c.nz(u * 1.2), c.nz(P.PACK_FIXED_COST)])
    return {"note": "Making cost for 100 g, excluding packaging. Localisation 10 adds 20%. Packaging costs the same Rs per pack whatever the size, "
                    "so small packs cost more per gram. Delivery costs are in the channel cost report.",
            "tables": [T("Supplier cost sheet", [("Category", "text"), ("Quality", "num"), ("Cost per 100 g, localisation 0 (Rs)", "d2"),
                                                 ("Cost per 100 g, localisation 10 (Rs)", "d2"),
                                                 ("Packaging per pack (Rs)", "d2")], rows)]}


def r_catmargin(c):
    rows = []
    for cat in c.cats:
        for s in c.segs:
            g = P.CATEGORIES[cat]["g"]
            fair = ref_price(cat, 5.0, g, s)
            cost = unit_cost(cat, 5.0, g, 0.0) + (P.SEG[s]["dist"] * 1.2 * (g / 100.0) ** 0.7)
            rows.append([P.CAT_LABEL[cat], P.SEG_SHORT[s], c.nz(fair), c.nz(cost), (fair - c.nz(cost)) / fair if fair else 0.0])
    return {"note": "Typical pack at quality 5 with no localisation, sold at the fair price, with basic delivery. Margin is before fixed costs.",
            "tables": [T("Category margin potential", [("Category", "text"), ("Segment", "text"), ("Fair price, typical pack (Rs)", "d1"),
                                                      ("Cost incl. delivery (Rs)", "d1"), ("Margin at fair price", "pct")], rows)]}


def _saved_lines(c):
    """Yield the student's saved packs: (label, cat, seg, pack text, grams, price, quality, loc, type)."""
    cats = _my_cats(c)
    labels = P.slot_labels(cats)
    prod = c.dec.get("product") or {}
    lines = c.dec.get("lines") or {}
    for sl in P.SLOTS:
        cat = cats[sl]
        if cat not in c.cats:
            continue
        q = float((prod.get(sl) or {}).get("quality", 5.0))
        loc = float((prod.get(sl) or {}).get("loc", 0.0))
        for s in c.segs:
            ln = lines.get(f"{sl}|{s}") or {}
            for k in P.PACKS:
                g, pr = float(ln.get(k + "_g") or 0.0), float(ln.get(k + "_price") or 0.0)
                if ln.get("serve", True) and g > 0 and pr > 0:
                    yield labels[sl], cat, s, k.upper(), g, pr, q, loc, ln.get(k + "_type", "gram")


def r_concept(c):
    rows = []
    for lab, cat, s, k, g, pr, q, loc, ptype in _saved_lines(c):
        fit = pack_fit(q, g, loc, c.tp[s]["cats"][cat]["ideal"], ptype, pr, c.tp[s]["pp"])
        f2 = max(0.0, min(100.0, c.nzp(fit, 20)))
        rows.append([lab, P.SEG_SHORT[s], f"{k}: {g:g} g{' LUP' if ptype == 'lup' else ''} at Rs {pr:g}", f2, acceptance(f2),
                     "Likely accepted" if f2 >= 60 else "Borderline" if f2 >= 42 else "Likely rejected"])
    return {"note": "Tested on your SAVED draft (quality, localisation and each pack's grams). Press Save draft first if you changed anything. "
                    "Acceptance below about 45 means most shoppers will not buy.",
            "tables": [T("Concept test of your packs", [("Category", "text"), ("Segment", "text"), ("Pack", "text"),
                                                        ("Fit score (0-100)", "d1"), ("Acceptance", "pct"),
                                                        ("Verdict", "text")], rows)]}


def r_pricetest(c):
    rows = []
    for lab, cat, s, k, g, pr, q, loc, ptype in _saved_lines(c):
        beta = c.nz(c.tp[s]["cats"][cat]["beta"])
        rp = ref_price(cat, q, g, s)
        price = pr or rp
        for mult in (0.8, 0.9, 1.0, 1.1, 1.25):
            pi = mult * price / rp
            rows.append([lab, P.SEG_SHORT[s], f"{k}: {g:g} g", mult * price, pi,
                         math.exp(-beta * math.log(max(pi, 0.05)))])
    return {"note": "Relative demand against the fair price for each saved pack, at your saved price and nearby prices. "
                    "1.00 means demand at the fair price. It does not include what rivals charge.",
            "tables": [T("Price response", [("Category", "text"), ("Segment", "text"), ("Pack", "text"), ("Price (Rs)", "d1"),
                                            ("Price vs fair price", "d2"), ("Relative demand", "d2")], rows)]}


def r_audit(c):
    rows = []
    for a in c.prev_group:
        res = a["result"]
        sh = res["totals"]["volume_share"]
        lines = res.get("lines") or []
        pis = [l["price_index"] for l in lines]
        pi = sum(pis) / len(pis) if pis else 0
        gs = [l["grams"] for l in lines]
        avg_g = sum(gs) / len(gs) if gs else 0
        cats = ", ".join(P.CAT_LABEL[x] for x in ((a.get("state") or {}).get("cats") or []))
        npk = len(lines)
        if c.sd > 0.15:     # basic: rounded figures
            sh, pi = round(sh * 20) / 20, round(pi * 10) / 10
        rows.append([a["alias"], cats, npk, avg_g, pi, sh])
    rows.sort(key=lambda r: -r[5])
    return {"note": "Last round's categories, packs and prices in your market (names hidden). Basic rounds the figures.",
            "tables": [T("Competitor audit", [("Company", "text"), ("Categories", "text"), ("Packs on sale", "num"),
                                              ("Average pack grams", "num"), ("Avg price vs fair", "d2"),
                                              ("Market share", "pct")], rows)]}


def r_brand(c):
    mine = c.state.get("brand", 20.0)
    others = [a["state"].get("brand", 20.0) for a in c.prev_group if a.get("state")]
    avg = sum(others) / len(others) if others else 20.0
    return {"note": "Brand strength index (0-100) from awareness and recall surveys. Brand builds through advertising and lasting experiences.",
            "tables": [T("Brand tracker", [("Measure", "text"), ("Index", "d1")],
                         [["Your brand", c.nzp(mine, 30)], ["Market average", c.nzp(avg, 30)]])]}


# ================= UNIT I: promotion =================

def r_media_habit(c):
    rows = []
    for m in P.MEDIA:
        rows.append([P.MEDIA_LABEL[m]] + [c.nz(P.MEDIA_R[m][i]) for i in range(3)])
    return {"note": "Share of each segment that can be reached by the medium with enough spend.",
            "tables": [T("Media reach potential", [("Medium", "text")] + [(P.SEG_SHORT[s], "pct") for s in P.SEGMENTS], rows)]}


def r_media_curve(c):
    rows = []
    for m in P.MEDIA:
        k = c.nz(P.MEDIA_K[m])
        row = [P.MEDIA_LABEL[m]]
        for lakhs in (1, 3):
            row.append(sum(P.MEDIA_R[m]) / 3 * (1 - math.exp(-k * lakhs)))
        rows.append(row)
    return {"note": "Average reach across segments for Rs 1 lakh and Rs 3 lakh of spend, before any rival crowding. Returns flatten quickly.",
            "tables": [T("Media response", [("Medium", "text"), ("Reach at Rs 1 lakh", "pct"), ("Reach at Rs 3 lakh", "pct")], rows)]}


def r_sov(c):
    rows = []
    for m in P.MEDIA:
        vals = [float((a["decision"].get("media") or {}).get(m, {}).get("spend", 0.0)) for a in c.prev_group]
        avg = sum(vals) / len(vals) if vals else 0.0
        rows.append([P.MEDIA_LABEL[m], c.nz(avg), c.nz(max(vals) if vals else 0.0)])
    return {"note": "What students in your market spent on each medium last round.",
            "tables": [T("Media spend tracker", [("Medium", "text"), ("Average spend (Rs)", "inr"), ("Highest spend (Rs)", "inr")], rows)]}


# ================= UNIT I: distribution =================

def r_outlets(c):
    rows = []
    for ch in P.CHANNELS:
        rows.append([P.CHANNEL_LABEL[ch]] + [c.nz(P.CH[ch]["cov"][i]) for i in range(3)])
    return {"note": "Share of outlets and households each channel can reach when used at full effort.",
            "tables": [T("Channel coverage", [("Channel", "text")] + [(P.SEG_SHORT[s], "pct") for s in P.SEGMENTS], rows)]}


def r_chcost(c):
    rows = []
    for ch in P.CHANNELS:
        rows.append([P.CHANNEL_LABEL[ch]] + [c.nz(P.CH[ch]["cost"][i]) * P.SEG[P.SEGMENTS[i]]["dist"] for i in range(3)])
    return {"note": "Delivery cost per 100 g by channel and segment, in rupees.",
            "tables": [T("Channel cost per 100 g", [("Channel", "text")] + [(P.SEG_SHORT[s], "d2") for s in P.SEGMENTS], rows)]}


def r_tpl(c):
    rows = []
    for s in P.SEGMENTS:
        m = (c.prev_own or {}).get("market", {}).get(s, {})
        grp = [a["result"]["market"].get(s, {}).get("congestion", 1.0) for a in c.prev_group[:1]]
        rows.append([P.SEG_SHORT[s], c.nz(grp[0] if grp else 1.0), c.nz(0.35 * c.tp[s]["base"] * c.n)])
    return {"note": "Last-mile partners have limited capacity. Above 1.00 means orders exceeded capacity: costs rose and service fell for everyone using them.",
            "tables": [T("Last-mile capacity", [("Segment", "text"), ("Congestion last round", "d2"), ("Capacity (100 g units)", "num")], rows)]}


def r_forecast(c):
    rows = []
    for l in (c.prev_own or {}).get("lines", []):
        rows.append([P.CAT_LABEL[l["cat"]], P.SEG_SHORT[l["segment"]], f"{l['pack'].upper()}: {l['grams']:g} g",
                     c.nz(l["demand_packs"] * P.GROWTH), l["unmet"] or 0.0, l["unsold"] or 0.0])
    return {"note": "Forecast of demand for each pack at LAST round's price and push, plus growth. It does not know about changes you make now. "
                    "Producing more than demand wastes money; less loses sales.",
            "tables": [T("Demand forecast (packs)", [("Category", "text"), ("Segment", "text"), ("Pack", "text"),
                                                     ("Forecast demand", "num"), ("Unmet demand last round", "num"),
                                                     ("Unsold last round", "num")], rows)]}


def r_inventory(c):
    rows = []
    for l in (c.prev_own or {}).get("lines", []):
        if l.get("stock") is not None:
            rows.append([P.CAT_LABEL[l["cat"]], P.SEG_SHORT[l["segment"]], l["pack"].upper(), l["stock"], l["packs_sold"],
                         l["unsold"], l["unmet"]])
    return {"note": "Your own production against sales last round, pack by pack.",
            "tables": [T("Inventory review", [("Category", "text"), ("Segment", "text"), ("Pack", "text"), ("Produced", "num"),
                                              ("Sold", "num"), ("Unsold", "num"), ("Lost sales", "num")], rows)]}


# ================= UNIT II: business models =================

def r_partners(c):
    rows = [[P.SEG_SHORT[s], c.nz(6.0 * c.n), c.nz(3000.0), 15.0] for s in P.SEGMENTS]
    return {"note": "SHG entrepreneurs available to be recruited each quarter across all students. If requests exceed the pool, "
                    "higher incentives win. About 15% leave each quarter.",
            "tables": [T("SHG partner pool", [("Segment", "text"), ("Pool per quarter", "num"),
                                              ("Training cost each (Rs)", "inr"), ("Quarterly attrition (%)", "d1")], rows)]}


def r_shg(c):
    rows = []
    for i, s in enumerate(P.SEGMENTS):
        w = [0.6, 1.0, 1.0][i]
        rows.append([P.SEG_SHORT[s]] + [c.nz(0.22 * w * (1 - math.exp(-n / 12.0))) for n in (5, 10, 20, 40)])
    return {"note": "Extra reach (share of households) added by an SHG network of the given size.",
            "tables": [T("SHG reach", [("Segment", "text"), ("5 members", "pct"), ("10", "pct"), ("20", "pct"), ("40", "pct")], rows)]}


def r_terms(c):
    return {"note": "Franchise outlets cost Rs 20,000 to set up and share about 5% of their sales. Aggregator platforms charge a "
                    "commission that rises when more students use them.",
            "tables": [T("Franchise and platform terms", [("Item", "text"), ("Term", "text")], [
                ["Franchise set-up per outlet", f"Rs {c.nz(20000):,.0f}"],
                ["Franchise revenue share", f"{c.nz(5.0):.1f}%"],
                ["Platform commission (low use)", f"{c.nz(8.0):.1f}%"],
                ["Platform commission (heavy use)", f"{c.nz(18.0):.1f}%"],
                ["Franchise reach (towns, large villages, remote)", "Strongest in towns, weakest in remote villages"]])]}


def r_fpo(c):
    rows = []
    for amt in (100000, 200000, 300000, 400000):
        e = 1 - math.exp(-amt / 200000.0)
        rows.append([amt, c.nz(5.0 * e), c.nz(0.15 * e * 100)])
    return {"note": "Cost saving on unit cost and extra demand goodwill in villages from tying up with farmer producer groups.",
            "tables": [T("FPO tie-up", [("Commitment per quarter (Rs)", "inr"), ("Unit cost saving (%)", "d1"),
                                        ("Village demand lift (%)", "d1")], rows)]}


# ================= UNIT III: CRM =================

def r_custbase(c):
    st = c.state
    mine = [["Your customers", st.get("customers") or sum(st.get("last_packs", {}).values()) / 3.0],
            ["Your churn per quarter", (st.get("churn") or 0.35)], ["Your cost to acquire (Rs)", st.get("cac") or 150.0],
            ["Your customer lifetime value (Rs)", st.get("clv") or 0.0]]
    rows = [[a, c.nz(b) if i != 1 else b] for i, (a, b) in enumerate(mine)]
    return {"note": "Your own customer base. Before Round 5 the figures are estimates from your sales.",
            "tables": [T("Customer base", [("Measure", "text"), ("Value", "d1")], rows)]}


def r_crmbench(c):
    ch = [a["state"].get("churn") for a in c.prev_group if a.get("state") and a["state"].get("churn")]
    cac = [a["state"].get("cac") for a in c.prev_group if a.get("state") and a["state"].get("cac")]
    clv = [a["state"].get("clv") for a in c.prev_group if a.get("state") and a["state"].get("clv")]
    avg = lambda v, d: sum(v) / len(v) if v else d
    return {"note": "Market averages from last round. A healthy business keeps lifetime value above about 3 times acquisition cost.",
            "tables": [T("CRM benchmarks", [("Measure", "text"), ("Market average", "d2")], [
                ["Churn per quarter", c.nz(avg(ch, 0.30))], ["Acquisition cost (Rs)", c.nz(avg(cac, 160.0))],
                ["Lifetime value (Rs)", c.nz(avg(clv, 400.0))]])]}


def r_privacy(c):
    trust = c.state.get("trust", 0.9)
    return {"note": "The regulator fines firms below the required privacy level. Over-contacting customers and manipulative ads reduce trust for the whole market.",
            "tables": [T("Privacy and trust", [("Item", "text"), ("Value", "d2")], [
                ["Required compliance level (0-10)", c.nz(5.0)],
                ["Fine per level of shortfall (Rs)", c.nz(30000.0)], ["Market trust index (0.5-1.0)", c.nzp(trust, 0.3)]])]}


def r_retention(c):
    rows = []
    for per_hh in (0, 20, 40, 80, 160):
        rows.append([per_hh, c.nz(0.35 * math.exp(-per_hh / 40.0)) * 100])
    return {"note": "Expected quarterly churn at different retention spend per household. Rival acquisition adds a little poaching on top.",
            "tables": [T("Retention response", [("Retention spend per household (Rs)", "inr"), ("Churn (%)", "d1")], rows)]}


# ================= UNIT III: offers =================

def r_rfm(c):
    n1 = c.state.get("customers") or sum(c.state.get("last_packs", {}).values()) / 3.0
    rows = [[P.RFM_LABEL[g], c.nz(n1 * c.tp["rfm"][g]["share"]), c.tp["rfm"][g]["share"]] for g in P.RFM]
    return {"note": "Your customers grouped by recency, frequency and spend.",
            "tables": [T("RFM groups", [("Group", "text"), ("Customers", "num"), ("Share", "pct")], rows)]}


def r_offerpilot(c):
    rows = []
    for g in P.RFM:
        i = c.tp["rfm"][g]["ideal"]
        rows.append([P.RFM_LABEL[g], c.nzp(i[0], 1.0), c.nzp(i[1], 8.0), c.tp["rfm"][g]["attach"] * c.rng.uniform(0.8, 1.2)])
    return {"note": "Pilot of many offers: the premium level and discount each group responded to best, and its best take-up.",
            "tables": [T("Offer pilot", [("Group", "text"), ("Best premium (0-10)", "d1"), ("Best discount (%)", "d1"),
                                         ("Best take-up", "pct")], rows)]}


def r_fatigue(c):
    rows = []
    for f_ in (1, 2, 4, 6, 8, 12):
        fat = 1 - math.exp(-0.10 * max(0.0, f_ - 2))
        rows.append([f_, c.nz(1 - fat) * 100, c.nz(100 * min(0.2, 0.012 * max(0, f_ - 4) ** 2))])
    return {"note": "More messages cut response and cause opt-outs above 4 a month. Opt-outs also lower market trust.",
            "tables": [T("Contact fatigue", [("Messages per month", "num"), ("Response kept (%)", "d1"), ("Customers lost (%)", "d1")], rows)]}


def r_ailift(c):
    rows = []
    data = c.state.get("data", 0.0)
    for b in (0, 50000, 100000, 200000, 400000):
        rows.append([b, c.nz((1 - math.exp(-b / 100000.0)) * (0.5 + 0.5 * data)) * 100])
    return {"note": "Lift in take-up from AI personalisation spend. It works better the stronger your customer data platform.",
            "tables": [T("Personalisation lift", [("Budget (Rs)", "inr"), ("Effect (index)", "d1")], rows)]}


def r_offertest(c):
    of = c.dec.get("offer") or {"premium": 4, "discount": 10}
    rows = []
    for g in P.RFM:
        rp = c.tp["rfm"][g]
        fit = 100 * math.exp(-0.5 * (((of["premium"] - rp["ideal"][0]) / 2.5) ** 2 + ((of["discount"] - rp["ideal"][1]) / 10.0) ** 2))
        f2 = max(0.0, min(100.0, c.nzp(fit, 20)))
        rows.append([P.RFM_LABEL[g], f2, 1 / (1 + math.exp(-(f2 - 45) / 10)), "Likely accepted" if f2 >= 60 else "Borderline" if f2 >= 42 else "Likely ignored"])
    return {"note": f"Tested on your SAVED offer: premium {of['premium']:g}, discount {of['discount']:g}%. Save your draft first.",
            "tables": [T("Offer test", [("Group", "text"), ("Fit (0-100)", "d1"), ("Acceptance", "pct"), ("Verdict", "text")], rows)]}


# ================= UNIT IV: analytics =================

def r_survey(c):
    rows = []
    for s in P.SEGMENTS:
        pi = c.tp[s]["pos_ideal"]
        rows.append([P.SEG_SHORT[s], c.nzp(pi[0], 1.5), c.nzp(pi[1], 1.5), c.nz(c.tp[s]["base"])])
    return {"note": "Household survey of 2,000 homes clustered by segment: where each segment wants brands to sit.",
            "tables": [T("Household survey: ideal positioning", [("Segment", "text"), ("Price position (0-10)", "d1"),
                                                                 ("Benefit message (0-10)", "d1"), ("Volume per firm", "num")], rows)]}


def r_attract(c):
    rows = []
    for cat in c.cats:
        for s in c.segs:
            size = c.tp[s]["base"] * c.tp[s]["cats"][cat]["w"] * c.n
            firms = _rivals_in(c, cat) + (1 if cat in _my_cats(c).values() else 0) if c.prev_group else None
            rows.append([P.CAT_LABEL[cat], P.SEG_SHORT[s], c.nz(size), firms, c.nz(size) / max(1, firms) if firms else None])
    return {"note": "Category size against the number of firms in it. A crowded category splits the same demand more ways.",
            "tables": [T("Category attractiveness", [("Category", "text"), ("Segment", "text"), ("Category volume", "num"),
                                                     ("Firms selling", "num"), ("Volume per firm", "num")], rows)]}


def r_pmap(c):
    rows = []
    for a in c.prev_group:
        pos = (a.get("state") or {}).get("position")
        if pos:
            rows.append([a["alias"], c.nzp(pos[0], 1.0), c.nzp(pos[1], 1.0)])
    return {"note": "Where rivals positioned their brand last round. Brands close together share customers.",
            "tables": [T("Perceptual map", [("Company", "text"), ("Price position", "d1"), ("Benefit message", "d1")], rows)]}


# ================= UNIT IV: digital =================

def r_dbench(c):
    rows = [[P.DIGITAL_LABEL[d], c.nz(P.DIGITAL_CPM[d]), c.nz(P.DIGITAL_CTR[d]) * 100, c.nz(P.DIGITAL_CVR[d]) * 100] for d in P.DIGITAL]
    return {"note": "Typical cost per 1,000 views, click-through rate and conversion rate. Costs rise as more students buy the same channel.",
            "tables": [T("Digital benchmarks", [("Channel", "text"), ("Cost per 1,000 views (Rs)", "d1"), ("CTR (%)", "d2"), ("Conversion (%)", "d2")], rows)]}


def r_dash(c):
    m = ((c.prev_own or {}).get("modules") or {}).get("digital")
    if not m:
        return {"note": "You had no digital campaign last round.", "tables": []}
    rows = [[r[0], r[1], r[2], r[3], r[4] * 100, r[5], r[6] or 0.0, r[7] or 0.0] for r in m["rows"]]
    return {"note": f"Your own digital performance last round. Model accuracy (AUC) was about {c.nzp(m['auc'], 0.15):.2f}.",
            "tables": [T("Campaign dashboard", [("Channel", "text"), ("Spend", "inr"), ("Impressions", "num"), ("Clicks", "num"),
                                                ("CTR (%)", "d2"), ("Conversions", "d1"), ("Cost per conversion", "inr"),
                                                ("Cost per click", "d1")], rows)]}


def r_mlval(c):
    pts = c.state.get("customers") or sum(c.state.get("last_packs", {}).values()) / 3.0
    dataq = min(1.0, pts / 20000.0)
    rows = []
    for ml in (0, 50000, 100000, 200000, 400000):
        auc = 0.5 + 0.32 * (1 - math.exp(-ml / 70000.0)) * (0.35 + 0.65 * dataq) * (0.6 + 0.4 * c.state.get("data", 0.0))
        auc = max(0.5, min(0.9, auc - 0.06 * max(0.0, ml / 100000.0 - 2.0 * dataq)))
        rows.append([ml, c.nzp(auc, 0.12)])
    return {"note": f"Expected model accuracy (AUC) for your data size (about {pts:,.0f} customers). More spend than the data supports overfits and the model gets worse. "
                    "A model near 0.5 is no better than guessing.",
            "tables": [T("ML validation", [("ML investment (Rs)", "inr"), ("Accuracy (AUC)", "d2")], rows)]}


def r_abtest(c):
    rows = [[k, c.nz(4.0 * min(3, k)), c.nz(20000.0 * k)] for k in range(0, 6)]
    return {"note": "Gain in campaign effectiveness from running tests. Gains stop after about three tests.",
            "tables": [T("A/B testing", [("Tests", "num"), ("Effectiveness gain (%)", "d1"), ("Cost (Rs)", "inr")], rows)]}


# ================= UNIT V: neuromarketing =================

def r_panel(c):
    rows = []
    for s in P.SEGMENTS:
        a = c.tp[s]["ad_ideal"]
        rows.append([P.SEG_SHORT[s], c.nzp(a[0], 1.0), c.nzp(a[1], 1.0), c.nzp(a[2], 1.0), c.nzp(6.0, 1.0)])
    return {"note": "Neuro panel baseline (attention, emotion and memory measures): the mix each segment responds to.",
            "tables": [T("What each segment responds to", [("Segment", "text"), ("Emotion (0-10)", "d1"), ("Reason (0-10)", "d1"),
                                                           ("Local story (0-10)", "d1"), ("Best brand cue (0-10)", "d1")], rows)]}


def r_adtest(c):
    cr = c.dec.get("creative")
    if not cr:
        return {"note": "Save a draft of your advertisement first, then buy the test.", "tables": []}
    rows = []
    mem = math.exp(-0.5 * ((cr["brand_cue"] - 6.0) / 3.0) ** 2)
    for s in P.SEGMENTS:
        ie = c.tp[s]["ad_ideal"]
        fit = 100 * math.exp(-0.5 * (((cr["emotion"] - ie[0]) / 2.5) ** 2 + ((cr["rational"] - ie[1]) / 2.5) ** 2 + ((cr["story"] - ie[2]) / 2.5) ** 2))
        # a survey over-states liking: stated intent is higher than real response
        bias = 12.0 if c.sd > 0.25 else 0.0
        f2 = max(0.0, min(100.0, c.nzp(fit, 20) + bias))
        rows.append([P.SEG_SHORT[s], f2, 1 / (1 + math.exp(-(f2 - 40) / 10)), max(0.0, min(1.0, c.nzp(mem, 1.0)))])
    return {"note": "Pre-test of your SAVED advertisement. A survey is cheap but people say more than they feel, so it flatters weak ads. "
                    "Eye tracking and EEG measure real attention and emotion.",
            "tables": [T("Ad pre-test", [("Segment", "text"), ("Engagement (0-100)", "d1"), ("Acceptance", "pct"), ("Memory encoding", "pct")], rows)]}


def r_ethics(c):
    manips = [float((a["decision"].get("creative") or {}).get("manipulation", 0.0)) for a in c.prev_group]
    avg = sum(manips) / len(manips) if manips else 0.0
    return {"note": "Above 7 the regulator fines you and the brand is damaged. If the market average rises above 3.5, trust falls for everyone.",
            "tables": [T("Ethics and regulation", [("Item", "text"), ("Value", "d2")], [
                ["Fine threshold (manipulation level)", 7.0], ["Fine per level above (Rs)", c.nz(50000.0)],
                ["Market average manipulation last round", c.nz(avg)],
                ["Market trust index", c.nzp(c.state.get("trust", 0.9), 0.3)]])]}


def r_clutter(c):
    prod = [float((a["decision"].get("creative") or {}).get("production", 0.0)) for a in c.prev_group]
    return {"note": "How much advertising production your rivals bought last round.",
            "tables": [T("Ad clutter", [("Measure", "text"), ("Value (Rs)", "inr")],
                         [["Average production budget", c.nz(sum(prod) / len(prod) if prod else 0.0)],
                          ["Highest production budget", c.nz(max(prod) if prod else 0.0)]])]}


# ================= UNIT VI: experiential =================

def r_pilot(c):
    rows = []
    for k in P.TOUCH:
        rows.append([P.TOUCH_LABEL[k]] + [c.nz(P.TOUCH_W[k][i]) for i in range(3)])
    return {"note": "Pilot results: how effective each touchpoint is per segment. Digital touchpoints barely work where smartphones are scarce. "
                    "A touchpoint must score above about 0.2 overall or it flops.",
            "tables": [T("Touchpoint pilots", [("Touchpoint", "text")] + [(P.SEG_SHORT[s], "d2") for s in P.SEGMENTS], rows)]}


def r_intent(c):
    rows = []
    for k in P.TOUCH:
        users = sum(1 for d in c.rivals_now if float((d.get("experience") or {}).get(k, {}).get("spend", 0.0)) > 0)
        frac = users / max(1, len(c.rivals_now))
        rows.append([P.TOUCH_LABEL[k], min(1.0, max(0.0, c.nzp(frac, 0.8)))])
    return {"note": "Intelligence on rivals' CURRENT saved plans. The more rivals use a touchpoint, the faster its novelty fades.",
            "tables": [T("Competitor touchpoint intent", [("Touchpoint", "text"), ("Share of rivals planning to use it", "pct")], rows)]}


def r_valuation(c):
    st = c.state
    rows = [["Your customers", st.get("customers") or 0.0], ["Customer lifetime value (Rs)", st.get("clv") or 0.0],
            ["Brand strength (0-100)", st.get("brand", 20.0)], ["Cash (Rs)", 0.0]]
    return {"note": "Final scorecard preview. Final value counts cash, customers valued at lifetime value and brand strength.",
            "tables": [T("Valuation inputs", [("Item", "text"), ("Value", "d1")], [[a, c.nz(b) if a != "Cash (Rs)" else b] for a, b in rows if a != "Cash (Rs)"])]}


def r_lup(c):
    rows = []
    for s in c.segs:
        pp = c.tp[s]["pp"]
        rows.append([P.SEG_SHORT[s], c.nz(pp), c.nzp(0.35 if s == "town" else 0.55 if s == "large_village" else 0.75, 0.3),
                     c.nz(0.20), c.nz(0.45)])
    return {"note": "Ticket price = the rupee price shoppers usually pay for one small pack. Price-point packs (LUP) sell on this price, so the "
                    "grams you fit in matter less, but the price must be close to the ticket price. Round prices (multiples of 5 and 10) sell "
                    "better because traders need not give change.",
            "tables": [T("Price-point (LUP) study", [("Segment", "text"), ("Usual ticket price (Rs)", "d1"),
                                                     ("Share of purchases made as price-point packs", "pct"),
                                                     ("Demand lift for round gram-pack prices (log points)", "d2"),
                                                     ("Demand lift for round LUP prices (log points)", "d2")], rows)]}


# ----- catalogue: id, group, first round, title, description, levels, generator -----
CATALOG = [
    ("industry", "Consumers and price", 1, "Industry overview (free)", "A general briefing on rural consumers and pricing.", lv(("Free", 0, 0.0)), r_industry),
    ("pref", "Consumers and price", 1, "Consumer preference survey", "Ideal quality, pack size and localisation for each category in each segment.", lv(("Basic", 30000, 0.30), ("Detailed", 80000, 0.10)), r_pref),
    ("price", "Consumers and price", 1, "Price perception study", "Fair price per 100 g, price sensitivity and packaging element, by category and segment.", lv(("Basic", 25000, 0.30), ("Detailed", 65000, 0.10)), r_price),
    ("lup", "Consumers and price", 1, "Price-point (LUP) and round-price study", "Usual ticket price, share of sachet-type buying and the value of round prices in each segment.", lv(("Basic", 20000, 0.25), ("Detailed", 50000, 0.08)), r_lup),
    ("catmargin", "Consumers and price", 1, "Category margin potential", "Fair price against cost for a typical pack in each category and segment.", lv(("Basic", 20000, 0.25), ("Detailed", 50000, 0.08)), r_catmargin),
    ("size", "Consumers and price", 1, "Market size and growth", "Category volume and growth in each segment, and how many rivals sell each category.", lv(("Basic", 20000, 0.30), ("Detailed", 55000, 0.10)), r_size),
    ("costs", "Consumers and price", 1, "Supplier cost sheet", "Manufacturing cost by category and quality level.", lv(("Basic", 10000, 0.15), ("Detailed", 25000, 0.03)), r_costs),
    ("concept", "Consumers and price", 1, "Concept test of your saved product", "Tests your saved packs (quality, localisation, grams): would each segment accept them?", lv(("Basic", 40000, 0.35), ("Detailed", 100000, 0.12)), r_concept),
    ("pricetest", "Consumers and price", 1, "Price response test", "Demand at your saved price for each pack and nearby prices.", lv(("Basic", 30000, 0.30), ("Detailed", 75000, 0.10)), r_pricetest),
    ("audit", "Competition", 2, "Competitor audit", "Last round's categories, packs, prices and shares in your market.", lv(("Basic", 25000, 0.30), ("Detailed", 70000, 0.0)), r_audit),
    ("brand", "Competition", 2, "Brand tracker", "Your brand strength against the market average.", lv(("Basic", 20000, 0.30), ("Detailed", 50000, 0.10)), r_brand),
    ("media_habit", "Promotion", 2, "Media habit survey", "How far each medium can reach each segment.", lv(("Basic", 25000, 0.30), ("Detailed", 65000, 0.10)), r_media_habit),
    ("media_curve", "Promotion", 2, "Media response curves", "Reach you get at Rs 1 lakh and Rs 3 lakh.", lv(("Basic", 25000, 0.30), ("Detailed", 65000, 0.10)), r_media_curve),
    ("sov", "Promotion", 3, "Media spend tracker", "What other students spent on each medium last round.", lv(("Basic", 25000, 0.30), ("Detailed", 60000, 0.05)), r_sov),
    ("outlets", "Distribution", 3, "Channel coverage study", "Reach of each channel by segment.", lv(("Basic", 25000, 0.30), ("Detailed", 65000, 0.10)), r_outlets),
    ("chcost", "Distribution", 3, "Channel cost benchmark", "Delivery cost per 100 g by channel and segment.", lv(("Basic", 20000, 0.25), ("Detailed", 50000, 0.08)), r_chcost),
    ("tpl", "Distribution", 3, "Last-mile capacity report", "Delivery partner capacity and last round's congestion.", lv(("Basic", 20000, 0.25), ("Detailed", 50000, 0.08)), r_tpl),
    ("forecast", "Distribution", 3, "Demand forecast", "Expected demand for each of your packs, for planning production.", lv(("Basic", 30000, 0.30), ("Detailed", 75000, 0.10)), r_forecast),
    ("inventory", "Distribution", 4, "Inventory review", "Your production against sales and lost sales, pack by pack.", lv(("Standard", 10000, 0.0)), r_inventory),
    ("partners", "Business models", 4, "SHG partner pool report", "Pool size, training cost and attrition.", lv(("Basic", 25000, 0.30), ("Detailed", 60000, 0.10)), r_partners),
    ("shg", "Business models", 4, "SHG reach study", "Extra reach from SHG networks of different sizes.", lv(("Basic", 25000, 0.30), ("Detailed", 60000, 0.10)), r_shg),
    ("terms", "Business models", 4, "Franchise and platform terms", "Set-up costs, revenue share and commissions.", lv(("Basic", 20000, 0.20), ("Detailed", 45000, 0.05)), r_terms),
    ("fpo", "Business models", 4, "FPO tie-up study", "Cost saving and goodwill from farmer groups.", lv(("Basic", 25000, 0.30), ("Detailed", 60000, 0.10)), r_fpo),
    ("custbase", "Customers and CRM", 5, "Customer base report", "Your customers, churn, acquisition cost and lifetime value.", lv(("Basic", 20000, 0.20), ("Detailed", 50000, 0.05)), r_custbase),
    ("crmbench", "Customers and CRM", 5, "CRM benchmarks", "Market averages for churn, acquisition cost and lifetime value.", lv(("Basic", 25000, 0.30), ("Detailed", 60000, 0.10)), r_crmbench),
    ("privacy", "Customers and CRM", 5, "Privacy and trust audit", "Required compliance level, fines and the market trust index.", lv(("Basic", 20000, 0.20), ("Detailed", 45000, 0.05)), r_privacy),
    ("retention", "Customers and CRM", 5, "Retention response study", "Churn at different retention spends.", lv(("Basic", 25000, 0.30), ("Detailed", 60000, 0.10)), r_retention),
    ("rfm", "Offers and AI", 6, "RFM customer table", "Your customers grouped by recency, frequency and spend.", lv(("Basic", 25000, 0.25), ("Detailed", 60000, 0.08)), r_rfm),
    ("offerpilot", "Offers and AI", 6, "Offer pilot results", "The premium and discount each group responded to best.", lv(("Basic", 35000, 0.30), ("Detailed", 90000, 0.10)), r_offerpilot),
    ("fatigue", "Offers and AI", 6, "Contact fatigue study", "Response and opt-outs by message frequency.", lv(("Basic", 20000, 0.25), ("Detailed", 50000, 0.08)), r_fatigue),
    ("ailift", "Offers and AI", 6, "Personalisation lift study", "Effect of AI personalisation spend.", lv(("Basic", 25000, 0.30), ("Detailed", 60000, 0.10)), r_ailift),
    ("offertest", "Offers and AI", 6, "Offer test of your saved offer", "Would each customer group accept your saved offer?", lv(("Basic", 35000, 0.35), ("Detailed", 90000, 0.12)), r_offertest),
    ("survey", "Segmentation", 7, "Household survey clusters", "Where each segment wants brands to position.", lv(("Basic", 30000, 0.30), ("Detailed", 80000, 0.10)), r_survey),
    ("attract", "Segmentation", 7, "Segment attractiveness table", "Category size against the number of firms selling it.", lv(("Basic", 25000, 0.30), ("Detailed", 60000, 0.10)), r_attract),
    ("pmap", "Segmentation", 8, "Perceptual map", "Where rivals positioned their brands last round.", lv(("Basic", 25000, 0.30), ("Detailed", 60000, 0.10)), r_pmap),
    ("dbench", "Digital and ML", 8, "Digital benchmarks", "Cost, click and conversion rates by channel.", lv(("Basic", 20000, 0.25), ("Detailed", 50000, 0.08)), r_dbench),
    ("dash", "Digital and ML", 9, "Campaign dashboard", "Your own digital impressions, clicks, conversions and costs.", lv(("Standard", 15000, 0.0)), r_dash),
    ("mlval", "Digital and ML", 8, "ML model validation", "Expected model accuracy for your data and budget.", lv(("Basic", 30000, 0.30), ("Detailed", 70000, 0.10)), r_mlval),
    ("abtest", "Digital and ML", 8, "A/B testing study", "Gains from running tests.", lv(("Basic", 20000, 0.25), ("Detailed", 45000, 0.08)), r_abtest),
    ("panel", "Neuro and advertising", 9, "Neuro panel baseline", "What emotion, reason and story each segment responds to.", lv(("Basic", 35000, 0.30), ("Detailed", 90000, 0.10)), r_panel),
    ("adtest", "Neuro and advertising", 9, "Ad pre-test of your saved ad", "Survey, eye tracking or EEG test of your saved advertisement.", lv(("Survey", 25000, 0.40), ("Eye tracking and facial coding", 80000, 0.18), ("EEG and biometrics", 160000, 0.07)), r_adtest),
    ("ethics", "Neuro and advertising", 9, "Ethics and regulation advisory", "Fine thresholds and the market's manipulation level.", lv(("Basic", 20000, 0.25), ("Detailed", 45000, 0.08)), r_ethics),
    ("clutter", "Neuro and advertising", 9, "Ad clutter report", "Rivals' advertising production budgets.", lv(("Basic", 20000, 0.30), ("Detailed", 45000, 0.08)), r_clutter),
    ("pilot", "Experience", 10, "Touchpoint pilots", "How effective each experiential touchpoint is by segment.", lv(("Basic", 30000, 0.30), ("Detailed", 75000, 0.10)), r_pilot),
    ("intent", "Experience", 10, "Competitor touchpoint intelligence", "Which touchpoints rivals plan to use.", lv(("Basic", 30000, 0.35), ("Detailed", 80000, 0.15)), r_intent),
    ("valuation", "Experience", 10, "Valuation inputs", "Customers, lifetime value and brand strength for the final scorecard.", lv(("Basic", 15000, 0.15), ("Detailed", 40000, 0.03)), r_valuation),
]
BY_ID = {c[0]: {"id": c[0], "group": c[1], "round": c[2], "title": c[3], "desc": c[4], "levels": c[5], "gen": c[6]}
         for c in CATALOG}

# reports that can be limited to chosen categories and segments (their full price is higher because they hold more rows)
SCOPE = {"lup": "seg", "pref": "catseg", "price": "catseg", "size": "catseg", "catmargin": "catseg", "attract": "catseg",
         "concept": "catseg", "pricetest": "catseg", "costs": "cat"}
SCOPE_COST_SCALE = 2.0
# reports about your own company or your own draft have no public equivalent
NO_PUBLIC = {"concept", "pricetest", "offertest", "adtest", "custbase", "inventory", "dash", "valuation", "brand",
             "rfm", "forecast", "industry"}
for _id, _r in BY_ID.items():
    _r["scope"] = SCOPE.get(_id)
    _r["public"] = _id not in NO_PUBLIC


def available(round_no):
    return [r for r in BY_ID.values() if r["round"] <= round_no and (P.MARKETING_ENABLED or r["id"] not in P.MARKETING_REPORTS)]


_FEATURES = {}


def _lead(tb):
    """Number of leading label columns (text) that every report keeps."""
    n = 0
    for _l, fmt in tb["cols"]:
        if fmt == "text":
            n += 1
        else:
            break
    return max(1, min(n, len(tb["cols"]) - 1)) if len(tb["cols"]) > 1 else 1


def features_of(rid):
    """The measures (columns) a student can tick before buying: [{'id','label'}]."""
    if rid in _FEATURES:
        return _FEATURES[rid]
    r = BY_ID[rid]
    from . import schema
    rng = random.Random("features")
    dec = schema.default_decision(10)
    st = {"customers": 5000.0, "brand": 20.0, "data": 0.3}
    c = Ctx(rng, 0.0, P.tournament_params(0), st, dec, {"lines": [], "segments": {}, "totals": {}}, [], [], 2, 10, 0)
    feats = []
    try:
        out = r["gen"](c)
        multi = len(out["tables"]) > 1
        for ti, tb in enumerate(out["tables"]):
            lead = _lead(tb)
            for ci, (label, _fmt) in enumerate(tb["cols"]):
                if ci < lead:
                    continue
                feats.append({"id": f"{ti}.{ci}", "label": (tb["title"] + ": " if multi else "") + label})
    except Exception:       # pragma: no cover - a generator that needs real data
        feats = []
    if not feats and rid == "dash":
        feats = [{"id": f"0.{i}", "label": l} for i, l in enumerate(
            ["Spend", "Impressions", "Clicks", "CTR (%)", "Conversions", "Cost per conversion", "Cost per click"], 1)]
    _FEATURES[rid] = feats
    return feats


def price_of(rid, level_idx, n_feat, n_cat=7, n_seg=3):
    """Cost of a custom report: the level's full price scaled by features, categories and segments chosen."""
    r = BY_ID[rid]
    base = r["levels"][level_idx]["cost"]
    if not base:
        return 0.0
    tot = max(1, len(features_of(rid)))
    f = 0.25 + 0.75 * max(0, min(tot, n_feat)) / tot
    sc = r["scope"]
    scale = 1.0
    if sc in ("cat", "catseg"):
        scale = SCOPE_COST_SCALE * (0.2 + 0.8 * max(1, n_cat) / len(P.CAT_KEYS))
    if sc in ("seg", "catseg"):
        scale *= 0.2 + 0.8 * max(1, n_seg) / len(P.SEGMENTS)
    return float(round(base * f * scale / 500.0) * 500)


def cost_of(bought):
    """bought: {report_id: {'cost': ...}} (older saves stored a level number)."""
    total = 0.0
    for rid, b in (bought or {}).items():
        if isinstance(b, dict):
            total += float(b.get("cost", 0.0))
        else:
            r = BY_ID.get(rid)
            if r and 0 <= int(b) < len(r["levels"]):
                total += r["levels"][int(b)]["cost"]
    return total


def _filter(tables, features):
    if features is None:
        return tables
    keep = set(features)
    out = []
    for ti, tb in enumerate(tables):
        lead = _lead(tb)
        cols = list(range(lead)) + [ci for ci in range(lead, len(tb["cols"])) if f"{ti}.{ci}" in keep]
        if len(cols) == lead:
            continue
        out.append({"title": tb["title"], "cols": [tb["cols"][i] for i in cols],
                    "rows": [[row[i] for i in cols] for row in tb["rows"]]})
    return out


def _calc(rid, tables):
    """Numbers for the in-page calculators, built only from the measures the student actually bought."""
    if not tables or rid not in ("price", "costs"):
        return None
    tb = tables[0]
    labels = [c[0] for c in tb["cols"]]
    cat_key = {v: k for k, v in P.CAT_LABEL.items()}
    seg_key = {v: k for k, v in P.SEG_SHORT.items()}
    def col(prefix):
        return next((i for i, l in enumerate(labels) if l.startswith(prefix)), None)
    if rid == "price":
        i1, i2, i3 = col("Fair price per 100 g"), col("Extra per quality point"), col("Packaging element")
        if None in (i1, i2, i3):
            return None
        return {"kind": "price", "rows": [{"cat": cat_key[r_[0]], "seg": seg_key[r_[1]], "base": r_[i1], "perq": r_[i2], "pack": r_[i3]}
                                          for r_ in tb["rows"]]}
    i0, i1, ip = col("Cost per 100 g, localisation 0"), col("Cost per 100 g, localisation 10"), col("Packaging per pack")
    if i0 is None:
        return None
    return {"kind": "cost", "rows": [{"cat": cat_key[r_[0]], "q": r_[1], "c0": r_[i0], "c10": (r_[i1] if i1 is not None else None),
                                      "pack": (r_[ip] if ip is not None else None)} for r_ in tb["rows"]]}


def generate(rid, level_idx, seed, pid, round_no, tp, state, dec, prev_own, prev_group, rivals_now, n,
             features=None, cats=None, segs=None):
    r = BY_ID[rid]
    lvl = r["levels"][level_idx]
    rng = random.Random(f"report-{seed}-{pid}-{round_no}-{rid}-{level_idx}")
    c = Ctx(rng, lvl["sd"], tp, state, dec, prev_own, prev_group, rivals_now, n, round_no, seed)
    if r["scope"]:
        c.cats = [x for x in P.CAT_KEYS if cats is None or x in cats] or list(P.CAT_KEYS)
        c.segs = [x for x in P.SEGMENTS if segs is None or x in segs] or list(P.SEGMENTS)
    out = r["gen"](c)
    out["tables"] = _filter(out["tables"], features)
    out["calc"] = _calc(rid, out["tables"])
    price = price_of(rid, level_idx, len(features) if features is not None else len(features_of(rid)),
                     len(c.cats), len(c.segs))
    out.update({"id": rid, "title": r["title"], "level": lvl["name"], "cost": price, "round": round_no})
    return out


def _coarse(v):
    if isinstance(v, bool) or not isinstance(v, (int, float)) or v == 0:
        return v
    mag = 10 ** (math.floor(math.log10(abs(v))) - 1)
    return round(v / mag) * mag


def public_report(rid, seed, round_no, tp, prev_group, n):
    """Free, coarse, market-wide version of a report: the same for every student, two spotlight categories,
    headline measures only and rounded numbers. None if the topic is your own private data."""
    r = BY_ID[rid]
    if not r["public"] or r["round"] > round_no:
        return None
    rng = random.Random(f"public-{seed}-{rid}")
    c = Ctx(rng, 0.40, tp, {}, {}, None, prev_group, [], n, round_no, seed)
    if r["scope"]:
        c.cats = rng.sample(P.CAT_KEYS, 2)
        c.segs = list(P.SEGMENTS)
    try:
        out = r["gen"](c)
    except Exception:        # pragma: no cover
        return None
    tables = out["tables"][:1]
    if not tables:
        return None
    tb = tables[0]
    lead = _lead(tb)
    keep = list(range(min(len(tb["cols"]), lead + 2)))       # label columns + two headline measures
    rows = [[(_coarse(row[i]) if i >= lead else row[i]) for i in keep] for row in tb["rows"][:8]]
    tb2 = {"title": tb["title"] + " (public estimate)", "cols": [tb["cols"][i] for i in keep], "rows": rows}
    scope_note = (" It covers only " + ", ".join(P.CAT_LABEL[x] for x in c.cats) + ".") if r["scope"] in ("cat", "catseg") else ""
    return {"id": rid, "title": r["title"], "level": "Public", "cost": 0,
            "note": "Free public estimate from trade bodies and last year's surveys: rounded, with large error, headline measures only." + scope_note,
            "tables": [tb2]}
