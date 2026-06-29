# Example: Python FastAPI

A small REST API with JWT auth, user registration, and item CRUD.

## Structure

```
app/
├── main.py          FastAPI application and middleware
├── auth.py          JWT creation, verification, password hashing
├── models.py        Pydantic request/response models
├── database.py      SQLAlchemy session factory
└── routes/
    ├── users.py     /users/register  /users/token  /users/me
    └── items.py     /items  CRUD endpoints
tests/
├── conftest.py      TestClient fixture
├── test_auth.py     Login, token, /me tests
└── test_users.py    Registration and item CRUD tests
```

## ContextOS workflow

```bash
# From this directory
contextos init
contextos scan
contextos task "fix auth bug"
contextos pack --budget 8000
contextos export claude --task "fix auth bug"
```

The pack will rank `app/auth.py` and `app/routes/users.py` highest for
auth-related tasks.
