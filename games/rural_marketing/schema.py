"""The decision form, round by round. Each round adds modules; earlier modules stay on the form
(collapsed) and carry forward your last values, so a rupee you keep spending keeps costing you.

Nothing here is a ready-made bundle: students create the product, channel mix, offer, ad and
experience themselves from numbers and sliders.
"""
import math

from . import params as P
from .engine import PRICE_MAX, PRICE_MIN, line_keys, ref_price  # noqa: F401

LINE_LABEL = {f"{sl}|{s}": f"{sl.upper()} in {P.SEG_SHORT[s]}" for sl in P.SLOTS for s in P.SEGMENTS}
PER = {
    "segment": (P.SEGMENTS, P.SEG_LABEL),
    "medium": (P.MEDIA, P.MEDIA_LABEL),
    "digital": (P.DIGITAL, P.DIGITAL_LABEL),
    "touch": (P.TOUCH, P.TOUCH_LABEL),
    "slot": (P.SLOTS, {sl: "Product " + sl[1] for sl in P.SLOTS}),
    "line": (line_keys(), LINE_LABEL),
}


def f(name, label, typ="number", lo=0, hi=None, step=1, default=0, help="", blank=False, options=None, opt_labels=None):
    return {"name": name, "label": label, "type": typ, "min": lo, "max": hi, "step": step,
            "default": default, "help": help, "blank": blank, "options": options, "opt_labels": opt_labels}


MODULES = [
    {"id": "portfolio", "round": 1, "per": None, "title": "Choose the three categories you will launch",
     "intro": "Seven categories are open. You launch exactly three, and the choice is locked after Round 1. "
              "Categories differ in market size by segment, price level, margin and what shoppers want. Reports show you which are worth entering.",
     "fields": [f(sl, "Product " + sl[1], "select", default=P.DEFAULT_CATS[i], options=P.CAT_KEYS) for i, sl in enumerate(P.SLOTS)]},
    {"id": "product", "round": 1, "per": "slot", "title": "Design each product",
     "intro": "One formulation per product, sold in all three markets. Quality and localisation are common to the product; pack sizes and prices are set per market below.",
     "fields": [
         f("quality", "Quality level (1-10)", "range", 1, 10, 0.5, 5, "Better ingredients cost more to make."),
         f("loc", "Localisation (0-10)", "range", 0, 10, 0.5, 0, "Vernacular pack, local taste and fragrance. Costs Rs 20,000 per point each quarter."),
     ]},
    {"id": "lines", "round": 1, "per": "line", "title": "Packs and prices in each market",
     "intro": "For every product in every market, decide whether to sell, and set up to two packs. Choose the pack type, the grams and the price yourself. "
              "A GRAM pack is chosen by the shopper for its grams and fair price. A PRICE-POINT pack (LUP) is chosen for its rupee price (Rs 5, 10, 20): "
              "shoppers care less about grams, but the price must be a usual ticket price for the segment and the grams you fit in must still be good value. "
              "Round prices (multiples of 5 and 10) are easier for traders, who then need not give change, and sell better. "
              "Leave Pack B at 0 grams to offer one pack only. Prices are limited to 40% to 200% of the fair price for that pack.",
     "fields": [f("serve", "Sell here", "checkbox", default=True),
                f("a_type", "Pack A type", "select", default="gram", options=["gram", "lup"], opt_labels={"gram": "Gram pack", "lup": "Price-point (LUP)"}),
                f("a_g", "Pack A grams", "number", 0, 2000, 1, 0, blank=True),
                f("a_price", "Pack A price (Rs)", "number", 0, 2000, 0.5, 0, blank=True),
                f("b_type", "Pack B type", "select", default="gram", options=["gram", "lup"], opt_labels={"gram": "Gram pack", "lup": "Price-point (LUP)"}),
                f("b_g", "Pack B grams (0 = none)", "number", 0, 2000, 1, 0, blank=True),
                f("b_price", "Pack B price (Rs)", "number", 0, 2000, 0.5, 0, blank=True)]},
    {"id": "focus", "round": 2, "per": "segment", "title": "Where to aim your promotion",
     "intro": "Your media, digital and experience spend is split across segments by these weights.",
     "fields": [f("share", "Share of promotion (any numbers; they are scaled to 100%)", "number", 0, 100, 5, 33)]},
    {"id": "media", "round": 2, "per": "medium", "title": "Promotion budget by medium",
     "intro": "Reach rises with spend but with diminishing returns, and falls when rivals crowd the same medium.",
     "fields": [f("spend", "Spend this quarter (Rs)", "number", 0, 2000000, 5000, 0)]},
    {"id": "push", "round": 2, "per": "line", "title": "Which packs get the promotion push",
     "intro": "Promotion weights say how much of your effort and shelf attention goes to each pack. "
              "They are relative: 50 everywhere means an even push. Push the pack you want to grow.",
     "fields": [f("a_w", "Pack A push (0-100)", "number", 0, 100, 5, 50), f("b_w", "Pack B push (0-100)", "number", 0, 100, 5, 50)]},
    {"id": "channels", "round": 3, "per": "segment", "title": "Distribution mix and stock",
     "intro": "Channel weights are shares of your effort (scaled to 100%) in each market.",
     "fields": [f(c, P.CHANNEL_LABEL[c] + " (weight)", "number", 0, 100, 5, 100 if c == "kirana" else 0) for c in P.CHANNELS]
               + [f("invest", "Channel development spend (Rs)", "number", 0, 1000000, 5000, 0,
                    "Raises coverage of your mix by up to 25%.")]},
    {"id": "stock", "round": 2, "per": "line", "title": "Production: packs to make for each pack",
     "intro": "You can only sell what you produce. Unsold packs are cleared at half their cost; short stock loses sales. "
              "Retailers pay you next quarter for part of your sales, and suppliers are paid next quarter for part of your production.",
     "fields": [f("a_stock", "Pack A to produce", "number", 0, 500000, 100, 0), f("b_stock", "Pack B to produce", "number", 0, 500000, 100, 0)]},
    {"id": "partners", "round": 4, "per": "segment", "title": "Partners: SHGs and franchise outlets",
     "intro": "Build your own network. The pool of SHG entrepreneurs is limited and shared; a higher incentive wins more.",
     "fields": [f("shg", "SHG entrepreneurs to recruit", "number", 0, 200, 1, 0),
                f("incentive", "Incentive per SHG entrepreneur per quarter (Rs)", "number", 0, 3000, 100, 0),
                f("franchise", "New franchise outlets", "number", 0, 50, 1, 0)]},
    {"id": "partner_g", "round": 4, "per": None, "title": "Farmer groups and aggregator platform",
     "fields": [f("fpo", "FPO tie-up commitment per quarter (Rs)", "number", 0, 400000, 10000, 0,
                  "Cuts unit cost up to 5% and builds goodwill in villages."),
                f("aggregator", "Share of sales through an aggregator platform (%)", "number", 0, 60, 5, 0,
                  "Adds reach but you pay a commission that rises as more students use platforms.")]},
    {"id": "crm", "round": 5, "per": None, "title": "Customer acquisition and retention",
     "fields": [f("acquisition", "Acquisition spend (Rs)", "number", 0, 1000000, 5000, 0, "New customers come from a shared pool, so rival spend raises your cost."),
                f("retention", "Retention programme spend (Rs)", "number", 0, 1000000, 5000, 0),
                f("cdp", "Customer data platform investment (0-10)", "range", 0, 10, 1, 0, "Rs 15,000 per level. Builds the data that makes AI work."),
                f("privacy", "Privacy compliance level (0-10)", "range", 0, 10, 1, 0, "Rs 8,000 per level. Fined if below the regulator's level.")]},
    {"id": "offer", "round": 6, "per": None, "title": "Design your cross-sell or upsell offer",
     "intro": "You create the add-on offer. Each customer group has a hidden ideal. Offers that miss it are ignored.",
     "fields": [f("premium", "How premium the add-on is (0-10)", "range", 0, 10, 0.5, 4),
                f("discount", "Discount on the add-on (%)", "number", 0, 40, 1, 10),
                f("personal", "AI personalisation budget (Rs)", "number", 0, 500000, 5000, 0),
                f("frequency", "Messages per customer per month", "number", 0, 12, 1, 2, "More messages cause opt-outs and erode market trust.")]
               + [f("target_" + g, "Target: " + P.RFM_LABEL[g], "checkbox", default=False) for g in P.RFM]},
    {"id": "position", "round": 7, "per": None, "title": "Position your brand",
     "intro": "Choose where your brand sits. Being close to a rival means sharing customers.",
     "fields": [f("price_pos", "Price position (0 economy, 10 premium)", "range", 0, 10, 0.5, 5),
                f("benefit", "Benefit message (0 functional, 10 emotional)", "range", 0, 10, 0.5, 5)]},
    {"id": "digital", "round": 8, "per": "digital", "title": "Digital campaign budgets",
     "fields": [f("spend", "Spend this quarter (Rs)", "number", 0, 1000000, 5000, 0)]},
    {"id": "digital_g", "round": 8, "per": None, "title": "Machine learning and testing",
     "fields": [f("ml", "ML model investment (Rs)", "number", 0, 600000, 5000, 0, "Needs enough customer data. Too much for your data overfits."),
                f("targeting", "How tightly the model targets (0-10)", "range", 0, 10, 1, 0, "Tighter targeting reaches fewer people but converts better if the model is good."),
                f("abtests", "A/B tests (Rs 20,000 each, up to 5)", "number", 0, 5, 1, 0)]},
    {"id": "creative", "round": 9, "per": None, "title": "Create your advertisement",
     "intro": "Each segment has a hidden ideal mix of emotion, reason and local story. Ads must pass the "
              "acceptance threshold or they are ignored and damage the brand.",
     "fields": [f("emotion", "Emotional intensity (0-10)", "range", 0, 10, 0.5, 5),
                f("rational", "Rational product claims (0-10)", "range", 0, 10, 0.5, 5),
                f("brand_cue", "Brand cue prominence (0-10)", "range", 0, 10, 0.5, 5, "Memory is best at a middle level."),
                f("story", "Local culture and story (0-10)", "range", 0, 10, 0.5, 5),
                f("manipulation", "Pressure and manipulation cues (0-10)", "range", 0, 10, 0.5, 0,
                  "Lifts short-term sales. High levels cost market trust and risk a regulator fine."),
                f("production", "Production budget (Rs)", "number", 0, 500000, 5000, 0)]},
    {"id": "experience", "round": 10, "per": "touch", "title": "Experiential and immersive touchpoints",
     "fields": [f("spend", "Spend this quarter (Rs)", "number", 0, 800000, 5000, 0)]},
    {"id": "exp_g", "round": 10, "per": None, "title": "Joining physical and digital",
     "fields": [f("integration", "Integration of physical and digital (0-10)", "range", 0, 10, 0.5, 0,
                  "Bonus only if you use both a physical and a digital touchpoint."),
                f("story", "Brand storytelling strength (0-10)", "range", 0, 10, 0.5, 5)]},
]
BY_ID = {m["id"]: m for m in MODULES}


def modules_for(round_no):
    mods = [m for m in MODULES if m["round"] <= round_no and (P.MARKETING_ENABLED or m["id"] not in P.MARKETING_MODULES)]
    return sorted(mods, key=lambda m: m["round"])


def keys_of(m):
    return PER[m["per"]][0] if m["per"] else [None]


def default_decision(round_no):
    """Suggested starting values for the form (not the autopilot)."""
    dec = {}
    for m in modules_for(round_no):
        if m["per"]:
            dec[m["id"]] = {k: {fl["name"]: fl["default"] for fl in m["fields"]} for k in keys_of(m)}
        else:
            dec[m["id"]] = {fl["name"]: fl["default"] for fl in m["fields"]}
    return dec


def _num(raw, fl, fallback):
    try:
        v = float(raw)
    except (TypeError, ValueError):
        v = float(fallback)
    if math.isnan(v) or math.isinf(v):
        v = float(fallback)
    lo, hi = fl["min"], fl["max"]
    v = max(lo, v)
    if hi is not None:
        v = min(hi, v)
    return v


def parse(form, round_no, saved):
    """Validate the posted form into a clean decision. Unknown or missing values fall back to
    the saved value, then the default."""
    base = default_decision(round_no)
    saved = saved or {}
    dec = {}
    for m in modules_for(round_no):
        mid = m["id"]
        if m["per"]:
            dec[mid] = {}
            for k in keys_of(m):
                dec[mid][k] = {}
                for fl in m["fields"]:
                    name = f"{mid}.{k}.{fl['name']}"
                    fb = saved.get(mid, {}).get(k, {}).get(fl["name"], base[mid][k][fl["name"]])
                    dec[mid][k][fl["name"]] = _field(form, name, fl, fb)
        else:
            dec[mid] = {}
            for fl in m["fields"]:
                name = f"{mid}.{fl['name']}"
                fb = saved.get(mid, {}).get(fl["name"], base[mid][fl["name"]])
                dec[mid][fl["name"]] = _field(form, name, fl, fb)
    return dec


def _field(form, name, fl, fallback):
    if fl["type"] == "checkbox":
        # an unchecked box is absent from the form, so presence means true
        return form.get(name) == "on"
    if fl["type"] == "select":
        v = form.get(name)
        return v if v in fl["options"] else fallback
    return _num(form.get(name), fl, fallback)


def prefill(round_no, saved, last_submitted, last_lines=None):
    """Values to show on the form: this round's saved draft, else last round's submitted decision,
    else the defaults. New modules always start from their defaults."""
    dec = default_decision(round_no)
    source = saved if saved else last_submitted
    if source:
        for m in modules_for(round_no):
            if m["id"] in source:
                dec[m["id"]] = _merge(dec[m["id"]], source[m["id"]])
    if round_no >= 2 and last_lines and not (saved and "stock" in saved):
        for key in line_keys():
            for k in P.PACKS:
                dec["stock"][key][k + "_stock"] = float(round(last_lines.get(f"{key}|{k}", 0.0) / 100.0) * 100)
    return dec


def _merge(base, over):
    out = dict(base)
    for k, v in over.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(out[k], v)
        else:
            out[k] = v
    return out
