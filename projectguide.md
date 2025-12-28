# MCP State Machine Host — Project Guide

## 1. What We Are Building

A **State Machine Host** that runs multiplayer, adversarial, turn-based games (starting with Chess and Rock-Paper-Scissors).

This is not a game server. It is a **coordination engine** that:

- Enforces rules via template-driven finite state machines
- Binds identity to actions via bearer token authentication
- Persists authoritative state in SQLite
- Exposes everything via a clean REST API (MCP adapter comes later)

---

## 2. Core Principles (Non-Negotiable)

| Principle | Meaning |
|-----------|---------|
| Server is the only source of truth | Agents cannot lie about state |
| Identity is enforced | Every action is bound to a verified agent_id |
| State transitions are deterministic | Same state + same action = same result |
| Templates are finite state machines | No arbitrary code execution |
| Logs are immutable | Actions are append-only receipts |
| Agents cannot act out of turn | Turn order is server-enforced |

---

## 3. Tech Stack

| Component | Choice | Rationale |
|-----------|--------|-----------|
| Web framework | FastAPI | Async-native, Pydantic validation, auto OpenAPI |
| Validation | Pydantic | Request/response schemas, catches bad input at boundary |
| Database | SQLite + aiosqlite | Simple, async, swappable to Postgres later |
| Chess logic | python-chess | Industry standard |
| Testing | pytest + pytest-asyncio + httpx | Async test support |

### requirements.txt

```
fastapi
uvicorn[standard]
pydantic
aiosqlite
python-chess
pytest
pytest-asyncio
httpx
```

---

## 4. Directory Structure

```
/engine
  ├── db.py              # SQLite connection, transactions, queries
  ├── auth.py            # token → agent_id resolution
  ├── sessions.py        # session lifecycle & participant management
  ├── templates/
  │     ├── base.py      # StateMachine interface
  │     ├── registry.py  # template_id → class mapping
  │     ├── chess.py     # chess.v1 implementation
  │     └── rps.py       # rps.v1 implementation
  └── errors.py          # error codes and exceptions

/api
  ├── main.py            # FastAPI app, lifespan, middleware
  ├── dependencies.py    # Depends() for auth, db
  ├── schemas.py         # Pydantic request/response models
  └── routes/
        ├── health.py
        ├── agents.py
        ├── sessions.py
        └── actions.py

/tests
  ├── conftest.py        # fixtures (test client, test db)
  ├── test_health.py
  ├── test_auth.py
  ├── test_agents.py
  ├── test_sessions.py
  ├── test_chess.py
  ├── test_rps.py
  └── test_invariants.py
```

---

## 5. Database Schema

```sql
-- Agents: identity + auth token
CREATE TABLE agents (
    agent_id TEXT PRIMARY KEY,
    token TEXT UNIQUE NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Sessions: game instances
CREATE TABLE sessions (
    session_id TEXT PRIMARY KEY,
    template TEXT NOT NULL,           -- e.g., "chess.v1", "rps.v1"
    state TEXT NOT NULL,              -- JSON blob (canonical state)
    status TEXT NOT NULL DEFAULT 'active',  -- 'active' | 'completed'
    tick INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Participants: binds agents to sessions with roles
CREATE TABLE participants (
    session_id TEXT NOT NULL,
    agent_id TEXT NOT NULL,
    role TEXT NOT NULL,               -- e.g., "white", "black", "player_1"
    PRIMARY KEY (session_id, agent_id),
    FOREIGN KEY (session_id) REFERENCES sessions(session_id),
    FOREIGN KEY (agent_id) REFERENCES agents(agent_id)
);

-- Actions: immutable log of all moves
CREATE TABLE actions (
    action_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    agent_id TEXT NOT NULL,
    role TEXT NOT NULL,
    action TEXT NOT NULL,             -- JSON blob
    tick INTEGER NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (session_id) REFERENCES sessions(session_id),
    FOREIGN KEY (agent_id) REFERENCES agents(agent_id)
);
```

---

## 6. State Machine Interface

All templates must implement this interface:

```python
from abc import ABC, abstractmethod

class StateMachine(ABC):
    """Base interface for all game templates."""
    
    @property
    @abstractmethod
    def template_id(self) -> str:
        """Unique identifier, e.g., 'chess.v1'"""
        pass
    
    @property
    @abstractmethod
    def roles(self) -> list[str]:
        """Required roles, e.g., ['white', 'black']"""
        pass
    
    @abstractmethod
    def initial_state(self) -> dict:
        """Return the starting state."""
        pass
    
    @abstractmethod
    def legal_actions(self, state: dict, role: str) -> list[str]:
        """Return list of legal actions for this role in this state."""
        pass
    
    @abstractmethod
    def apply_action(self, state: dict, role: str, action: str) -> dict:
        """Apply action and return new state. Raises if illegal."""
        pass
    
    @abstractmethod
    def is_terminal(self, state: dict) -> bool:
        """Return True if no more actions are possible."""
        pass
    
    @abstractmethod
    def view_state(self, state: dict, role: str) -> dict:
        """Return state as visible to this role (for hidden information games)."""
        pass
```

### Rules for Templates

- **No side effects** — pure functions only
- **Deterministic** — same input = same output
- **No I/O** — no network, no disk, no randomness from outside

---

## 7. API Endpoints

### Authentication

All endpoints except `POST /agents` and `GET /health` require:

```
Authorization: Bearer <token>
```

### Error Response Format

```json
{
  "error": {
    "code": "INVALID_ACTION",
    "message": "Not your turn"
  }
}
```

Standard error codes:

| Code | HTTP Status | Meaning |
|------|-------------|---------|
| `UNAUTHORIZED` | 401 | Missing or invalid token |
| `FORBIDDEN` | 403 | Valid token but not permitted |
| `NOT_FOUND` | 404 | Resource doesn't exist |
| `INVALID_ACTION` | 400 | Action not legal in current state |
| `CONFLICT` | 409 | Tick mismatch (optimistic locking) |
| `INVALID_REQUEST` | 400 | Malformed request body |
| `ALREADY_ACTED` | 400 | Already submitted action this phase (RPS) |

---

### Endpoints

#### Health Check

```
GET /health
→ 200 { "status": "ok" }
```

No auth required.

---

#### Agent Registration

```
POST /agents
→ 201 { "agent_id": "...", "token": "..." }
```

No auth required. Creates a new agent with a random token.

---

#### Session Creation

```
POST /sessions
Authorization: Bearer <token>
{
  "template": "chess.v1",
  "participants": {
    "white": "<agent_id>",
    "black": "<agent_id>"
  }
}
→ 201 { "session_id": "...", "template": "...", "status": "active" }
```

Rules:
- Caller must be one of the participants
- All roles must be filled
- All agent_ids must exist

---

#### List Sessions

```
GET /sessions?agent_id=<agent_id>
Authorization: Bearer <token>
→ 200 { "sessions": [...] }
```

Returns sessions where the querying agent is a participant.

---

#### Get Session State

```
GET /sessions/{session_id}/state
Authorization: Bearer <token>
→ 200 {
  "session_id": "...",
  "template": "...",
  "status": "active",
  "tick": 5,
  "state": { ... },           // Filtered view for this agent
  "your_role": "white",
  "legal_actions": ["e2e4", "d2d4", ...]
}
```

Rules:
- Only participants can read
- State is filtered through `view_state()` (hides opponent info in RPS)

---

#### Submit Action

```
POST /sessions/{session_id}/actions
Authorization: Bearer <token>
{
  "action": "e2e4",
  "expected_tick": 0          // Optional, required for chess
}
→ 200 {
  "tick": 1,
  "state": { ... },
  "status": "active"
}
```

Rules:
- Agent must be a participant
- Action must be in `legal_actions` for their role
- For sequential games (chess): `expected_tick` must match current tick
- For simultaneous games (RPS): submission tracked per-agent, no tick check

---

#### Get Action Log

```
GET /sessions/{session_id}/log
Authorization: Bearer <token>
→ 200 {
  "actions": [
    { "tick": 0, "role": "white", "action": "e2e4", "agent_id": "...", "created_at": "..." },
    { "tick": 1, "role": "black", "action": "e7e5", "agent_id": "...", "created_at": "..." }
  ]
}
```

Rules:
- Only participants can read
- Log is append-only and immutable

---

## 8. Template Specifications

### chess.v1

**Roles:** `white`, `black`

**State:**
```json
{
  "fen": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
  "turn": "white",
  "outcome": null
}
```

**Actions:** UCI notation (e.g., `e2e4`, `e7e8q` for promotion)

**Turn order:** Strictly alternating. Only the role matching `turn` may act.

**Terminal:** Checkmate, stalemate, or draw.

**Tick:** Increments by 1 after each move. `expected_tick` is required.

---

### rps.v1

**Roles:** `player_1`, `player_2`

**State:**
```json
{
  "phase": "commit",
  "choices": {
    "player_1": null,
    "player_2": null  
  },
  "result": null
}
```

**Actions:** `rock`, `paper`, or `scissors`

**Flow:**
1. Both players submit their choice (order doesn't matter)
2. Once both have submitted, `phase` becomes `"reveal"`, choices are visible, and `result` is computed

**Hidden information:** 
- During `commit` phase, `view_state()` hides opponent's choice
- After both submit, full state is visible

**Terminal:** When `result` is set (`player_1_wins`, `player_2_wins`, or `draw`)

**Tick:** 
- Tick 0: Neither has submitted
- Tick 1: One has submitted
- Tick 2: Both submitted, result computed

**No expected_tick required** — server tracks who has submitted and rejects duplicates.

---

## 9. Invariants (Must Always Hold)

These are tested explicitly in `test_invariants.py`:

1. **No action without auth** — 401 for missing/invalid token
2. **No action by non-participant** — 403 for valid token but wrong session
3. **No illegal action** — 400 for actions not in `legal_actions`
4. **No out-of-turn action** — 400 for wrong role in chess
5. **No double action** — 409 (chess tick mismatch) or 400 (RPS already acted)
6. **No action after terminal** — 400 when `is_terminal` is true
7. **No state mutation by read** — GET endpoints never change state
8. **No log mutation** — action log is append-only

---

## 10. What Success Looks Like

- Two Claude agents can play a complete chess game
- Two Claude agents can play Rock-Paper-Scissors
- All invariants hold under adversarial testing
- No ambiguity about game state
- Full audit trail of all actions

---

## 11. Future Work (Not MVP)

- MCP adapter (wrap REST as MCP tools/resources)
- WebSocket subscriptions for real-time updates
- Additional templates (Tic-Tac-Toe, Poker)
- Rate limiting
- Session expiration
- Spectator mode
