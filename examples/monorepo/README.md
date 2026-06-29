# Example: Monorepo (Turborepo)

A multi-package workspace with a shared type library, an Express API, and a React frontend.

## Structure

```
packages/
├── shared/              Types and validation helpers shared by all packages
│   └── src/
│       ├── types.ts     User, Project, ApiResponse, ApiError
│       └── validators.ts  Email, UUID, role, permission helpers
├── api/                 Express REST API
│   └── src/
│       ├── index.ts     App entry point and routing
│       ├── auth.ts      /auth/register  /auth/login
│       └── routes.ts    /projects CRUD
└── web/                 React frontend
    └── src/
        ├── App.tsx            Project list page
        └── components/
            └── ProjectCard.tsx  Single project display
```

## ContextOS workflow

```bash
# From monorepo root — ContextOS scans the whole workspace
contextos init
contextos scan
contextos task "add project archiving"
contextos pack --budget 12000
contextos export claude --task "add project archiving"
```

The dependency graph will show that `packages/api/src/routes.ts` and
`packages/web/src/App.tsx` both depend on `packages/shared/src/types.ts`,
so ContextOS includes the shared types in the pack automatically.
