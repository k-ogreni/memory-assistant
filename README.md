# Workplace Assistant: Dual-Layer Memory System

A conversational agent with two memory layers: working memory (session-only) for non-crucial information, and long-term memory (persistent) for stable facts about users. Since no scenario was specifically mentioned, to make the system more accessible, I chose a scenario on my own: a system that stores information for various teams, which you can query or add details about yourself to.

## Quick Start

```bash
# install the reqs
pip install -r requirements.txt
# run the app
python main.py
# run the demo with the sample convo
python demo.py
```

Requires: Ollama running with `ollama pull llama3.2`

## Approach: Two Memory Layers

### Working Memory (Session-Only)
- **Stored in**: Python dataclass (in-memory for the session)
- **Contains**: conversation history (last 8 turns) + current task state (`current_request` in my code, constitutes the structured details of the current retrieval request)
- **Cleared**: at session end
- **Why**: gives the LLM recent context without over-storing facts long-term storage

### Long-Term Memory (Persistent)
- **Stored in**: `data/users.json` on disk
- **Contains**: user profiles with allowlisted fields only
- **Persists**: across sessions
- **Why**: remembers stable, crucial facts like preferences, roles, constraints

The agent processes each message: **gate (block sensitive data) → extract & store stable facts → understand intent → retrieve if needed → respond**.

## Key Decisions

1. **Allowlist-based storage**: Only `email`, `name`, `role`, and `team` can be stored as core fields. `preferences` and `work_constraints` are flexible nested objects (e.g., editor, language, timezone, availability). Everything else is ignored or discarded.

2. **Four validation rules** (all must pass before storing):
   - **Allowlist check**: field is in the approved list
   - **Sensitivity check**: value has no passwords, tokens, SSNs
   - **Stability check**: value is not temporary ("debugging X today" is temporary; "I use Python" is stable)
   - **Work-relevance check**: value is work-related (no hobbies, personal life)

3. **Deterministic policy enforcement**: Python code validates and enforces all rules. The LLM extracts *candidate* facts, as I call them here, which means that it does not decide that they get stored, just presents them as options; the logic after decides what actually gets stored. This prevents the LLM from accidentally leaking or over-storing data.

4. **Team-based access control**: Users can only query teammates on the same team. Cross-team requests are blocked before any data reaches the LLM. This is done in order to show an aspect of privacy/sensitivity (though these are also something that is handled through the various allowlists, but I wanted to show another aspect of where these two could show up and how to handle it - in cases of partitioning).

5. **Context isolation**: The LLM only sees the *relevant subset* of memory for each query. A "What's my editor?" query shows only `preferences.editor`, not the full profile.

6. **Custom Agent**: No agent framework was used but a "custom", minimalistic agent was created to orchestrate the flow as it felt more natural for this task instead of using the former, since I didn't have to utilize anything from there to make this work the way I envisioned it.

## Privacy & Sensitivity Boundaries

**Sensitive data** (like passwords, api keys, etc.): Blocked immediately,not stored anywhere, nor sent to the LLM.

**Cross-team queries**: Access check runs first and the query is denied before any data is fetched.

**Temporary information** (such as: "I'm debugging X today"): Extracted but rejected for storage; it stays in working memory conversation only.

**Over-sharing**: The LLM fetches only the necessary fields related to the question; this avoids leakage from the system.

## Memory Extraction Rule

**Storage happens only on non-retrieval turns** (so, only what consists of a statement, not a questions). Each extracted fact is validated against all four rules; if any rule fails, the fact is rejected.

## Retrieval Strategy

**On session start**: User provides email → profile loaded from JSON into memory (or created if unavailable). Available for queries within this session.

**On explicit queries**: User asks a question → intent parsed → if retrieval is needed, the relevant fields are fetched and injected into the LLM prompt only. Working memory (conversation history) is available to the LLM for context on future queries.

**Access control**: Before retrieving a teammate's data, `check_team_access()` runs. If teams don't match, query is denied.

## Architecture: Agent-Centered Design

The `Agent` class is the orchestrator:
- Owns `WorkingMemory` (session state)
- References `LongTermMemory` (persistent store)
- Uses LLM as a capability for extraction, intent parsing, and response generation
- Enforces all policy deterministically through pure Python logic

Each turn follows: **sense (parse intent) → decide (what to do) → act (store/retrieve) → respond (generate reply and update history)**.

## File Structure

**agent.py**: Agent orchestrator that runs gate → extract → understand → retrieve → respond for each message.

**policy.py**: Allowlist definitions, validation rules (sensitivity, stability, work-relevance), and team access control.

**memory.py**: LongTermMemory (in a JSON file) and WorkingMemory (session-only conversation history).

**llm.py**: Ollama local LLM model integration for memory extraction, intent parsing, and response generation.

**models.py**: UserProfile and WorkingState dataclasses.

**main.py**: Conversation loop.

**demo.py**: Scripted 12-turn demonstration to quickly see the systems capabilities.

**data/users.json**: Persistent user store with seed profiles.

## Tradeoffs

- **Allowlist rigidity vs. flexibility**: Locked to a fixed set of fields. Tradeoff: prevents accidental storage of unvetted data types, but requires updating policy.py if new fields are needed.
- **4 validation rules**: Slightly expensive (4 checks per fact), but catches edge cases and prevents subtle leaks.
- **Small working memory window** (8 turns): Reduces context for the LLM but stays within llama3.2's limits. Adjustable via `.env`.
- **No framework**: Built from scratch without LangChain or similar. Tradeoff: simpler to understand, but more code to maintain.

## Other notes
- I decided to have logs to show LTM vs WM through the conversation to ensure that those were being utilized correctly. The logs are intentionally left there, not forgotten.
- The final decision for what gets stored or dropped from the candidate options lies within the deterministic Python logic. I chose to do that, because as we are aware LLMs can hallucinate quite often, especially in smaller, lightweight models such as llama3.2:8b that I am using, and as such, it is best to have this guard so you can ensure anything that goes in a DB is safe.
- While I have checks for specific fields, I haven't added rigid allowlist checks for the nested items inside working constraints or preferences, simply to make this more flexible, since logically speaking, users can have constraints or preferences that I cannot account for, whereas the rest of the details will follow the same pattern and can thus have the same key name.
- Because as I mentioned earlier I was using a lightweight model that isn't super good, I focused a lot on making the prompt exhaustive so that it would give me proper answers. I am sure there may be cases where it goes off-script and may hallucinate, but I tried to guide it properly through the questions that I thought of asking and ensuring that, for different ways of expressing things as a user, it would still give me a proper response. It may not have been the main idea behind the system I needed to build, but I wanted to make it robust to a certain degree to verify that it worked fine.
- I have not done much of error handling except for what I felt pertained the most to good results during the conversation so that responses made sense. Future improvements would definitely include better error handling, e.g., checking if email follows a specific format before storing it and prompting the user to resend the email if not, or how I have all users' emails ending in @company.com & no checks if they have the same name to also check the email to tell which user it is, and so on.
- I tried to not go overboard and make this simple. The prompts are probably the most "complicated" thing since I needed to very thoroughly work with them and make the prompt include an exhaustive list of instructions to avoid specific errors I got when testing the app, to have better answers when conversing with the assistant, but hopefully that is okay given the model constraint mentioned above. Another future improvement would be to focus more on the prompt and make it shorter but better at identifying different cases and still responding well to them (or using prompting frameworks to help with that). I also chose a JSON file as storage instead of a DB so results could be seen very easily without having to set up anything else.