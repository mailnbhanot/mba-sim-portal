"""What a game must provide. The portal (logins, tournaments, teams, rounds, events,
leaderboard, export) is shared; a game only supplies its own rules and screens."""


class Game:
    key = ""             # short id stored with each tournament, e.g. "rural_marketing"
    title = ""
    course_code = ""
    summary = ""
    total_rounds = 10
    implemented_rounds = set()   # round numbers that can be played so far
    events = {}                  # {key: {"label", "desc", "suits", ...game specific effects}}

    # ---- market and rules ----
    def tournament_params(self, seed):
        """True hidden parameters for one tournament (same for everyone in it)."""
        return {}

    def combine_events(self, keys):
        """Turn the active event keys into a modifiers object for run_round."""
        return {}

    def default_decision(self, round_no):
        """Decision used when a student or team submits nothing. Should be a bad one."""
        raise NotImplementedError

    def unsubmitted_decision(self, saved, round_no):
        """Decision applied to a non-submitter. `saved` is whatever they stored (e.g. purchases)."""
        return self.default_decision(round_no)

    def parse_form(self, form, round_no, saved):
        """Validate the submitted HTML form and return a clean decision dict."""
        raise NotImplementedError

    def run_round(self, round_no, players, tparams, mods):
        """players: [{"id": participant_id, "decision": {...}}] for ONE market group.
        Return {participant_id: result_dict}. Results must be JSON-serialisable and contain
        result["totals"]["profit"], ["group_rank"] and ["group_size"]."""
        raise NotImplementedError

    def debrief(self, result, round_no, submitted):
        """List of short concept notes shown to the student after the round."""
        return []

    def reflection_question(self, round_no):
        return ""

    # ---- screens ----
    def form_template(self, round_no):
        raise NotImplementedError

    def results_template(self, round_no):
        raise NotImplementedError

    def side_context(self, t, participant, decision, round_no, view_round, is_open):
        """Extra data for the side panels (statements, libraries). Games may override."""
        return {}

    def form_context(self, t, participant, decision, round_no):
        """Extra variables for the decision screen."""
        return {}

    def template_globals(self):
        """Constants the game's templates need."""
        return {}

    def handle_action(self, name, form, t, participant, data, round_no):
        """Game-specific buttons on the decision screen (e.g. buying a report).
        Return (new_data_or_None, message, category)."""
        return None, "Unknown action.", "error"
