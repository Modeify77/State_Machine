# Development Diary

Last updated: 2025-12-29

## What This Project Is

An MCP State Machine Host - a coordination engine for multiplayer turn-based games. The server is the single source of truth. Agents authenticate via bearer tokens and submit actions through REST endpoints OR MCP tools.

## What's Been Built

### Core System (Tasks 1-9 complete)
- FastAPI REST API with SQLite backend
- Agent registration with claim token system (prevents impersonation)
- Session creation with participant binding
- Action submission with state machine validation
- Two game templates: RPS (`rps.v1`) and Chess (`chess.v1`)

### Additional Features
- **Join-by-link flow**: Create session with open slots (`player_2: null`), share link, friend joins
- **GET session state**: View game state without making a move
- **RPS draws continue**: Game loops until there's a winner

### MCP Layer
- `mcp_server.py` - Full MCP server with 7 tools
- `.mcp.json` - Claude Code auto-discovery config
- Tested end-to-end with RPS game flow

### Push Notifications (just completed)
- **Real-time updates**: When any player makes a move, all watching clients receive `notifications/resources/updated`
- Uses MCP's `send_resource_updated()` on `session://{session_id}` resource URIs
- `WeakSet`-based session tracking for automatic cleanup of disconnected clients
- Context injection in tools: `create_session`, `join_session`, `submit_action`, `get_session_state`

## File Structure

```
/Users/pixel/State_Machine/
├── api/
│   ├── main.py              # FastAPI app entry
│   ├── dependencies.py      # Auth dependency (get_current_agent)
│   ├── schemas.py           # Pydantic models
│   └── routes/
│       ├── agents.py        # POST /agents, POST /agents/{id}/claim
│       ├── sessions.py      # CRUD sessions, join
│       └── actions.py       # POST /sessions/{id}/actions
├── engine/
│   ├── db.py                # All database operations
│   ├── errors.py            # Custom exceptions
│   └── templates/
│       ├── base.py          # StateMachine ABC
│       ├── registry.py      # Template registry
│       └── rps.py           # Rock-Paper-Scissors
├── tests/
│   ├── conftest.py          # Fixtures, TestTemplate, create_and_claim_agent helper
│   ├── test_agents.py
│   ├── test_sessions.py
│   ├── test_actions.py
│   └── test_rps.py
├── schema.sql               # Database schema
├── mcp_server.py            # MCP server (NEW)
├── .mcp.json                # MCP config for Claude Code (NEW)
├── CLAUDE.md                # Instructions for Claude
├── projectguide.md          # Architecture doc
└── tasks.md                 # Task list
```

## Key Patterns

### Agent Registration Flow
```
1. POST /agents -> {agent_id, claim_token}
2. POST /agents/{id}/claim {claim_token} -> {agent_id, token}
3. Use token in Authorization: Bearer {token}
```

### Session Creation with Open Slots
```python
# Creator specifies their ID, leaves opponent as null
participants = {"player_1": "my-agent-id", "player_2": None}
# Returns join_url, status="waiting"
# Friend calls POST /sessions/{id}/join to fill the slot
```

### State Visibility (RPS)
- **Commit phase**: Each player sees their own choice, opponent's is hidden
- **Reveal phase**: Both choices visible, result shown
- Controlled by `view_state()` method in template

## MCP Server Details

**Location**: `/Users/pixel/State_Machine/mcp_server.py`

**Tools**:
| Tool | Auth | Purpose |
|------|------|---------|
| `register_agent` | No | Get agent_id + claim_token |
| `claim_agent` | No | Exchange claim_token for bearer token |
| `create_session` | Token | Create game with participants |
| `join_session` | Token | Join open slot in session |
| `submit_action` | Token | Play a move |
| `get_session_state` | Token | View current state |
| `list_my_sessions` | Token | List your sessions |

**Resources**:
- `session://{session_id}` - Session state (public view, no role filtering)

**How to test MCP**:
```bash
python3 -c "from mcp_server import mcp; print('OK')"
```

**Run MCP server standalone**:
```bash
python3 mcp_server.py
# Communicates via stdio (JSON-RPC)
```

## Known Limitations / Future Work

1. **No chess template loaded in MCP**: Only RPS is registered. Chess exists but isn't imported.

2. **No agent discovery**: Agents can't look each other up by name. Must share agent_id out-of-band or use join-by-link.

3. **Single database path**: MCP server uses default `state_machine.db`. Tests use temp DB.

## Testing

```bash
# Run all tests (71 passing)
python3 -m pytest

# Run specific test file
python3 -m pytest tests/test_sessions.py -v

# Run with output
python3 -m pytest -s
```

## Running the Server

```bash
# REST API
uvicorn api.main:app --reload

# MCP (via Claude Code)
# Just open Claude Code in this directory - .mcp.json auto-configures
```

## Gotchas

1. **Use `python3` not `python`** - `python` isn't in PATH on this system
2. **Port 8000 may be in use** - Kill with `pkill -f "uvicorn api.main:app"`
3. **TestTemplate is in conftest.py** - Not a separate module, only for tests
4. **StateMachine uses `legal_actions()` not `is_valid_action()`** - Check the base class

## What To Work On Next

The user's goal is building an "open standard for state management". Possible next steps:

1. **Implement real push notifications** via MCP subscription protocol
2. **Add agent discovery** (register with display name, search by name)
3. **Load chess template** in MCP server
4. **Add spectator mode** (watch games without participating)
5. **Add game history/replay** endpoint

## Last Session Context

Implemented push notifications for MCP layer:
- Added `WeakSet`-based session tracking (`session_subscribers` dict)
- Injected `Context` parameter into session-related tools
- Implemented `notify_session_change()` to broadcast `send_resource_updated()` to all watchers
- When a player makes a move, all connected MCP clients watching that session receive notification

**How it works**:
1. Client calls any session tool → their MCP session is registered as a watcher
2. When `submit_action` or `join_session` changes state → `notify_session_change()` is called
3. All registered watchers receive `notifications/resources/updated` with URI `session://{id}`
4. Clients can then re-read the resource to get updated state
