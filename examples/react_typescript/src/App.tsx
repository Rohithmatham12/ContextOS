import React from "react";
import { Dashboard } from "./components/Dashboard/Dashboard";
import { LoginForm } from "./components/Auth/LoginForm";
import { useAuth } from "./hooks/useAuth";

export default function App(): React.JSX.Element {
  const { user, token, isLoading, error, login, logout } = useAuth();

  if (user && token) {
    return <Dashboard user={user} token={token} onLogout={logout} />;
  }

  return (
    <div style={{ maxWidth: 400, margin: "80px auto" }}>
      <LoginForm onLogin={login} error={error} isLoading={isLoading} />
    </div>
  );
}
