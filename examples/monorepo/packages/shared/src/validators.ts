import type { User } from "./types";

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export function isValidEmail(email: string): boolean {
  return EMAIL_RE.test(email);
}

export function isValidUUID(id: string): boolean {
  return UUID_RE.test(id);
}

export function isAdmin(user: User): boolean {
  return user.role === "admin";
}

export function canEditProject(user: User, projectOwnerId: string): boolean {
  return user.role === "admin" || user.id === projectOwnerId;
}

export function validateUserCreate(data: unknown): string[] {
  const errors: string[] = [];
  if (typeof data !== "object" || data === null) return ["Invalid payload"];
  const d = data as Record<string, unknown>;
  if (!d.email || !isValidEmail(String(d.email))) errors.push("Invalid email");
  if (!d.role || !["admin", "member", "viewer"].includes(String(d.role)))
    errors.push("Invalid role");
  return errors;
}
