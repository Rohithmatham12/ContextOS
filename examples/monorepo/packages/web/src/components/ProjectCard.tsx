import React from "react";
import type { Project } from "@example/shared/src/types";

interface Props {
  project: Project;
  onDelete?: (id: string) => void;
  canDelete?: boolean;
}

export function ProjectCard({ project, onDelete, canDelete = false }: Props): React.JSX.Element {
  return (
    <article aria-label={project.name}>
      <h3>{project.name}</h3>
      <p>Members: {project.members.length}</p>
      <time dateTime={project.createdAt}>
        Created {new Date(project.createdAt).toLocaleDateString()}
      </time>
      {canDelete && onDelete && (
        <button onClick={() => onDelete(project.id)} aria-label={`Delete ${project.name}`}>
          Delete
        </button>
      )}
    </article>
  );
}
