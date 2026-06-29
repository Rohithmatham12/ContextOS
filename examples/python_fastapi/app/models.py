"""Pydantic data models."""

from __future__ import annotations

from pydantic import BaseModel, EmailStr


class User(BaseModel):
    username: str
    email: EmailStr
    role: str = "user"
    hashed_password: str = ""


class UserPublic(BaseModel):
    username: str
    email: EmailStr
    role: str


class UserCreate(BaseModel):
    username: str
    email: EmailStr
    password: str


class Item(BaseModel):
    id: int
    title: str
    description: str = ""
    owner: str


class ItemCreate(BaseModel):
    title: str
    description: str = ""


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    username: str
