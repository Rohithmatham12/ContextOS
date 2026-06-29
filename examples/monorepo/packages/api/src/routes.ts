import { Router } from "express";
import type { Project } from "@example/shared/src/types";

export const projectsRouter = Router();

const projects = new Map<string, Project>();

projectsRouter.get("/", (_req, res) => {
  res.json({ data: [...projects.values()], meta: { total: projects.size } });
});

projectsRouter.post("/", (req, res) => {
  const { name, ownerId } = req.body as { name?: string; ownerId?: string };
  if (!name || !ownerId) {
    return res.status(400).json({ code: "MISSING_FIELDS", message: "name and ownerId required" });
  }
  const project: Project = {
    id: crypto.randomUUID(),
    name,
    ownerId,
    members: [ownerId],
    createdAt: new Date().toISOString(),
  };
  projects.set(project.id, project);
  return res.status(201).json({ data: project });
});

projectsRouter.get("/:id", (req, res) => {
  const project = projects.get(req.params.id);
  if (!project) return res.status(404).json({ code: "NOT_FOUND", message: "Project not found" });
  return res.json({ data: project });
});

projectsRouter.delete("/:id", (req, res) => {
  if (!projects.has(req.params.id)) {
    return res.status(404).json({ code: "NOT_FOUND", message: "Project not found" });
  }
  projects.delete(req.params.id);
  return res.status(204).send();
});
