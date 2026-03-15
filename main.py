from memory import LongTermMemory
from models import UserProfile
from agent import Agent


def onboard_new_user(email: str, ltm: LongTermMemory) -> UserProfile:
    """Collect info from a new user and create their profile."""
    print("\nWelcome! I don't have you on file yet. Let me collect some info.\n")
    name = input("  Your full name: ").strip()
    role = input("  Your job title/role: ").strip()
    team = input("  Your team name: ").strip()
    profile = UserProfile(email=email, name=name, role=role, team=team)
    ltm.create(profile)
    return profile


def main():
    print("=" * 60)
    print("  Workplace Assistant — Conversational Agent with Memory")
    print("=" * 60)
    print()

    ltm = LongTermMemory()
    print()

    email = input("Enter your email to start: ").strip().lower()
    if not email:
        print("No email provided. Exiting.")
        return

    profile = ltm.lookup(email)
    if profile is None:
        profile = onboard_new_user(email, ltm)
    else:
        print(f"\nWelcome back, {profile.name}!\n")

    agent = Agent(profile, ltm)
    print()
    print("Type 'quit' to end the session.\n")

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not user_input:
            continue
        if user_input.lower() in ("quit", "exit"):
            break

        print()
        response = agent.handle(user_input)
        print(f"\nAssistant: {response}\n")

    print()
    agent.end_session()
    print("Session ended. Long-term memory persisted. Working memory discarded.")


if __name__ == "__main__":
    main()
