export interface User {
  username: string;
  email: string;
  role: "admin" | "user";
}

export interface Item {
  id: number;
  title: string;
  description: string;
  owner: string;
}

export interface AuthState {
  user: User | null;
  token: string | null;
  isLoading: boolean;
  error: string | null;
}

export interface ApiError {
  detail: string;
}
