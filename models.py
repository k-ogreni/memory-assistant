from dataclasses import dataclass, field
from typing import Optional


@dataclass
class UserProfile:
    """Represents a user's long-term memory record (stored in the json file)."""
    email: str
    name: str
    role: str
    team: str
    preferences: dict = field(default_factory=dict)
    work_constraints: dict = field(default_factory=dict)


@dataclass
class WorkingState:
    """Represents in-session working memory."""
    user_email: str
    conversation_history: list = field(default_factory=list)
    current_request: Optional[dict] = None
