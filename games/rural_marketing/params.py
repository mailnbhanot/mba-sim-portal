"""Constants and hidden market parameters for the MKTM679 game.

The *true* consumer preferences are hidden. Students learn about them only through paid
reports (which are noisy). Each tournament gets its own slightly different parameters.
"""
import random

START_CASH = 5_000_000
OVERHEAD = 200_000          # fixed company cost per quarter
SEG_FIXED = 60_000          # fixed cost per segment served
REACH_CAP = 2.5             # max volume = 2.5 x the average firm's base volume
THETA, TAU = 45.0, 10.0     # consumer acceptance threshold on the 0-100 fit score
GROWTH = 1.03               # category growth per round
PRICE_MIN, PRICE_MAX = 0.4, 2.0   # allowed price as a multiple of the segment reference price

SEGMENTS = ["town", "large_village", "remote_village"]
SEG_LABEL = {"town": "Towns (Tier 2/3)", "large_village": "Large villages",
             "remote_village": "Remote villages (Tier 4)"}
SEG_SHORT = {"town": "Towns", "large_village": "Large villages", "remote_village": "Remote villages"}

MEDIA = ["mela", "van", "radio", "vernacular", "trade"]
MEDIA_LABEL = {"mela": "Haat, mela and wall painting", "van": "Promotion van campaign",
               "radio": "Local radio", "vernacular": "Vernacular digital and WhatsApp",
               "trade": "Trade promotion to retailers"}
CHANNELS = ["kirana", "van", "b2b", "tpl", "quick"]
CHANNEL_LABEL = {"kirana": "Wholesaler to kirana", "van": "Own delivery van",
                 "b2b": "B2B retailer app", "tpl": "Last-mile delivery partner",
                 "quick": "Quick-commerce hub (towns only)"}
DIGITAL = ["video", "whatsapp", "social", "search"]
DIGITAL_LABEL = {"video": "Vernacular video", "whatsapp": "WhatsApp campaigns",
                 "social": "Social media", "search": "Search"}
TOUCH = ["mela", "ar", "game", "avatar", "cocreate"]
TOUCH_LABEL = {"mela": "Haat or mela activation (physical)", "ar": "AR or phone product experience (digital)",
               "game": "Gamified WhatsApp loyalty (digital)", "avatar": "Virtual brand avatar or influencer (digital)",
               "cocreate": "Customer co-creation challenge (physical and digital)"}
RFM = ["champions", "loyal", "at_risk", "new"]
RFM_LABEL = {"champions": "Champions (recent, frequent, high spend)", "loyal": "Loyal regulars",
             "at_risk": "At risk (lapsing)", "new": "New customers"}

# static segment parameters. ideal = (quality, grams, localisation)
SEG = {
    "town": {"base": 60_000, "beta": 3.0, "eps": 2.5, "pm": 1.00, "dist": 1.00, "a0": 0.55,
             "ideal": (7.0, 150.0, 4.0)},
    "large_village": {"base": 40_000, "beta": 3.5, "eps": 3.0, "pm": 0.92, "dist": 1.80, "a0": 0.45,
                      "ideal": (5.5, 100.0, 7.0)},
    "remote_village": {"base": 25_000, "beta": 4.2, "eps": 3.5, "pm": 0.85, "dist": 2.40, "a0": 0.30,
                       "ideal": (4.0, 60.0, 9.0)},
}

# ---- product categories: a firm launches 3 of these 7 ----
# g = typical pack (grams), pm = price level per gram, k = cost as a share of fair price (lower = richer margin),
# qs / ls = how the category shifts the ideal quality / localisation, w = category size by segment (units of a typical pack)
CATEGORIES = {
    "toothpaste": {"label": "Toothpaste", "g": 100, "pm": 1.30, "k": 1.00, "qs": 0.5, "ls": -1.0, "w": [0.34, 0.28, 0.15]},
    "tea": {"label": "Packaged tea", "g": 250, "pm": 1.00, "k": 0.92, "qs": 0.0, "ls": 0.0, "w": [0.30, 0.30, 0.25]},
    "detergent": {"label": "Detergent powder", "g": 500, "pm": 0.50, "k": 1.10, "qs": -0.5, "ls": 0.5, "w": [0.28, 0.26, 0.20]},
    "biscuits": {"label": "Biscuits", "g": 100, "pm": 1.20, "k": 0.95, "qs": 0.3, "ls": 0.0, "w": [0.26, 0.22, 0.15]},
    "hair_oil": {"label": "Hair oil", "g": 100, "pm": 1.50, "k": 0.85, "qs": -0.3, "ls": 1.5, "w": [0.12, 0.20, 0.24]},
    "noodles": {"label": "Instant noodles", "g": 70, "pm": 1.20, "k": 1.08, "qs": 0.8, "ls": -1.5, "w": [0.18, 0.12, 0.05]},
    "soap": {"label": "Bathing soap", "g": 100, "pm": 1.10, "k": 1.00, "qs": -0.2, "ls": 0.5, "w": [0.16, 0.18, 0.17]},
}
CAT_KEYS = list(CATEGORIES)
CAT_LABEL = {k: v["label"] for k, v in CATEGORIES.items()}
N_PRODUCTS = 3
SLOTS = ["p1", "p2", "p3"]
PACKS = ["a", "b"]                       # two pack slots per product per segment
PACK_FIXED_COST = 0.8                    # packaging cost per pack, Rs
PACK_FIXED_PRICE = 1.2                   # packaging element in the fair price, Rs
PRODUCT_FIXED = 40_000                   # upkeep per launched product per quarter
SKU_FIXED = 6_000                        # artwork, tooling and listing per active pack per quarter
PACK_TYPES = {"gram": "Gram pack (shopper chooses by grams)", "lup": "Price-point pack, LUP (shopper chooses by Rs 5 / 10 / 20)"}
LUP_PP = {"town": 20.0, "large_village": 10.0, "remote_village": 5.0}   # typical ticket price shoppers like to pay
MARKETING_ENABLED = False                # Stage 1: no marketing levers. Set True to bring back promotion, digital, ads, experiences
MARKETING_MODULES = {"focus", "media", "push", "digital", "digital_g", "creative", "experience", "exp_g"}
MARKETING_REPORTS = {"brand", "media_habit", "media_curve", "sov", "dbench", "dash", "mlval", "abtest", "panel", "adtest",
                     "ethics", "clutter", "pilot", "intent"}


def slot_labels(cats):
    """Names for the three products. A repeated category is numbered: Soap 1, Soap 2, Soap 3."""
    names = [CAT_LABEL[cats[sl]] for sl in SLOTS]
    out = {}
    for i, sl in enumerate(SLOTS):
        same = [j for j, n in enumerate(names) if n == names[i]]
        out[sl] = names[i] if len(same) == 1 else f"{names[i]} {same.index(i) + 1}"
    return out

SEG_GFAC = {"town": 1.3, "large_village": 1.0, "remote_village": 0.6}
AR_SHARE = 0.15                          # share of sales the retail trade pays a quarter later
AP_SHARE = 0.20                          # share of production cost paid to suppliers a quarter later
OVERDRAFT_RATE = 0.03                    # interest per quarter on a bank overdraft
DEFAULT_CATS = ["toothpaste", "tea", "detergent"]

# channel: coverage (share of outlets reached) and cost factor, per segment
CH = {
    "kirana": {"cov": [0.55, 0.45, 0.30], "cost": [1.0, 1.0, 1.0]},
    "van": {"cov": [0.45, 0.60, 0.55], "cost": [1.5, 1.3, 1.2]},
    "b2b": {"cov": [0.60, 0.40, 0.20], "cost": [1.1, 1.2, 1.4]},
    "tpl": {"cov": [0.55, 0.50, 0.45], "cost": [1.3, 1.3, 1.1]},
    "quick": {"cov": [0.70, 0.10, 0.0], "cost": [2.0, 2.5, 3.0]},
}
# media responsiveness (max reach) by segment, and speed k per Rs 1 lakh
MEDIA_R = {"mela": [0.35, 0.65, 0.75], "van": [0.25, 0.60, 0.70], "radio": [0.45, 0.55, 0.50],
           "vernacular": [0.65, 0.45, 0.20], "trade": [0.40, 0.45, 0.40]}
MEDIA_K = {"mela": 1.1, "van": 0.9, "radio": 0.8, "vernacular": 1.3, "trade": 1.0}
DIGITAL_R = {"video": [0.60, 0.45, 0.25], "whatsapp": [0.55, 0.50, 0.30],
             "social": [0.65, 0.40, 0.15], "search": [0.50, 0.25, 0.10]}
DIGITAL_K = {"video": 1.0, "whatsapp": 1.2, "social": 1.1, "search": 1.4}
DIGITAL_CTR = {"video": 0.012, "whatsapp": 0.045, "social": 0.018, "search": 0.035}
DIGITAL_CPM = {"video": 90.0, "whatsapp": 55.0, "social": 110.0, "search": 160.0}   # Rs per 1000 impressions
DIGITAL_CVR = {"video": 0.020, "whatsapp": 0.050, "social": 0.018, "search": 0.040}
TOUCH_W = {"mela": [0.30, 0.70, 0.90], "ar": [0.80, 0.30, 0.05], "game": [0.60, 0.50, 0.20],
           "avatar": [0.70, 0.40, 0.10], "cocreate": [0.50, 0.55, 0.45]}
TOUCH_K = {"mela": 0.9, "ar": 1.2, "game": 1.1, "avatar": 1.0, "cocreate": 0.8}
TOUCH_PHYSICAL = {"mela", "cocreate"}
TOUCH_DIGITAL = {"ar", "game", "avatar", "cocreate"}
# ad creative ideals by segment: (emotion, rational, local story)
AD_IDEAL = {"town": (6.0, 6.5, 3.5), "large_village": (7.0, 4.5, 6.5), "remote_village": (7.5, 3.0, 8.5)}
# positioning ideals by segment: (price position 0-10, benefit 0 functional - 10 emotional)
POS_IDEAL = {"town": (6.5, 6.0), "large_village": (4.5, 4.5), "remote_village": (2.5, 3.0)}
# RFM groups: share of customers, ideal offer (premium, discount), base attach rate
RFM_PARAM = {"champions": {"share": 0.15, "ideal": (8.0, 5.0), "attach": 0.40},
             "loyal": {"share": 0.30, "ideal": (5.0, 12.0), "attach": 0.28},
             "at_risk": {"share": 0.25, "ideal": (2.5, 28.0), "attach": 0.14},
             "new": {"share": 0.30, "ideal": (3.5, 18.0), "attach": 0.18}}


def tournament_params(seed):
    """True hidden parameters for one tournament."""
    rng = random.Random(f"params-{seed}")
    out = {}
    for seg, sp in SEG.items():
        q, g, loc = sp["ideal"]
        cats = {}
        for ck, cv in CATEGORIES.items():
            cats[ck] = {
                "ideal": [q + cv["qs"] + rng.uniform(-0.8, 0.8), cv["g"] * SEG_GFAC[seg] * rng.uniform(0.85, 1.15),
                          max(0.0, loc + cv["ls"] + rng.uniform(-1.0, 1.0))],
                "w": cv["w"][SEGMENTS.index(seg)] * rng.uniform(0.85, 1.15),
                "beta": sp["beta"] * rng.uniform(0.85, 1.15),
            }
        out[seg] = {
            "base": sp["base"] * rng.uniform(0.85, 1.15),
            "beta": sp["beta"] * rng.uniform(0.85, 1.15),
            "pp": LUP_PP[seg] * rng.uniform(0.8, 1.25),
            "cats": cats,
            "ad_ideal": [v + rng.uniform(-0.8, 0.8) for v in AD_IDEAL[seg]],
            "pos_ideal": [v + rng.uniform(-0.6, 0.6) for v in POS_IDEAL[seg]],
        }
    out["rfm"] = {k: {"share": v["share"] * rng.uniform(0.85, 1.15),
                      "ideal": [v["ideal"][0] + rng.uniform(-0.8, 0.8), v["ideal"][1] * rng.uniform(0.85, 1.15)],
                      "attach": v["attach"] * rng.uniform(0.9, 1.1)} for k, v in RFM_PARAM.items()}
    tot = sum(v["share"] for v in out["rfm"].values())
    for v in out["rfm"].values():
        v["share"] /= tot
    return out


def new_state():
    return {"brand": 20.0, "trust": 0.9, "data": 0.0, "customers": None, "loyalty": 0.0,
            "shg": {s: 0 for s in SEGMENTS}, "franchise": {s: 0 for s in SEGMENTS},
            "cats": None, "products": {}, "position": None, "last_packs": {s: 0 for s in SEGMENTS},
            "fin": {"cash": START_CASH, "ar": 0.0, "ap": 0.0, "debt": 0.0, "capital": START_CASH, "retained": 0.0},
            "churn": None, "cac": None, "clv": None}
