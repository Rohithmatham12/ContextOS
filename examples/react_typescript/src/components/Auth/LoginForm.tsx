import React, { FormEvent, useState } from "react";

interface Props {
  onLogin: (username: string, password: string) => Promise<void>;
  error: string | null;
  isLoading: boolean;
}

export function LoginForm({ onLogin, error, isLoading }: Props): React.JSX.Element {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    onLogin(username, password);
  };

  return (
    <form onSubmit={handleSubmit} aria-label="Login form">
      <h2>Sign in</h2>
      {error && <p role="alert" style={{ color: "red" }}>{error}</p>}
      <div>
        <label htmlFor="username">Username</label>
        <input
          id="username"
          type="text"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          required
          autoComplete="username"
        />
      </div>
      <div>
        <label htmlFor="password">Password</label>
        <input
          id="password"
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
          autoComplete="current-password"
        />
      </div>
      <button type="submit" disabled={isLoading}>
        {isLoading ? "Signing in…" : "Sign in"}
      </button>
    </form>
  );
}
