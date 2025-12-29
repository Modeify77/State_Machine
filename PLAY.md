# Play State Machine Games

Connect your Claude Code to the game server and play RPS or Chess against friends!

## Quick Setup (30 seconds)

**Step 1:** Add this to your `~/.claude/mcp.json` (create the file if it doesn't exist):

```json
{
  "mcpServers": {
    "state-machine": {
      "type": "sse",
      "url": "https://state-machine-mcp.fly.dev/sse"
    }
  }
}
```

**Step 2:** Restart Claude Code

**Step 3:** Ask Claude: "Register me as a game agent and create a Rock Paper Scissors game"

## How to Play

### Create a game (you're player 1):
```
"Create an RPS game with an open slot for a friend to join"
```

Claude will give you a **session ID** to share.

### Join a friend's game (you're player 2):
```
"Join game session <paste-session-id-here>"
```

### Make your move:
```
"Play rock" (or paper, or scissors)
```

## Available Games

| Game | Template ID | Description |
|------|-------------|-------------|
| Rock Paper Scissors | `rps.v1` | Best of 1, draws replay |
| Chess | `chess.v1` | Standard chess |

## What Claude Can Do

- `register_agent` - Create your player identity
- `create_session` - Start a new game
- `join_session` - Join someone's game
- `submit_action` - Make a move
- `get_session_state` - Check game status
- `list_my_sessions` - See your active games

## Server Status

**URL:** https://state-machine-mcp.fly.dev/sse

Test if it's online:
```bash
curl -s https://state-machine-mcp.fly.dev/sse -H "Accept: text/event-stream" | head -1
```

---

Made with Claude Code
