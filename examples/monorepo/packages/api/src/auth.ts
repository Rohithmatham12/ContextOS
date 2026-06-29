import { Router } from "express";
import { isValidEmail } from "@example/shared/src/validators";
import type { User } from "@example/shared/src/types";

export const authRouter = Router();

// In-memory store — replace with real DB in production.
const users = new Map<string, User & { passwordHash: string }>();

authRouter.post("/register", (req, res) => {
  const { email, role = "member", password } = req.body as {
    email?: string;
    role?: string;
    password?: string;
  };

  if (!email || !isValidEmail(email)) {
    return res.status(400).json({ code: "INVALID_EMAIL", message: "Invalid email address" });
  }
  if (!password || password.length < 8) {
    return res.status(400).json({ code: "WEAK_PASSWORD", message: "Password too short" });
  }
  if (users.has(email)) {
    return res.status(409).json({ code: "EMAIL_TAKEN", message: "Email already registered" });
  }

  const user: User = {
    id: crypto.randomUUID(),
    email,
    role: role as User["role"],
    createdAt: new Date().toISOString(),
  };
  users.set(email, { ...user, passwordHash: Buffer.from(password).toString("base64") });
  return res.status(201).json({ data: user });
});

authRouter.post("/login", (req, res) => {
  const { email, password } = req.body as { email?: string; password?: string };
  const stored = email ? users.get(email) : undefined;

  if (!stored || stored.passwordHash !== Buffer.from(password ?? "").toString("base64")) {
    return res.status(401).json({ code: "INVALID_CREDENTIALS", message: "Wrong email or password" });
  }

  // Simplified token — use real JWT in production.
  const token = Buffer.from(`${stored.id}:${Date.now()}`).toString("base64");
  return res.json({ data: { token, user: { id: stored.id, email: stored.email, role: stored.role } } });
});
