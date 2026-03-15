
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from models import UserProfile

# allowlist, includes information that should be stored in my json file
ALLOWED_FIELDS = {"email", "name", "role", "team", "preferences", "work_constraints"}

# words the system should drop immediately, the allowlist is the first line of defense
# but maybe it could pass as a preference or constraint
SENSITIVE_PATTERNS = [
    "password", "passwd", "pwd", "secret", "ssn", "social security",
    "credit card", "bank account", "salary", "compensation",
    "api_key", "api key", "token", "credential", "private key",
]

# these will disallow such things to be stored in ltm
UNSTABLE_PATTERNS = [
    "today", "right now", "currently working on", "this afternoon",
    "this morning", "this evening", "at the moment", "for now",
    "debugging", "fixing", "investigating", "looking into",
    "just finished", "about to", "later today", "tomorrow",
]

# other specific things to ignore since they can end up in preferences
NON_WORK_PATTERNS = [
    "hobby", "hobbies", "favorite food", "favourite food",
    "weekend plans", "vacation plans", "birthday",
    "pet", "family", "personal life", "dating",
]


def is_allowlisted(field_name: str) -> bool:
    return field_name.lower() in ALLOWED_FIELDS


def contains_sensitive_data(text: str) -> bool:
    lower = text.lower()
    return any(pattern in lower for pattern in SENSITIVE_PATTERNS)


def is_unstable(text: str) -> bool:
    lower = text.lower()
    return any(pattern in lower for pattern in UNSTABLE_PATTERNS)


def is_non_work_related(text: str) -> bool:
    lower = text.lower()
    return any(pattern in lower for pattern in NON_WORK_PATTERNS)


def validate_for_storage(field_name: str, value: str) -> tuple[bool, str]:
    """
    Check all four storage rules before persisting a fact to long-term memory.
    Returns (ok, reason).
    """
    if not is_allowlisted(field_name):
        return False, f"'{field_name}' is not in the allowlisted fields."
    if contains_sensitive_data(str(value)):
        return False, "Value contains sensitive information. Rejected."
    if is_unstable(str(value)):
        return False, "Value appears temporary or session-specific. Not stored in long-term memory."
    if is_non_work_related(str(value)):
        return False, "Value is not work-related. Not stored in long-term memory."
    return True, "OK"


def validate_nested_value(key: str, value: str) -> tuple[bool, str]:
    """Validate a sub-key or value inside preferences/work_constraints.
    No allowlist check — sub-keys are intentionally open-ended.
    """
    if contains_sensitive_data(key) or contains_sensitive_data(value):
        return False, "Contains sensitive information."
    if is_unstable(key) or is_unstable(value):
        return False, "Appears temporary or session-specific."
    if is_non_work_related(key) or is_non_work_related(value):
        return False, "Not work-related."
    return True, "OK"


def check_team_access(
    requester: "UserProfile",
    target: "UserProfile",
) -> tuple[bool, str]:
    """
    Check whether the requester is allowed to view the target user's info.
    Only same-team access is permitted.
    """
    if requester.team != target.team:
        return (
            False,
            f"Access denied: you ({requester.team}) cannot view info about "
            f"members outside your team. {target.name} is on {target.team}.",
        )
    return True, "OK"
