# MBA Simulation Portal

One portal, many games. The teacher logs in, uploads students, picks a **game**, chooses
**individual or team play**, enrols students, and runs the rounds. Students log in and only see
tournaments they are enrolled in.

**Games built so far:** MKTM679 Emerging Dimensions of Marketing (all 10 rounds).
New games plug into the same portal (see "Adding a game" below).

## IMPORTANT if you ran the earlier version
The database layout changed. Delete the old file before starting: `sim.db` (or `instance\sim.db`).

## Run it on your computer (Windows PowerShell)

    pip install -r requirements.txt
    $env:ADMIN_PASSWORD="mypass123"
    python -m flask --app app run

Open http://127.0.0.1:5000 and log in as `admin` / `mypass123`. Keep the window open.
(Mac: `ADMIN_PASSWORD=mypass123 python3 -m flask --app app run --port 8000`.)
Run the tests with `python -m pytest`.

## Put it online for free
Two free accounts: **Supabase** (database) and **Render** (web hosting).
1. Supabase: create a project, copy Project Settings > Database > Connection string (URI), add your password.
2. GitHub: create a repository and upload this folder.
3. Render: New > Blueprint, pick the repository (it reads `render.yaml`). Enter `ADMIN_PASSWORD`
   and `DATABASE_URL` when asked. Render gives you the web address for students.
- Render's free service sleeps after 15 minutes idle (about 30 seconds to wake).
- Automatic rounds close on time only if something visits the site. Create a free job at cron-job.org that
  opens `https://YOUR-SITE.onrender.com/tick?key=YOUR_TICK_SECRET` every 5 minutes
  (TICK_SECRET is in Render > Environment).
- Supabase's free database pauses after a week idle. Open its dashboard to resume.


## How the MKTM679 game works
- **Portfolio.** Seven categories (toothpaste, tea, detergent, biscuits, hair oil, noodles, soap). Each student launches three in Round 1 and the choice is locked.
  Categories differ in size by segment, price level, margin and what shoppers want.
- **No bundles, no given prices.** Per product the student sets quality and localisation. Per product per market (town, large village,
  remote village) the student sets up to **two packs**: grams and price are blank and entirely theirs. From Round 2 they set the
  production quantity of each pack. Repeated categories are numbered (Soap 1, Soap 2, Soap 3) so prices stay distinguishable.
- **Gram packs vs price-point (LUP) packs.** Each pack is either type. Gram packs are judged on grams and fair price; LUP packs (Rs 5, 10, 20)
  are judged on the rupee price against the segment's usual ticket price and are far less sensitive to grams.
- **Round prices sell better** (multiples of 10, then 5, then whole rupees; awkward prices like 24.7 are penalised, twice as hard for LUP).
- **Fixed and variable costs.** Variable (production, delivery, offers) grows with sales. Fixed grows with what is launched: Rs 2 lakh
  overhead, Rs 40,000 per live product, Rs 6,000 per live pack, Rs 60,000 per market served, Rs 20,000 per localisation point. The P&L shows
  contribution, then operating profit. The decision form shows a live check of price against making cost once the cost sheet is bought.
- **Marketing is switched off** in Stage 1 (promotion, digital, advertising, experiential and their reports). One flag,
  `MARKETING_ENABLED` in `games/rural_marketing/params.py`, brings it back.
- **Concept corner.** A searchable handbook in the left menu: every rule, term, formula, worked example and an A to Z glossary
  (`games/rural_marketing/concepts.py`).
- **Consumers decide.** Each category and segment has a hidden ideal (quality, grams, localisation). A pack scoring below the acceptance
  threshold (fit about 45/100) is not bought, and the student still pays the costs.
- **Financial statements.** Opening position in Round 1 (Rs 50 lakh cash, everything else zero). From Round 2: profit and loss (this round and
  cumulative), balance sheet and cash flow. Retailers pay 15% of sales a quarter late and suppliers are paid 20% of production a quarter
  late, so cash differs from profit; a firm that runs out of cash gets a 3% a quarter overdraft.
- **Reports are built by the student.** About 45 reports. The student ticks the measures, categories, segments and accuracy level, and the price
  follows the selection. Every topic that is not your own private data also has a **free public version**: coarse, rounded, two spotlight
  categories, headline measures, identical for everyone. Bought reports are shown beside the public version.
- **Ranking = profit + market share.** Teacher sets the weight (default 60/40). Standings show cumulative profit, average share and score.
- **No decision = no sales.** Non-submitters designed no product, so they sell nothing and still pay the Rs 2 lakh overhead each round.
- **Events** can be added by the teacher at any round: festival, monsoon, competitor, fuel, privacy_law, platform_outage, ad_backlash.

## Using it
1. **Students**: upload a CSV with `name`, `roll_no` (becomes the username), `batch`. A credentials CSV
   downloads at once. Save it; passwords are not stored in readable form.
2. **New tournament**: choose the game, **Individual or Teams**, manual or automatic rounds,
   single market or industry groups.
3. **Enrol** by batch or by pasted usernames. For team tournaments you can also write
   `Team Alpha: user1, user2, user3` lines to place students in teams yourself; everyone else is put in
   random teams of the size you set when you press Start.
4. **Start.** During a round: watch who has submitted, trigger events, extend the deadline, or process early.
5. Students see results, their market table, the leaderboard and a reflection question. Download all results as CSV.

**Teams:** a team is one company with one shared decision and one shared result. Any member can submit;
the last submission counts.

**No decision = a loss.** A student or team that submits nothing gets the game's autopilot default,
which is deliberately loss-making (in MKTM679 Round 1: Rs 6 pouch in every segment, below unit cost).

## Adding a game (for the developer / for Claude)
1. Create `games/<your_game>/__init__.py` with a class that extends `games.base.Game`
   (rules: `default_decision`, `parse_form`, `run_round`, events, debrief, templates).
2. Put its screens in `templates/games/<your_game>/` (a decision form and a results page per round).
3. Register it: `register(YourGame())` at the bottom of its module, and add one import line in `games/__init__.py`.
4. Add tests next to `tests/test_game.py`. Logins, tournaments, teams, round control, events, leaderboard and
   export need no changes: they work for every game.

## Files
    games/base.py                  what a game must provide
    games/registry.py              list of games
    games/rural_marketing/         MKTM679 game: engine.py (maths) and __init__.py (rules)
    services.py                    tournament logic shared by all games
    app.py  models.py  templates/  the portal
    tests/                         automated tests
