from memory import LongTermMemory, WorkingMemory
from models import UserProfile
from policy import (
    ALLOWED_FIELDS,
    contains_sensitive_data,
    check_team_access,
    validate_for_storage,
    validate_nested_value,
)
from llm import (
    parse_retrieval_intent,
    extract_memory_fields,
    build_system_prompt,
    generate_response,
)


class Agent:
    """
    Workplace assistant agent. Owns working memory, uses long-term memory
    and LLM as capabilities. All policy decisions are deterministic.
    """

    def __init__(self, profile: UserProfile, ltm: LongTermMemory):
        self.profile = profile
        self.ltm = ltm
        self.memory = WorkingMemory(profile.email)

    def handle(self, message: str) -> str:
        """Process a user message using the custom agent."""

        if contains_sensitive_data(message):
            print("POLICY: Sensitive data in message — blocked, no trace stored")
            return (
                "Your message appears to contain sensitive information. "
                "I cannot process or store it."
            )

        if self._may_contain_storable_fact(message):
            stored = self._extract_and_store(message)
        else:
            stored = {}

        request = self._parse_message(message)
        if request["type"] == "retrieval":
            outcome = self._retrieve(request)
        else:
            outcome = {"status": "success", "context": self._baseline_context()}
        if stored and outcome.get("context"):
            outcome["context"]["stored"] = stored

        return self._respond(message, request, outcome)

    def end_session(self):
        """Discard working memory at session end."""
        self.memory.clear()

    def _parse_message(self, message: str) -> dict:
        """
        Parse a user message into a structured request.
        Returns: {"type": "retrieval"|"statement", "target": ..., "fields": [...]}
        """
        intent = parse_retrieval_intent(message)
        target = intent.get("target")
        fields = intent.get("fields", [])

        if target:
            if not fields:
                fields = ["role", "team", "preferences", "work_constraints"]
            return {"type": "retrieval", "target": target, "fields": fields}
        return {"type": "statement", "target": None, "fields": []}

    def _extract_and_store(self, message: str) -> dict:
        """Use LLM to extract facts, validate via policy, persist to LTM."""
        extracted = extract_memory_fields(message)
        stored = {}
        for field, value in extracted.items():
            if field in ("preferences", "work_constraints") and isinstance(value, dict):
                if self._validate_nested(field, value):
                    self.ltm.update(self.profile.email, field, value)
                    stored[field] = value
            elif field in ALLOWED_FIELDS:
                ok, reason = validate_for_storage(field, str(value))
                if ok:
                    self.ltm.update(self.profile.email, field, value)
                    stored[field] = value
                else:
                    print(f"POLICY: Rejected '{field}': {reason}")
        return stored

    def _validate_nested(self, field: str, value: dict) -> bool:
        """Validate keys and values inside preferences/work_constraints.
        Sub-keys are open-ended, so only sensitivity, stability, and work-relevance are checked.
        """
        for sub_key, sub_val in value.items():
            ok, reason = validate_nested_value(sub_key, str(sub_val))
            if not ok:
                print(f"POLICY: Rejected '{field}.{sub_key}': {reason}")
                return False
        return True

    def _retrieve(self, request: dict) -> dict:
        """
        Fetch requested profile data. Returns an outcome dict:
        {"status": "success"|"not_found"|"access_denied", "context": ..., "reason": ...}
        """
        target = request["target"]
        fields = request["fields"]

        if target == "self":
            return self._retrieve_self(fields)
        elif target == "all_teammates":
            return self._retrieve_team(fields)
        else:
            return self._retrieve_person(target, fields)

    def _retrieve_self(self, fields: list) -> dict:
        context = {"name": self.profile.name}
        context.update(self._pick_fields(self.profile, fields))
        print(f"LTM: Self-query for {fields}")
        return {"status": "success", "context": context}

    def _retrieve_team(self, fields: list) -> dict:
        """Retrieve requested fields for all team members, here we also include the user."""
        members = self.ltm.get_team_members(self.profile.team)
        if not members:
            return {"status": "success", "context": {
                "name": self.profile.name,
                "note": "No team members found.",
            }}
        team_data = []
        for member in members:
            entry = {"name": member.name}
            entry.update(self._pick_fields(member, fields))
            team_data.append(entry)
            label = "own" if member.email == self.profile.email else "teammate"
            print(f"LTM: Team query — {label} {member.name}, fields {fields}")
        return {"status": "success", "context": {
            "name": self.profile.name,
            "team_members": team_data,
        }}

    def _retrieve_person(self, name: str, fields: list) -> dict:
        source = self.ltm.find_by_name(name)
        if source is None:
            print(f"LTM: No user found with name '{name}'")
            return {
                "status": "not_found",
                "context": None,
                "reason": f"No person named '{name}' found in the system.",
            }

        allowed, reason = check_team_access(self.profile, source)
        if not allowed:
            print(f"POLICY: Cross-team access blocked: {reason}")
            return {"status": "access_denied", "context": None, "reason": reason}

        context = {"name": self.profile.name, "teammate_name": source.name}
        context.update(self._pick_fields(source, fields, prefix="teammate_"))
        print(f"LTM: Retrieved {fields} for {source.name}")
        return {"status": "success", "context": context}

    def _respond(self, message: str, request: dict, outcome: dict) -> str:
        """Generate the final reply and update working memory."""
        status = outcome.get("status", "success")
        self.memory.add_turn("user", message)

        if status == "access_denied":
            denial = f"I'm sorry, I can't share that information. {outcome['reason']}"
            self.memory.add_turn("assistant", denial)
            return denial

        if status == "not_found":
            reply = outcome["reason"]
            self.memory.add_turn("assistant", reply)
            return reply

        if request["type"] == "retrieval":
            self.memory.set_request({
                "intent": "retrieve",
                "target": request["target"],
                "fields": request["fields"],
            })
        else:
            self.memory.set_request(None)

        is_retrieval = request["type"] == "retrieval"
        system_prompt = build_system_prompt(
            self.profile.name, outcome["context"], is_retrieval=is_retrieval
        )
        response = generate_response(system_prompt, self.memory.get_context())

        self.memory.add_turn("assistant", response)
        return response

    @staticmethod
    def _may_contain_storable_fact(message: str) -> bool:
        """Skip LLM extraction for short or question-only messages."""
        msg = message.strip()
        if len(msg.split()) < 3:
            return False
        if msg.endswith("?") and not any(kw in msg.lower() for kw in (
            "i use", "i prefer", "my ", "i'm ", "i am ", "i can't", "i cannot",
        )):
            return False
        return True

    # needed for the agent to always have some context on who it is talking to
    # even if the working memory after let's say, 20 turns, has no trace of info regarding the user
    def _baseline_context(self) -> dict:
        """Minimal context for non-retrieval turns."""
        return {
            "name": self.profile.name,
            "role": self.profile.role,
            "team": self.profile.team,
        }

    @staticmethod
    def _pick_fields(profile: UserProfile, fields: list, prefix: str = "") -> dict:
        """Extract only the requested fields from a profile."""
        result = {}
        for field in fields:
            if "." in field:
                top, sub = field.split(".", 1)
                top_val = getattr(profile, top, {})
                if isinstance(top_val, dict) and sub in top_val:
                    key = f"{prefix}{top}" if prefix else top
                    if key not in result:
                        result[key] = {}
                    result[key][sub] = top_val[sub]
            else:
                val = getattr(profile, field, None)
                if val is not None:
                    result[f"{prefix}{field}" if prefix else field] = val
        return result
