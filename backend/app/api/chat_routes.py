from typing import Literal

from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel, Field

from ..services.catalogue_chat import answer
from .routes import repository

router = APIRouter()


class ChatTurn(BaseModel):
    message: str = Field(default="", max_length=1000)
    session: str | None = Field(default=None, max_length=64)
    decision: Literal["confirm", "dismiss"] | None = None
    field: str = Field(default="", max_length=64)
    value: str = Field(default="", max_length=64)


@router.post("/chat")
def chat(turn: ChatTurn, response: Response):
    if not turn.decision and not turn.message.strip():
        raise HTTPException(422, "Enter a question.")
    response.headers["Cache-Control"] = "no-store"
    try:
        return answer(turn, repository.all())
    except KeyError as exc:
        raise HTTPException(410, "Conversation expired. Start a new chat.") from exc
    except ValueError as exc:
        raise HTTPException(409, "This suggestion has changed. Ask again.") from exc
