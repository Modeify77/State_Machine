-- Agents: identity + auth token
CREATE TABLE IF NOT EXISTS agents (
    agent_id TEXT PRIMARY KEY,
    token TEXT UNIQUE NOT NULL,
    claim_token TEXT UNIQUE NOT NULL,
    claimed INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Sessions: game instances
CREATE TABLE IF NOT EXISTS sessions (
    session_id TEXT PRIMARY KEY,
    template TEXT NOT NULL,
    state TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    tick INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Participants: binds agents to sessions with roles
CREATE TABLE IF NOT EXISTS participants (
    session_id TEXT NOT NULL,
    agent_id TEXT NOT NULL,
    role TEXT NOT NULL,
    PRIMARY KEY (session_id, agent_id),
    FOREIGN KEY (session_id) REFERENCES sessions(session_id),
    FOREIGN KEY (agent_id) REFERENCES agents(agent_id)
);

-- Actions: immutable log of all moves
CREATE TABLE IF NOT EXISTS actions (
    action_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    agent_id TEXT NOT NULL,
    role TEXT NOT NULL,
    action TEXT NOT NULL,
    tick INTEGER NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (session_id) REFERENCES sessions(session_id),
    FOREIGN KEY (agent_id) REFERENCES agents(agent_id)
);
