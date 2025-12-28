# MCP State Machine Host — Tasks

Execute these tasks in order. Complete one task fully before moving to the next.

---

## TASK 1 — Project Scaffold

**Goal:** Create a clean Python project with FastAPI, SQLite, and test scaffolding.

**Deliverables:**
- Git repo initialized with `.gitignore`
- `requirements.txt` with all dependencies
- `api/main.py` with FastAPI app and `/health` endpoint
- `tests/conftest.py` with async test client fixture
- `tests/test_health.py`

**Acceptance Tests:**
```python
def test_health_returns_ok():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
```

**Commit:** `chore: initial project scaffold with FastAPI`

---

## TASK 2 — Database Layer

**Goal:** Create SQLite schema and async database layer.

**Deliverables:**
- `engine/db.py` with:
  - `init_db()` — creates tables
  - `get_db()` — async context manager for connections
  - Query helpers for agents, sessions, participants, actions
- `schema.sql` file with table definitions
- Database initialization on app startup

**Acceptance Tests:**
```python
async def test_can_create_and_retrieve_agent():
    agent = await db.create_agent()
    retrieved = await db.get_agent_by_id(agent["agent_id"])
    assert retrieved["agent_id"] == agent["agent_id"]

async def test_can_create_session():
    session = await db.create_session("chess.v1", initial_state, participants)
    assert session["status"] == "active"
```

**Commit:** `feat: sqlite schema and async database layer`

---

## TASK 3 — Authentication Middleware

**Goal:** Bind every request to a verified agent identity.

**Deliverables:**
- `engine/auth.py` with `get_agent_by_token()`
- `api/dependencies.py` with `get_current_agent()` dependency
- Auth middleware that:
  - Extracts `Authorization: Bearer <token>`
  - Looks up agent_id
  - Attaches to request state
  - Returns 401 for missing/invalid tokens

**Acceptance Tests:**
```python
def test_missing_token_returns_401():
    response = client.get("/sessions")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"

def test_invalid_token_returns_401():
    response = client.get("/sessions", headers={"Authorization": "Bearer fake"})
    assert response.status_code == 401

def test_valid_token_proceeds():
    # Create agent, use its token
    response = client.get("/sessions", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code != 401
```

**Commit:** `feat: bearer token authentication middleware`

---

## TASK 4 — Agent Registration Endpoint

**Goal:** Allow explicit agent identity creation.

**Deliverables:**
- `api/routes/agents.py` with `POST /agents`
- Generates random `agent_id` (uuid4)
- Generates random `token` (secrets.token_urlsafe)
- No auth required for this endpoint

**Acceptance Tests:**
```python
def test_create_agent():
    response = client.post("/agents")
    assert response.status_code == 201
    data = response.json()
    assert "agent_id" in data
    assert "token" in data

def test_token_authenticates():
    create_resp = client.post("/agents")
    token = create_resp.json()["token"]
    auth_resp = client.get("/sessions", headers={"Authorization": f"Bearer {token}"})
    assert auth_resp.status_code != 401
```

**Commit:** `feat: agent registration endpoint`

---

## TASK 5 — State Machine Interface

**Goal:** Define the abstract interface all templates must implement.

**Deliverables:**
- `engine/templates/base.py` with `StateMachine` ABC
- `engine/templates/registry.py` with template lookup
- `engine/errors.py` with custom exceptions

**Interface:**
```python
class StateMachine(ABC):
    @property
    def template_id(self) -> str: ...
    @property
    def roles(self) -> list[str]: ...
    def initial_state(self) -> dict: ...
    def legal_actions(self, state: dict, role: str) -> list[str]: ...
    def apply_action(self, state: dict, role: str, action: str) -> dict: ...
    def is_terminal(self, state: dict) -> bool: ...
    def view_state(self, state: dict, role: str) -> dict: ...
```

**Acceptance Tests:**
```python
def test_dummy_template_conforms_to_interface():
    # Create a minimal dummy implementation
    # Verify all methods are callable and return correct types
```

**Commit:** `feat: state machine interface and template registry`

---

## TASK 6 — Session Creation & Listing

**Goal:** Create sessions with bound participants and roles.

**Deliverables:**
- `api/routes/sessions.py` with:
  - `POST /sessions` — create session
  - `GET /sessions` — list sessions for agent
- `api/schemas.py` with Pydantic models

**Request Schema:**
```python
class CreateSessionRequest(BaseModel):
    template: str  # "chess.v1" or "rps.v1"
    participants: dict[str, str]  # role -> agent_id
```

**Acceptance Tests:**
```python
def test_create_session():
    response = client.post("/sessions", json={
        "template": "chess.v1",
        "participants": {"white": agent1_id, "black": agent2_id}
    }, headers=auth_header)
    assert response.status_code == 201
    assert response.json()["status"] == "active"

def test_non_participant_cannot_create():
    # agent3 tries to create session for agent1 vs agent2
    response = client.post("/sessions", json={...}, headers=agent3_auth)
    assert response.status_code == 403

def test_list_sessions_filters_by_participant():
    # Create session with agent1 and agent2
    # agent1 sees it in their list
    # agent3 does not
```

**Commit:** `feat: session creation and participant binding`

---

## TASK 7 — Rock-Paper-Scissors Template

**Goal:** Implement RPS as first template (simpler than chess, tests simultaneous moves).

**Deliverables:**
- `engine/templates/rps.py` implementing `StateMachine`
- Register in `registry.py`

**State:**
```python
{
    "phase": "commit",  # "commit" | "reveal"
    "choices": {"player_1": None, "player_2": None},
    "result": None  # None | "player_1_wins" | "player_2_wins" | "draw"
}
```

**Acceptance Tests:**
```python
def test_initial_state():
    rps = RockPaperScissors()
    state = rps.initial_state()
    assert state["phase"] == "commit"
    assert state["choices"] == {"player_1": None, "player_2": None}

def test_legal_actions_during_commit():
    state = {"phase": "commit", "choices": {"player_1": None, "player_2": None}, "result": None}
    actions = rps.legal_actions(state, "player_1")
    assert set(actions) == {"rock", "paper", "scissors"}

def test_no_actions_after_committed():
    state = {"phase": "commit", "choices": {"player_1": "rock", "player_2": None}, "result": None}
    actions = rps.legal_actions(state, "player_1")
    assert actions == []

def test_view_state_hides_opponent_choice():
    state = {"phase": "commit", "choices": {"player_1": "rock", "player_2": None}, "result": None}
    view = rps.view_state(state, "player_2")
    assert view["choices"]["player_1"] == "hidden"
    assert view["choices"]["player_2"] is None

def test_both_commit_resolves():
    state = {"phase": "commit", "choices": {"player_1": "rock", "player_2": None}, "result": None}
    state = rps.apply_action(state, "player_2", "scissors")
    assert state["phase"] == "reveal"
    assert state["result"] == "player_1_wins"

def test_terminal_after_resolution():
    state = {"phase": "reveal", "choices": {"player_1": "rock", "player_2": "scissors"}, "result": "player_1_wins"}
    assert rps.is_terminal(state) is True
```

**Commit:** `feat: rock-paper-scissors template`

---

## TASK 8 — Chess Template

**Goal:** Implement chess template using python-chess.

**Deliverables:**
- `engine/templates/chess.py` implementing `StateMachine`
- Register in `registry.py`

**State:**
```python
{
    "fen": "...",  # FEN string
    "turn": "white",  # "white" | "black"
    "outcome": None  # None | "white_wins" | "black_wins" | "draw"
}
```

**Acceptance Tests:**
```python
def test_initial_state():
    chess_template = ChessGame()
    state = chess_template.initial_state()
    assert state["turn"] == "white"
    assert state["outcome"] is None

def test_legal_actions_for_white():
    state = chess_template.initial_state()
    actions = chess_template.legal_actions(state, "white")
    assert "e2e4" in actions
    assert len(actions) == 20  # 20 possible opening moves

def test_black_cannot_move_when_white_turn():
    state = chess_template.initial_state()
    actions = chess_template.legal_actions(state, "black")
    assert actions == []

def test_apply_legal_move():
    state = chess_template.initial_state()
    new_state = chess_template.apply_action(state, "white", "e2e4")
    assert new_state["turn"] == "black"
    assert "e4" in new_state["fen"]

def test_illegal_move_raises():
    state = chess_template.initial_state()
    with pytest.raises(IllegalActionError):
        chess_template.apply_action(state, "white", "e2e5")  # illegal

def test_checkmate_is_terminal():
    # Set up a checkmate position via FEN
    state = {"fen": "...", "turn": "black", "outcome": "white_wins"}
    assert chess_template.is_terminal(state) is True
```

**Commit:** `feat: chess template`

---

## TASK 9 — Action Submission Endpoint

**Goal:** Allow agents to submit actions to sessions.

**Deliverables:**
- `api/routes/actions.py` with `POST /sessions/{session_id}/actions`
- Optimistic locking via `expected_tick` for sequential games
- Submission tracking for simultaneous games

**Request Schema:**
```python
class SubmitActionRequest(BaseModel):
    action: str
    expected_tick: int | None = None
```

**Acceptance Tests:**
```python
def test_submit_valid_action():
    response = client.post(f"/sessions/{session_id}/actions", 
        json={"action": "e2e4", "expected_tick": 0},
        headers=white_auth)
    assert response.status_code == 200
    assert response.json()["tick"] == 1

def test_wrong_turn_rejected():
    # White's turn, black tries to move
    response = client.post(f"/sessions/{session_id}/actions",
        json={"action": "e7e5", "expected_tick": 0},
        headers=black_auth)
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_ACTION"

def test_tick_mismatch_rejected():
    # Submit with wrong expected_tick
    response = client.post(f"/sessions/{session_id}/actions",
        json={"action": "e2e4", "expected_tick": 5},
        headers=white_auth)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "CONFLICT"

def test_action_logged():
    client.post(f"/sessions/{session_id}/actions", ...)
    log = client.get(f"/sessions/{session_id}/log", headers=auth).json()
    assert len(log["actions"]) == 1
```

**Commit:** `feat: action submission with optimistic locking`

---

## TASK 10 — State Query Endpoint

**Goal:** Allow participants to read session state.

**Deliverables:**
- `GET /sessions/{session_id}/state` in `api/routes/sessions.py`
- Returns filtered state via `view_state()`
- Includes `legal_actions` for the querying agent

**Response Schema:**
```python
{
    "session_id": "...",
    "template": "chess.v1",
    "status": "active",
    "tick": 5,
    "state": { ... },
    "your_role": "white",
    "legal_actions": ["e2e4", ...]
}
```

**Acceptance Tests:**
```python
def test_participant_can_read_state():
    response = client.get(f"/sessions/{session_id}/state", headers=auth)
    assert response.status_code == 200
    assert "state" in response.json()

def test_non_participant_cannot_read():
    response = client.get(f"/sessions/{session_id}/state", headers=other_auth)
    assert response.status_code == 403

def test_rps_hides_opponent_choice():
    # player_1 has chosen, player_2 queries state
    response = client.get(f"/sessions/{session_id}/state", headers=player_2_auth)
    assert response.json()["state"]["choices"]["player_1"] == "hidden"
```

**Commit:** `feat: session state query endpoint`

---

## TASK 11 — Action Log Endpoint

**Goal:** Provide immutable audit trail.

**Deliverables:**
- `GET /sessions/{session_id}/log` in `api/routes/actions.py`
- Returns ordered list of all actions

**Response Schema:**
```python
{
    "actions": [
        {
            "tick": 0,
            "role": "white",
            "agent_id": "...",
            "action": "e2e4",
            "created_at": "2024-..."
        }
    ]
}
```

**Acceptance Tests:**
```python
def test_log_returns_all_actions():
    # Make several moves
    log = client.get(f"/sessions/{session_id}/log", headers=auth).json()
    assert len(log["actions"]) == expected_count

def test_log_is_ordered():
    log = client.get(f"/sessions/{session_id}/log", headers=auth).json()
    ticks = [a["tick"] for a in log["actions"]]
    assert ticks == sorted(ticks)

def test_non_participant_cannot_read_log():
    response = client.get(f"/sessions/{session_id}/log", headers=other_auth)
    assert response.status_code == 403
```

**Commit:** `feat: immutable action log endpoint`

---

## TASK 12 — Invariant & Adversarial Tests

**Goal:** Prove the system cannot be broken.

**Deliverables:**
- `tests/test_invariants.py` with comprehensive adversarial tests

**Test Cases:**

```python
def test_no_action_without_auth():
    response = client.post(f"/sessions/{sid}/actions", json={"action": "e2e4"})
    assert response.status_code == 401

def test_no_action_by_non_participant():
    response = client.post(f"/sessions/{sid}/actions", 
        json={"action": "e2e4"},
        headers=outsider_auth)
    assert response.status_code == 403

def test_no_illegal_action():
    response = client.post(f"/sessions/{sid}/actions",
        json={"action": "e2e5", "expected_tick": 0},  # illegal move
        headers=white_auth)
    assert response.status_code == 400

def test_no_out_of_turn_action():
    # It's white's turn
    response = client.post(f"/sessions/{sid}/actions",
        json={"action": "e7e5", "expected_tick": 0},
        headers=black_auth)
    assert response.status_code == 400

def test_no_double_action_chess():
    client.post(f"/sessions/{sid}/actions", json={"action": "e2e4", "expected_tick": 0}, headers=white_auth)
    response = client.post(f"/sessions/{sid}/actions", json={"action": "d2d4", "expected_tick": 0}, headers=white_auth)
    assert response.status_code == 409

def test_no_double_action_rps():
    client.post(f"/sessions/{sid}/actions", json={"action": "rock"}, headers=p1_auth)
    response = client.post(f"/sessions/{sid}/actions", json={"action": "paper"}, headers=p1_auth)
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "ALREADY_ACTED"

def test_no_action_after_terminal():
    # Complete a game
    response = client.post(f"/sessions/{sid}/actions", json={"action": "e2e4"}, headers=auth)
    assert response.status_code == 400

def test_read_does_not_mutate():
    state_before = client.get(f"/sessions/{sid}/state", headers=auth).json()
    client.get(f"/sessions/{sid}/state", headers=auth)
    client.get(f"/sessions/{sid}/log", headers=auth)
    state_after = client.get(f"/sessions/{sid}/state", headers=auth).json()
    assert state_before == state_after
```

**Commit:** `test: adversarial and invariant enforcement tests`

---

## TASK 13 — End-to-End Game Tests

**Goal:** Prove complete games work.

**Deliverables:**
- `tests/test_e2e.py` with full game playthroughs

**Test Cases:**

```python
def test_complete_rps_game():
    # Create two agents
    # Create RPS session
    # Both submit choices
    # Verify result and terminal state

def test_complete_chess_game_scholars_mate():
    # Create two agents
    # Create chess session
    # Play scholar's mate (4-move checkmate)
    # Verify white wins and game is terminal
```

**Commit:** `test: end-to-end game completion tests`

---

## Post-MVP Tasks (Do Not Start Until Above Complete)

### TASK 14 — MCP Adapter

Wrap REST endpoints as MCP tools:
- `create_session` tool
- `submit_action` tool
- `get_state` resource
- `get_log` resource

### TASK 15 — WebSocket Subscriptions

Real-time state updates for waiting agents.

### TASK 16 — Additional Templates

- Tic-Tac-Toe
- Connect Four
