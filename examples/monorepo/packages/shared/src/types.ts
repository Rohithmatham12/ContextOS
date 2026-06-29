export interface User {
  id: string;
  email: string;
  role: "admin" | "member" | "viewer";
  createdAt: string;
}

export interface Project {
  id: string;
  name: string;
  ownerId: string;
  members: string[];
  createdAt: string;
}

export interface ApiResponse<T> {
  data: T;
  meta?: { total?: number; page?: number };
}

export interface ApiError {
  code: string;
  message: string;
  details?: unknown;
}
