from fastapi import HTTPException


def get_or_404(db, model, key, what: str = "Record"):
    obj = db.get(model, key)
    if obj is None:
        raise HTTPException(404, f"{what} not found.")
    return obj
