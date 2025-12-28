from pydantic import BaseModel


class CreateSessionRequest(BaseModel):
    template: str
    participants: dict[str, str]  # role -> agent_id


class SessionResponse(BaseModel):
    session_id: str
    template: str
    status: str
    tick: int


class SessionListResponse(BaseModel):
    sessions: list[SessionResponse]
