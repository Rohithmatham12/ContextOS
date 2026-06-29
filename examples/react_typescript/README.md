# Example: React TypeScript SPA

A single-page app with JWT auth, item CRUD, custom hooks, and component tests.

## Structure

```
src/
├── App.tsx                      Root component — auth gate
├── types/index.ts               Shared TypeScript interfaces
├── api/client.ts                Typed fetch wrapper
├── hooks/
│   ├── useAuth.ts               Login/logout state + token persistence
│   └── useApi.ts                Items data fetching and mutation
└── components/
    ├── Auth/
    │   ├── LoginForm.tsx         Login form with error display
    │   └── LoginForm.test.tsx    Vitest + Testing Library tests
    └── Dashboard/
        └── Dashboard.tsx         Item list with create/delete
```

## ContextOS workflow

```bash
contextos init
contextos scan
contextos task "fix auth bug — token not refreshed on 401 response"
contextos pack --budget 8000
contextos export cursor --task "fix auth bug"
```

Auth-related tasks will surface `src/hooks/useAuth.ts` and `src/api/client.ts`.
