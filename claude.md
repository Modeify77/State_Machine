# CLAUDE.md

Instructions for Claude Code when working on this project.

## Project Overview

This is an MCP State Machine Host — a coordination engine for multiplayer turn-based games. The server is the single source of truth. Agents authenticate via bearer tokens and submit actions through REST endpoints.

**Templates:** Chess (`chess.v1`) and Rock-Paper-Scissors (`rps.v1`)

## Tech Stack

- **Framework:** FastAPI (async)
- **Database:** SQLite via aiosqlite
- **Validation:** Pydantic
- **Chess logic:** python-chess
- **Testing:** pytest + pytest-asyncio + httpx

## Key Files

| File | Purpose |
|------|---------|
| `projectguide.md` | Architecture, principles, API contracts |
| `tasks.md` | Ordered task list with acceptance criteria |
| `api/main.py` | FastAPI app entry point |
| `engine/db.py` | Database layer |
| `engine/templates/base.py` | StateMachine interface |

## Task Execution Rules

**These are mandatory. Do not deviate.**

1. **One task at a time** — Complete the task fully before moving on
2. **Read the task** — Check `tasks.md` for exact deliverables and tests
3. **Write tests first** — Or alongside implementation, never after
4. **Run tests before committing** — All tests must pass
5. **Do not refactor unrelated code** — Stay focused on the task
6. **Do not invent abstractions** — Follow the spec exactly
7. **Commit with the specified message** — Use the exact message from the task
8. **If stuck, say so** — Do not guess or improvise

## Coding Standards

### Python

```python
# Use type hints everywhere
def get_agent_by_token(token: str) -> Agent | None:
    ...

# Async functions for all I/O
async def create_session(...) -> Session:
    ...

# Pydantic for request/response schemas
class CreateSessionRequest(BaseModel):
    template: str
    participants: dict[str, str]
```

### File Structure

```
# Routes go in api/routes/
# Each route file has one router

from fastapi import APIRouter
router = APIRouter()

@router.post("/sessions")
async def create_session(...):
    ...
```

### Database

```python
# Always use async context manager
async with get_db() as db:
    await db.execute(...)
    await db.commit()

# Never use raw SQL in route handlers — use db.py helpers
```

### Error Handling

```python
# Use custom exceptions from engine/errors.py
from engine.errors import UnauthorizedError, InvalidActionError

# Let FastAPI exception handlers convert to JSON
raise InvalidActionError("Not your turn")
```

### Testing

```python
# Use httpx AsyncClient
@pytest.fixture
async def client():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac

# Test both success and failure cases
async def test_valid_action(client, session, auth_headers):
    response = await client.post(...)
    assert response.status_code == 200

async def test_invalid_action_rejected(client, session, auth_headers):
    response = await client.post(...)
    assert response.status_code == 400
```

## State Machine Rules

Templates must be:

- **Pure** — No side effects
- **Deterministic** — Same input = same output
- **No I/O** — No network, disk, or external randomness

```python
# GOOD
def apply_action(self, state: dict, role: str, action: str) -> dict:
    new_state = copy.deepcopy(state)
    # modify new_state
    return new_state

# BAD — mutates input
def apply_action(self, state: dict, role: str, action: str) -> dict:
    state["turn"] = "black"  # NO! Mutating input
    return state
```

## Common Patterns

### Auth Dependency

```python
from api.dependencies import get_current_agent

@router.get("/sessions")
async def list_sessions(agent: Agent = Depends(get_current_agent)):
    ...
```

### Template Lookup

```python
from engine.templates.registry import get_template

template = get_template("chess.v1")
state = template.initial_state()
```

### Database Transaction

```python
async with get_db() as db:
    session = await db.get_session(session_id)
    new_state = template.apply_action(session.state, role, action)
    await db.update_session(session_id, new_state, tick=session.tick + 1)
    await db.log_action(session_id, agent_id, role, action, session.tick)
    await db.commit()
```

## What NOT To Do

| Don't | Why |
|-------|-----|
| Add logging infrastructure | Not in scope |
| Add rate limiting | Post-MVP |
| Add WebSocket support | Post-MVP |
| Create a CLI | Not in scope |
| Add Docker | Not in scope |
| Refactor for "cleanliness" | If it works and tests pass, it's done |
| Add type stubs for libraries | Unnecessary |
| Create helper utilities "for later" | YAGNI |

## Error Codes Reference

| Code | HTTP | When |
|------|------|------|
| `UNAUTHORIZED` | 401 | No token or invalid token |
| `FORBIDDEN` | 403 | Valid token, but not permitted |
| `NOT_FOUND` | 404 | Session/agent doesn't exist |
| `INVALID_REQUEST` | 400 | Malformed request body |
| `INVALID_ACTION` | 400 | Action not legal |
| `ALREADY_ACTED` | 400 | Already submitted this phase (RPS) |
| `CONFLICT` | 409 | Tick mismatch |

## Running the Project

```bash
# Install dependencies
pip install -r requirements.txt

# Run tests
pytest

# Run server
uvicorn api.main:app --reload
```

## Commit Format

Use the exact commit message from the task:

```bash
git add .
git commit -m "feat: session creation and participant binding"
```

## When Starting a New Task

1. Read the task in `tasks.md`
2. Create any new files needed
3. Write the tests (can be alongside implementation)
4. Implement until tests pass
5. Run full test suite: `pytest`
6. Commit with the specified message
7. Report completion

## Questions to Ask (Before Guessing)

- "The task says X but earlier code does Y — which should I follow?"
- "This test case isn't clear — what's the expected behavior?"
- "Should I fix this bug I found in unrelated code?"

When in doubt, ask. Do not improvise.
