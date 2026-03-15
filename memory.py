import json
import os
from dataclasses import asdict
from typing import Optional

from dotenv import load_dotenv

from models import UserProfile, WorkingState

load_dotenv()

MAX_HISTORY_TURNS = int(os.getenv("MAX_HISTORY_TURNS", "8"))


class LongTermMemory:
    """JSON-backed persistent memory store, keyed by email."""

    def __init__(self, filepath: str = None):
        filepath = filepath or os.getenv("DATA_PATH", "data/users.json")
        self.filepath = filepath
        self._store: dict[str, UserProfile] = {}
        self._load()

    def _load(self) -> None:
        if not os.path.exists(self.filepath):
            self._store = {}
            return
        with open(self.filepath, "r") as f:
            raw = json.load(f)
        for email, data in raw.items():
            self._store[email] = UserProfile(**data)
        print(f"LTR: Loaded {len(self._store)} user(s) from {self.filepath}")

    def _save(self) -> None:
        os.makedirs(os.path.dirname(self.filepath), exist_ok=True)
        with open(self.filepath, "w") as f:
            json.dump(
                {email: asdict(profile) for email, profile in self._store.items()},
                f,
                indent=4,
            )

    def lookup(self, email: str) -> Optional[UserProfile]:
        profile = self._store.get(email)
        if profile:
            print(f"LTR: Retrieved profile for {email}")
        else:
            print(f"LTR: No profile found for {email}")
        return profile

    def create(self, profile: UserProfile) -> None:
        self._store[profile.email] = profile
        self._save()
        print(f"LTR: Created new profile for {profile.email}")

    def update(self, email: str, field: str, value) -> None:
        """Update a single field on an existing profile. Caller is responsible for validation."""
        profile = self._store.get(email)
        if profile is None:
            print(f"LTR: Cannot update - no profile for {email}")
            return

        if field in ("preferences", "work_constraints"):
            current = getattr(profile, field)
            if isinstance(value, dict):
                current.update(value)
            else:
                print(f"LTR: Expected dict for '{field}', got {type(value).__name__}")
                return
        elif hasattr(profile, field):
            setattr(profile, field, value)
        else:
            print(f"LTR: Unknown field '{field}'")
            return

        self._save()
        print(f"LTR: Updated {field} for {email}")

    def get_team_members(self, team: str) -> list[UserProfile]:
        return [p for p in self._store.values() if p.team == team]

    def find_by_name(self, name: str) -> Optional[UserProfile]:
        """Find a user by partial name match (case-insensitive)."""
        name_lower = name.lower()
        for profile in self._store.values():
            if name_lower in profile.name.lower():
                return profile
        return None


class WorkingMemory:
    """In-process memory that exists only for the current session."""

    def __init__(self, user_email: str):
        self.state = WorkingState(user_email=user_email)
        print(f"WORKING MEMORY: Initialized new session for {user_email}")

    def add_turn(self, role: str, content: str) -> None:
        self.state.conversation_history.append({"role": role, "content": content})
        # if the turns will get longer than 8, which is the value given for MAX_HISTORY_TURNS
        # i trim the history so that it keeps the last 8
        if len(self.state.conversation_history) > MAX_HISTORY_TURNS:
            self.state.conversation_history = self.state.conversation_history[-MAX_HISTORY_TURNS:]
        print(
            f"WORKING MEMORY: Added {role} turn "
            f"(history: {len(self.state.conversation_history)} turns)"
        )

    def set_request(self, request: Optional[dict]) -> None:
        self.state.current_request = request
        if request:
            print(f"WORKING MEMORY: Set current request: {request}")
        else:
            print("WORKING MEMORY: Cleared current request")

    def get_context(self) -> list[dict]:
        return list(self.state.conversation_history)

    def get_request(self) -> Optional[dict]:
        return self.state.current_request

    def clear(self) -> None:
        self.state = WorkingState(user_email=self.state.user_email)
        print("WORKING MEMORY: Session cleared - all working memory discarded")
