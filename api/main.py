from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from api.routes import sessions
from engine.db import init_db
from engine.errors import StateMachineError


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(lifespan=lifespan)
app.include_router(sessions.router)


@app.exception_handler(StateMachineError)
async def state_machine_error_handler(
    request: Request, exc: StateMachineError
) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": exc.code, "message": exc.message}},
    )


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}
