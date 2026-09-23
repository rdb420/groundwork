"""Who may open a map. Every route that reads or changes a map, its recordings, drafts, parking
lot, rules, document or images goes through open_board, so tightening access is one change here.

Maps are shared workspaces today: any signed-in person with the link can open one (see
docs/ARCHITECTURE.md, "Decisions and known limits"). The map list still shows contributors only
the maps they started.
"""
from fastapi import HTTPException
from sqlalchemy.orm import Session as DB

from .models import Board, User


def can_open_board(board: Board, user: User) -> bool:
    return True


def open_board(db: DB, bid: str | None, user: User) -> Board:
    board = db.get(Board, bid) if bid else None
    if board is None or not can_open_board(board, user):
        raise HTTPException(404, "Map not found.")
    return board
