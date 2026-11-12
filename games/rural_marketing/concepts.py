"""The Concept Corner: every rule, term, formula and calculation a student needs, in one place.

Principle: the RULES of the game are public and explained here (costs of running the company, price limits,
accounting timing, ranking). The MARKET FACTS (what shoppers want, how price-sensitive they are, how big each
category is, making cost per gram) are hidden and must be bought as reports. Worked examples use made-up
numbers and are labelled as illustrations.
"""


def E(t, p=(), f=(), ex=None, tip=None):
    return {"t": t, "p": list(p), "f": list(f), "ex": ex, "tip": tip}


SECTIONS = [
    {"id": "start", "title": "1. How the game works", "items": [
        E("The aim", [
            "You run a packaged-goods company in rural and semi-urban India for 10 quarters (rounds). You pick three products, design them, choose pack sizes and prices for three markets, "
            "and try to earn a profit and a good market share. Consumers decide what sells. If they do not like a pack, they do not buy it and you still pay your costs."]),
        E("What you decide, round by round (Stage 1: no marketing)", [
            "Round 1: choose three categories, design each product, set up to two packs per product per market, with grams and prices.",
            "Round 2: also decide how many packs of each type to produce, and fix what Round 1 got wrong.",
            "Round 3: choose your distribution channels. Round 4: partners (SHG entrepreneurs, franchise outlets, farmer groups, aggregator platforms).",
            "Round 5: customer acquisition and retention. Round 6: add-on offers. Round 7: brand positioning. Rounds 8 to 10: refine everything you have built.",
            "Promotion, digital marketing, advertising and experiential marketing are switched off in Stage 1 so that you focus on product, pack, price, cost and cash."]),
        E("What you see", [
            "Left menu: Concept corner (this page), Financial statements, Free public data, Report shop and my reports, Standings and your past results."]),
        E("Who competes with whom", [
            "Your teacher puts you in a market with other students (or teams). Every decision of every company changes the market: if rivals cut prices, your share falls; "
            "if many firms enter the same category, each gets a thinner slice."]),
        E("If you do not submit", [
            "If you do not submit a decision, you have designed no product, so you sell nothing. You still pay the company overhead every quarter, "
            "and anything you bought in the report shop. A saved draft is NOT used when the round closes. Only a submission counts."]),
        E("Ranking", [
            "Your score each round is a weighted average of two percentile ranks among all companies: profit and market share. The default weight is 60% profit and 40% share, "
            "and your teacher can change it. Overall standings average your score over the rounds."],
          f=["round score = w x profit percentile + (1 - w) x market-share percentile"],
          tip="Chasing only share (by selling below cost) or only profit (by selling tiny volumes) both lose ranking points."),
    ]},
    {"id": "products", "title": "2. Categories, products and packs", "items": [
        E("Category", [
            "A category is a kind of product: toothpaste, packaged tea, detergent powder, biscuits, hair oil, instant noodles, bathing soap. Categories differ in how big the market is in each segment, "
            "how much people pay per gram, how much margin there is, and what kind of product shoppers want. You launch three products. You may even launch the same category more than once "
            "(for example three soaps): they are then named Soap 1, Soap 2 and Soap 3 so you can tell them apart. Two similar products in one category take sales from each other."]),
        E("Product, pack and SKU", [
            "A product is one formulation: a quality level and a localisation level. A pack is the product in a particular size at a particular price. "
            "You can offer two packs (A and B) of each product in each market. Each active pack is a SKU (stock keeping unit) and carries a listing cost every quarter."]),
        E("Segments (markets)", [
            "Towns (Tier 2 and 3), large villages and remote villages (Tier 4). They differ in income, preferences, how easy they are to reach, and delivery cost. "
            "One product formulation is sold in all three, but you choose packs and prices separately for each."]),
        E("Quality (1 to 10)", [
            "Better ingredients. Raises making cost and the fair price. Each segment has a hidden ideal quality for each category: towns tend to want higher quality than remote villages."]),
        E("Localisation (0 to 10)", [
            "Vernacular pack, local taste or fragrance. Raises making cost by 2% for each point and costs Rs 20,000 per point per product every quarter. Remote and large villages like more of it."]),
        E("Hidden ideal and fit score", [
            "For every category and segment there is a hidden ideal product: ideal quality, ideal pack size in grams and ideal localisation. You find it out by buying the consumer preference survey. "
            "Your pack is given a fit score from 0 to 100 that falls as it moves away from the ideal in any of the three dimensions. A pack that is far off on one dimension scores low even if the others are perfect."],
          f=["fit = 100 x exp(-0.5 x [ ((quality - ideal q)/2)^2 + (ln(grams/ideal grams)/0.5)^2 + ((localisation - ideal l)/2.5)^2 ])"],
          ex="Illustration: ideal quality 6 and your quality 8 gives a quality term of (2/2)^2 = 1. If grams and localisation are perfect, fit = 100 x exp(-0.5) = 61."),
        E("Acceptance threshold", [
            "Shoppers buy a pack only if the fit score is high enough. Around a fit of 45 half of the interested shoppers accept the pack. Well below 45, almost nobody buys, whatever the price. Well above, almost everybody does."],
          f=["acceptance = 1 / (1 + exp(-(fit - 45) / 10))"],
          ex="Fit 45 gives 50% acceptance, fit 65 gives about 88%, fit 25 gives about 12%.",
          tip="Use the concept test report on your saved draft before you submit."),
        E("Gram pack", [
            "A gram pack is chosen by the shopper for its size: 100 g, 250 g, 500 g. It is judged on grams against the segment's ideal, and its price is compared with the fair price for those grams."]),
        E("Price-point pack (LUP)", [
            "LUP stands for low unit price pack: the Rs 5, Rs 10 or Rs 20 sachet or small pack. Shoppers choose it by the rupee price, not by grams. In the game this means: "
            "(1) grams matter much less to acceptance, (2) the price must be close to the usual ticket price of the segment (small in remote villages, larger in towns), "
            "(3) the grams you fit in still matter through value for money, because fewer grams for the same price means a higher price index, and (4) a price that needs change is penalised more than for a gram pack. "
            "Buy the price-point (LUP) study for the usual ticket price."],
          f=["LUP fit = fit with a wide grams tolerance (0.5 becomes 1.4) x (0.4 + 0.6 x ticket-price match)",
             "ticket-price match = exp(-0.5 x (ln(price / usual ticket price) / 0.6)^2)"]),
        E("Round prices", [
            "Traders do not like giving change. Prices that are multiples of 10 (10, 20, 30) sell best, other multiples of 5 (15, 25) next, whole rupees next, then prices ending in 0.5, and prices like 12.3 or 24.7 sell worst. "
            "For price-point packs the effect is about twice as strong. The effect is a lift or a penalty on demand, so a slightly dearer round price can beat a cheaper awkward price."],
          ex="Rs 60 can sell more than Rs 59.7 even though it is dearer."),
    ]},
    {"id": "pricing", "title": "3. Price, fair price and cost cover", "items": [
        E("Price", ["The price you charge for one pack, in rupees. You choose it freely between 40% and 200% of the fair price of that pack. Prices outside that band are moved to the nearest limit."]),
        E("Fair price", [
            "The price shoppers in a segment consider fair for a pack of your grams and quality. It rises with grams and quality, differs by category and segment, and includes a packaging element. "
            "The price perception study gives the three numbers you need, and you can use the fair price calculator in the Report shop once you have bought them."],
          f=["fair price = grams/100 x (price per 100 g at quality 5 + extra per quality point x (quality - 5)) + packaging element"],
          ex="Illustration: price per 100 g at quality 5 is Rs 10, extra per quality point Rs 1.6, packaging Rs 1.2. A 250 g pack at quality 7 has fair price = 2.5 x (10 + 1.6 x 2) + 1.2 = Rs 34.7."),
        E("Price index", ["Your price divided by the fair price. 1.00 means priced at fair, 0.90 means 10% below fair."], f=["price index = price / fair price"]),
        E("Price sensitivity (elasticity)", [
            "How strongly demand reacts to price. If sensitivity is 3, a pack priced 10% below the market average wins roughly 30% more share, and one priced 10% above loses roughly 30%. "
            "Sensitivity is higher in remote villages. The price perception study gives it by category and segment."],
          f=["share weight = exp(-sensitivity x ln(price index / average price index) + ln(fit/50) + round-price effect)"]),
        E("Market share (in your own market)", [
            "Within a category and segment, each pack's weight is the formula above. Your share is your weight divided by the total of everyone's. A second pack of the same product only adds about a quarter of a pack's weight (it mostly takes sales from your first pack). "
            "The market's total demand also moves with the average price level: when everyone raises prices, fewer packs are bought in total."]),
        E("Making cost (variable)", [
            "What it costs to produce one pack: grams times the cost per gram (which rises with quality and category) times (1 + 2% per point of localisation), plus a packaging cost per pack. "
            "Small packs cost more per gram because the packaging cost is the same for every pack. The supplier cost sheet report gives the cost per 100 g by category and quality. Use the making cost calculator."],
          f=["making cost = grams/100 x cost per 100 g (quality, category) x (1 + 0.02 x localisation) + packaging per pack"]),
        E("Delivery cost (variable)", [
            "Taking a pack to the shop. It grows with pack size (but less than proportionally), is higher in remote villages, and depends on the channels you use. The channel cost benchmark shows it."],
          f=["delivery cost per pack = segment delivery rate x (grams/100)^0.7 x channel cost factor"]),
        E("Do I meet the basic cost?", [
            "On the decision form, once you have bought the supplier cost sheet, each pack shows a live check: does the price cover the making cost? "
            "To judge fully, remember that delivery and fixed costs also have to be recovered. A price that covers only making cost still loses money after delivery and fixed costs."],
          f=["contribution per pack = price - making cost - delivery cost per pack", "contribution margin % = contribution per pack / price"],
          ex="Illustration: price Rs 30, making cost Rs 17, delivery Rs 2.5. Contribution = Rs 10.5 per pack, margin 35%."),
        E("Break-even", [
            "The number of packs you must sell for the contribution to cover the fixed costs that the pack, product and market bring."],
          f=["break-even packs = fixed costs to recover / contribution per pack"],
          ex="Illustration: a pack adds Rs 6,000 listing cost and its share of Rs 40,000 product upkeep, say Rs 20,000 in all. At Rs 10.5 contribution you need 1,905 packs just to break even."),
        E("Mark-up and margin", [
            "Mark-up is profit as a percentage of cost. Margin is profit as a percentage of price. A 50% mark-up on cost is only a 33% margin on price."],
          f=["mark-up = (price - cost) / cost", "margin = (price - cost) / price"]),
        E("Cost-plus and market-based pricing", [
            "Cost-plus: add a margin to cost. Market-based: start from what shoppers consider fair and what rivals charge. Good pricing uses both: stay near fair, check that cost is covered, then choose a round price."]),
    ]},
    {"id": "costs", "title": "4. Fixed and variable costs", "items": [
        E("Variable costs: grow with sales", [
            "Production cost of the packs you make, delivery and commissions, and the cost of add-on offers. If you sell more packs they rise. They appear above the contribution line on your profit and loss account."]),
        E("Fixed costs: grow with what you launch", [
            "Costs you pay whatever you sell. In this game they grow as your range grows:",
            "Company overhead: Rs 2,00,000 every quarter, always.",
            "Product upkeep: Rs 40,000 for every product that has at least one pack on sale.",
            "Pack listing and artwork: Rs 6,000 for every pack on sale (one product with two packs in three markets is six packs).",
            "Localisation upkeep: Rs 20,000 per point of localisation per product.",
            "Market fixed costs: Rs 60,000 for every segment in which you sell.",
            "Product reformulation: if you change a product's quality or localisation from the previous round, Rs 1,00,000 x (change in quality / 10 + change in localisation / 10).",
            "Programme costs: channel development, partner network and customer programmes.",
            "Research: the reports you buy. Fines: privacy and regulator fines."]),
        E("Why a wide range can lose money", [
            "Each extra product, pack and market adds fixed cost. It pays only if its contribution is larger than the fixed cost it brings."],
          ex="A pack that sells too little to cover its Rs 6,000 listing cost reduces your profit even if each pack earns a contribution."),
        E("Semi-fixed idea in this game", ["Fixed costs are fixed for a quarter, not forever. You change them by changing what you launch."]),
        E("Unsold stock", [
            "You decide how many packs to produce (from Round 2). You can sell only what you made. Packs you made but did not sell are cleared at half their making cost, so the loss is half the production cost of the surplus. "
            "Demand you could not meet because stock ran out is lost sales."],
          f=["packs sold = minimum(demand, packs produced)", "cost of surplus = 50% x making cost x (produced - sold)"],
          tip="Order near the forecast. The demand forecast report helps. Too little loses sales, too much wastes money."),
    ]},
    {"id": "finance", "title": "5. Financial statements", "items": [
        E("Profit and loss account", [
            "Shows what you earned and spent in the round. Revenue minus variable costs is the contribution. Contribution minus fixed costs is operating profit. Interest on any overdraft is then taken off to give net profit. "
            "There is no tax in the game. The cumulative column adds up all rounds so far."],
          f=["contribution = revenue - variable costs", "operating profit = contribution - fixed costs", "net profit = operating profit - interest"]),
        E("Balance sheet", [
            "A snapshot at the end of the round. Assets: cash and trade receivables. Liabilities: trade payables and any bank overdraft. Equity: share capital (your starting Rs 50 lakh) plus retained earnings (all profits and losses so far). It always balances."],
          f=["assets = liabilities + equity", "retained earnings = sum of net profit of all rounds"]),
        E("Trade receivables", ["Retailers pay 15% of your sales one quarter late. The unpaid part is an asset called receivables."], f=["receivables = 15% x sales revenue of the round"]),
        E("Trade payables", ["You pay suppliers 20% of your production cost one quarter late. The unpaid part is a liability called payables."], f=["payables = 20% x production cost of the round"]),
        E("Cash flow statement", [
            "Shows where cash came from and went to. Profit is adjusted for the timing of receipts and payments. Cash from operations is net profit minus the increase in receivables plus the increase in payables. "
            "In Round 1 the share capital you started with is shown as cash introduced."],
          f=["cash from operations = net profit - increase in receivables + increase in payables", "closing cash = opening cash + operations + financing"]),
        E("Profit is not cash", [
            "A fast-growing firm can be profitable and still short of cash, because it pays for production now and is paid by retailers later."]),
        E("Bank overdraft", ["If cash would fall below zero, the bank lends the shortfall as an overdraft. It costs 3% interest every quarter and is repaid first when cash returns."], f=["interest = 3% x overdraft at the start of the round"]),
        E("Useful ratios", [
            "Gross or contribution margin: contribution / revenue. Net margin: net profit / revenue. Return on equity: net profit / equity. Working capital: receivables - payables. "
            "Operating leverage: the more fixed cost you carry, the more profit swings with sales."]),
        E("Reading the statements", [
            "Check first: did contribution cover fixed costs? Then: is the cash from operations lower than profit (growth tied up in receivables)? Then: is the overdraft growing?"]),
    ]},
    {"id": "reports", "title": "6. Reports and data", "items": [
        E("Free public data and paid reports", [
            "Every research topic that is not your own private data has a free public version. It is coarse: numbers are rounded, it carries a large error, covers only two spotlight categories and shows two headline measures. "
            "Everyone sees the same public data. A paid report is precise, covers the categories and segments you choose and lets you choose the measures."]),
        E("Choosing measures, scope and accuracy", [
            "For each paid report you tick the measures (columns) you want, the categories and segments, and the accuracy level. The price falls as you select less. Basic is cheaper and noisier. Detailed is dearer and close to the truth."],
          f=["price = full price of the level x (0.25 + 0.75 x measures chosen / measures available) x scope factor",
             "scope factor = 2 x (0.2 + 0.8 x categories chosen / 7) x (0.2 + 0.8 x segments chosen / 3) for category and segment reports"]),
        E("Noise and accuracy", [
            "A Basic report's numbers can be off by about 30%, a Detailed report's by about 10%. Buying the same report twice does not help because the error is fixed for you. Decide what precision your decision needs."]),
        E("Tests of your own draft", [
            "The concept test, price response test and offer test examine the draft you saved. Press Save draft first. A test of a draft you did not save tests the default form values."]),
        E("When are reports charged?", ["The cost is charged when the round is processed and shows in the profit and loss account as research."]),
    ]},
    {"id": "dist", "title": "7. Distribution (Round 3)", "items": [
        E("Channel", ["The route a pack takes to the shopper: wholesaler to kirana, own delivery van, B2B retailer app, last-mile delivery partner, quick-commerce hub (towns only). Each channel has coverage and a cost to serve in each segment."]),
        E("Coverage and availability", [
            "Coverage is the share of shops a channel reaches. Your weights say how you split effort across channels. More coverage lifts sales but cost to serve rises. "
            "Channel development spend raises the coverage of your mix by up to 25%."],
          f=["availability = sum of (channel weight x channel coverage) x development effect"]),
        E("Last-mile congestion", ["The delivery partner has limited capacity in each segment, shared by all companies. If many of you use it, delivery gets slower and dearer for everyone."]),
        E("Cost to serve", ["Delivery cost per pack for the channel mix you chose. Compare it with contribution per pack before pushing a channel."]),
    ]},
    {"id": "models", "title": "8. Rural business models (Round 4)", "items": [
        E("SHG entrepreneur", ["A self-help-group woman who sells your packs in her village. The pool of such entrepreneurs is limited and shared. If requests exceed the pool, entrepreneurs go to those who offer the higher incentive."],
          f=["extra reach = 0.22 x segment factor x (1 - exp(-SHG count / 12))"]),
        E("Franchise outlet", ["An outlet that carries your brand. It adds reach and costs Rs 20,000 to set up each. Franchises pay you a small commission-like margin share on sales."]),
        E("FPO tie-up", ["A farmer producer organisation. Your commitment cuts unit cost by up to 5% and builds goodwill in villages."]),
        E("Aggregator platform", ["An online or app platform. It adds reach and takes a commission that rises as more students use platforms."]),
        E("Capital-light or controlled", ["Partners cut your own capital need but give you less control over price and service. Own vans cost more but you control the experience."]),
    ]},
    {"id": "crm", "title": "9. Customers and CRM (Rounds 5 and 6)", "items": [
        E("Customer acquisition cost (CAC)", ["What it costs to win one new customer. It rises when rivals also spend on acquisition from the same pool."], f=["CAC = acquisition spend / new customers won"]),
        E("Churn", ["The share of customers lost in a quarter. Retention spend lowers it. Poaching by rivals raises it."], f=["churn = lost customers / customers at start"]),
        E("Customer lifetime value (CLV)", ["The profit a customer is expected to bring over their life with you. The game uses a simple form."],
          f=["CLV = contribution per customer per quarter x (1 - churn) / (churn + 0.02)", "rule of thumb: CLV / CAC should be at least 3"]),
        E("Customer data platform", ["An investment that builds usable data. Costs Rs 15,000 per level. Needed for AI personalisation to work."]),
        E("Privacy and trust", ["The regulator requires a minimum privacy compliance level. Below it you are fined and trust in the whole market falls, which lowers everyone's demand."]),
        E("RFM segmentation", ["Customers grouped by recency, frequency and monetary value: champions, loyal regulars, at-risk and new customers. Each group likes a different offer."]),
        E("Cross-sell and upsell", ["Cross-sell offers another product; upsell offers a better version. You choose how premium the offer is and the discount."], f=["take-up = group's base rate x acceptance x (1 + personalisation) x (1 - fatigue) x trust"]),
        E("Contact fatigue", ["Too many messages cause opt-outs and erode trust for the whole market."]),
    ]},
    {"id": "later", "title": "10. Coming in Stage 2 (switched off now)", "items": [
        E("Promotion and media", ["Haat, mela, vans, radio and vernacular digital. Reach has diminishing returns and rivals crowd you out. Not part of Stage 1."]),
        E("Digital metrics and machine learning", ["Impressions, click-through rate (CTR = clicks / impressions), cost per click, conversion rate, cost per acquisition, return on ad spend (ROAS = revenue / ad spend), and model accuracy (AUC)."]),
        E("Neuromarketing and ethics", ["Pre-testing advertisements with surveys, eye tracking and EEG, and where persuasion becomes manipulation."]),
        E("Experiential and immersive marketing", ["Physical and digital touchpoints, novelty that fades when rivals copy you, and why digital experiences fail where smartphones are scarce."]),
    ]},
    {"id": "glossary", "title": "11. Glossary (A to Z)", "items": [
        E("A/B test", ["Showing two versions of something to compare which works better."]),
        E("Acceptance", ["The share of interested shoppers who find a pack good enough to buy. See acceptance threshold."]),
        E("Aggregator", ["A platform that connects many small sellers to buyers."]),
        E("Artwork", ["The design of the pack. Each pack on sale needs one, which is part of the listing cost."]),
        E("Brand", ["The name and reputation shoppers connect with your products."]),
        E("Category", ["A kind of product, such as tea or soap."]),
        E("CLV, CAC, churn", ["See customers and CRM."]),
        E("Contribution", ["Revenue minus variable costs. It pays for fixed costs and then becomes profit."]),
        E("Cost to serve", ["The cost of getting a pack to the shopper through a channel."]),
        E("Elasticity", ["How much demand changes when price changes. See price sensitivity."]),
        E("FMCG", ["Fast-moving consumer goods: packaged goods bought often and quickly, such as soap and tea."]),
        E("Fixed cost", ["A cost you pay whatever you sell."]),
        E("FPO", ["Farmer producer organisation."]),
        E("Haat", ["A weekly village market."]),
        E("Kirana", ["A small neighbourhood or village shop."]),
        E("Last mile", ["The final leg of delivery to the shop or home."]),
        E("Listing cost", ["The quarterly cost of keeping a pack on sale (artwork, tooling, trade listing)."]),
        E("Localisation", ["Adapting the product and pack to local language, taste and culture."]),
        E("LUP", ["Low unit price pack, such as a Rs 5 or Rs 10 sachet."]),
        E("Market share", ["Your share of the packs sold in the market. In the ranking it is measured on volume."]),
        E("Mark-up and margin", ["See pricing."]),
        E("Overdraft", ["Money borrowed from the bank when your cash would go below zero."]),
        E("Price point", ["A price people recognise and pay easily: Rs 5, 10, 20."]),
        E("Receivables and payables", ["Money owed to you by retailers, and money you owe suppliers."]),
        E("RFM", ["Recency, frequency, monetary value."]),
        E("SHG", ["Self-help group."]),
        E("SKU", ["A single stock keeping unit: one pack of one product."]),
        E("Tier 2, 3, 4", ["Classes of town and village by size and income, from larger towns to remote villages."]),
        E("Variable cost", ["A cost that grows with the number of packs sold."]),
        E("Working capital", ["Money tied up in the day-to-day running of the business: receivables less payables (and stock)."]),
    ]},
    {"id": "sheet", "title": "12. Formula sheet", "items": [
        E("All formulas in one place", [], f=[
            "fair price = grams/100 x (P100 + Pq x (quality - 5)) + packaging",
            "price index = price / fair price",
            "fit = 100 x exp(-0.5 x [((q - ideal q)/2)^2 + (ln(g / ideal g)/0.5)^2 + ((l - ideal l)/2.5)^2])",
            "acceptance = 1 / (1 + exp(-(fit - 45)/10))",
            "making cost = grams/100 x C100 x (1 + 0.02 x localisation) + packaging",
            "contribution per pack = price - making cost - delivery",
            "break-even packs = fixed costs to recover / contribution per pack",
            "packs sold = min(demand, produced); surplus cleared at 50% of making cost",
            "contribution = revenue - variable costs; operating profit = contribution - fixed costs",
            "net profit = operating profit - 3% x overdraft",
            "receivables = 15% x sales; payables = 20% x production cost",
            "cash from operations = net profit - change in receivables + change in payables",
            "CLV = contribution per customer x (1 - churn) / (churn + 0.02)",
            "round score = w x profit percentile + (1 - w) x share percentile"])]},
    {"id": "worked", "title": "13. Worked example: from design to profit", "items": [
        E("A made-up example, step by step", [
            "Numbers here are illustrations only. The real numbers are in your reports.",
            "1. You buy the preference survey and learn that towns want quality about 7 and 150 g of tea, and large villages want quality about 5.5 and 100 g.",
            "2. You design tea at quality 6.5 and localisation 5 as a compromise, and set a 150 g pack for towns and a 100 g pack for large villages.",
            "3. The price study says price per 100 g at quality 5 is Rs 15 in towns, extra per quality point Rs 1.6, packaging Rs 1.2. Fair price of the 150 g town pack at quality 6.5 = 1.5 x (15 + 1.6 x 1.5) + 1.2 = Rs 27.",
            "4. The cost sheet says making cost per 100 g at quality 6.5 is Rs 9. Making cost of 150 g = 1.5 x 9 x (1 + 0.02 x 5) + 0.8 = Rs 15.7. Delivery about Rs 1.6. Contribution at Rs 25 = 25 - 15.7 - 1.6 = Rs 7.7 (31%).",
            "5. You choose Rs 25: a round price, slightly below fair. If you expect to sell 5,000 packs, contribution is Rs 38,500. Fixed costs of that pack: Rs 6,000 listing plus a share of product upkeep and the Rs 60,000 for the town market. You check that the whole product and market cover their fixed costs.",
            "6. After the round you read the profit and loss account (contribution less fixed costs), the cash flow (cash lags profit) and the pack table (fit, acceptance, contribution per pack), and adjust."]),
    ]},
]


def all_text():
    """Flat searchable text for each entry (used by the page filter)."""
    return SECTIONS
