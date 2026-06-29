"""Item routes: CRUD for user-owned items."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app import auth
from app.models import Item, ItemCreate, User

router = APIRouter()

_ITEM_STORE: dict[int, Item] = {}
_next_id = 1


@router.get("/", response_model=list[Item])
def list_items(current_user: User = Depends(auth.get_current_user)) -> list[Item]:
    return [i for i in _ITEM_STORE.values() if i.owner == current_user.username]


@router.post("/", response_model=Item, status_code=201)
def create_item(
    body: ItemCreate, current_user: User = Depends(auth.get_current_user)
) -> Item:
    global _next_id
    item = Item(id=_next_id, title=body.title, description=body.description, owner=current_user.username)
    _ITEM_STORE[_next_id] = item
    _next_id += 1
    return item


@router.get("/{item_id}", response_model=Item)
def get_item(item_id: int, current_user: User = Depends(auth.get_current_user)) -> Item:
    item = _ITEM_STORE.get(item_id)
    if item is None or item.owner != current_user.username:
        raise HTTPException(status_code=404, detail="Item not found")
    return item


@router.delete("/{item_id}", status_code=204)
def delete_item(item_id: int, current_user: User = Depends(auth.get_current_user)) -> None:
    item = _ITEM_STORE.get(item_id)
    if item is None or item.owner != current_user.username:
        raise HTTPException(status_code=404, detail="Item not found")
    del _ITEM_STORE[item_id]
