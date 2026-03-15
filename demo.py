import json
import os
import shutil

from memory import LongTermMemory
from agent import Agent

# temp file
DEMO_DATA = "data/demo_users.json"
ORIGINAL_DATA = "data/users.json"


def separator(label: str = "") -> None:
    print()
    if label:
        print(f"{'-' * 20} {label} {'-' * 20}")
    else:
        print("-" * 60)
    print()


def run_demo():
    print("=" * 60)
    print("  DEMO: Dual-Layer Memory System (12 Turns)")
    print("  Using live Ollama LLM responses")
    print("=" * 60)

    shutil.copy(ORIGINAL_DATA, DEMO_DATA)

    # First fresh session
    separator("SESSION 1 - Alice logs in (existing user)")

    ltm = LongTermMemory(filepath=DEMO_DATA)
    email = "alice@company.com"
    profile = ltm.lookup(email)
    print(f"\nWelcome back, {profile.name}!\n")

    agent = Agent(profile, ltm)

    # Turn 1: Email lookup (already done above)
    separator("TURN 1 - Existing user identified via email")
    print(f"[Demo] User identified: {profile.name} ({profile.email})")
    print(f"[Demo] Team: {profile.team}, Role: {profile.role}")

    # Turn 2: Stable preference -> should be stored in LTM
    separator("TURN 2 - Stable preference (LTM write)")
    user_msg = "My primary programming language is TypeScript"
    print(f"User: {user_msg}\n")
    response = agent.handle(user_msg)
    print(f"\nAssistant: {response}")

    # Turn 3: Temporary task -> working memory only
    separator("TURN 3 - Temporary task (working memory only - will be used in later steps)")
    user_msg = "I'm debugging the checkout flow today"
    print(f"User: {user_msg}\n")
    response = agent.handle(user_msg)
    print(f"\nAssistant: {response}")

    # Turn 4: Retrieve stored preference from seed data
    separator("TURN 4 - Retrieve preference from LTM")
    user_msg = "What's my preferred editor?"
    print(f"User: {user_msg}\n")
    response = agent.handle(user_msg)
    print(f"\nAssistant: {response}")

    # Turn 5: Ask about current task -> working memory read
    separator("TURN 5 - Working memory read (recent conversation context)")
    user_msg = "What's my current task?"
    print(f"User: {user_msg}\n")
    response = agent.handle(user_msg)
    print(f"\nAssistant: {response}")

    # Turn 6: Cross-team query -> should be blocked
    separator("TURN 6 - Cross-team access (BLOCKED)")
    user_msg = "What team is Carol on?"
    print(f"User: {user_msg}\n")
    response = agent.handle(user_msg)
    print(f"\nAssistant: {response}")

    # Turn 7: Same-team query -> should be allowed
    separator("TURN 7 - Same-team access (ALLOWED)")
    user_msg = "What's Bob's role?"
    print(f"User: {user_msg}\n")
    response = agent.handle(user_msg)
    print(f"\nAssistant: {response}")

    # Turn 8: Sensitive data -> rejected
    separator("TURN 8 - Sensitive data (REJECTED)")
    user_msg = "My password is hunter2"
    print(f"User: {user_msg}\n")
    response = agent.handle(user_msg)
    print(f"\nAssistant: {response}")

    # Turn 9: Stable work constraint -> should be stored in LTM
    separator("TURN 9 - Stable work constraint (LTM write)")
    user_msg = "I can't do meetings before 10am"
    print(f"User: {user_msg}\n")
    response = agent.handle(user_msg)
    print(f"\nAssistant: {response}")

    # Turn 10: Ask for conversation summary -> working memory read
    separator("TURN 10 - Noise")
    user_msg = "I can eat a whole pizza by myself"
    print(f"User: {user_msg}\n")
    response = agent.handle(user_msg)
    print(f"\nAssistant: {response}")

    # Turn 11: Session end
    separator("TURN 11 - Session ends")
    agent.end_session()
    print("[Demo] Session 1 ended. Working memory discarded. Long-term memory persists.\n")

    print("[Demo] Current LTM state for Alice:")
    refreshed_profile = ltm.lookup(email)
    print(f"  Preferences: {json.dumps(refreshed_profile.preferences, indent=4)}")
    print(f"  Work constraints: {json.dumps(refreshed_profile.work_constraints, indent=4)}")

    # New session 
    separator("TURN 12 - New session, same user")

    ltm2 = LongTermMemory(filepath=DEMO_DATA)
    profile2 = ltm2.lookup(email)
    agent2 = Agent(profile2, ltm2)

    print(f"\n[Demo] Long-term memory PERSISTED: {profile2.name} found with updated preferences")
    print(f"  Preferences: {json.dumps(profile2.preferences, indent=4)}")
    print(f"  Work constraints: {json.dumps(profile2.work_constraints, indent=4)}")
    print(f"\n[Demo] Working memory EMPTY: current request = {agent2.memory.get_request()}")
    print(f"[Demo] Conversation history = {agent2.memory.get_context()}")

    agent2.end_session()
    os.remove(DEMO_DATA)

if __name__ == "__main__":
    run_demo()
