import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import React from "react";
import { describe, expect, it, vi } from "vitest";
import { LoginForm } from "./LoginForm";

describe("LoginForm", () => {
  it("renders username and password inputs", () => {
    render(<LoginForm onLogin={vi.fn()} error={null} isLoading={false} />);
    expect(screen.getByLabelText("Username")).toBeInTheDocument();
    expect(screen.getByLabelText("Password")).toBeInTheDocument();
  });

  it("calls onLogin with credentials on submit", async () => {
    const onLogin = vi.fn().mockResolvedValue(undefined);
    render(<LoginForm onLogin={onLogin} error={null} isLoading={false} />);
    fireEvent.change(screen.getByLabelText("Username"), { target: { value: "alice" } });
    fireEvent.change(screen.getByLabelText("Password"), { target: { value: "secret" } });
    fireEvent.submit(screen.getByRole("form"));
    await waitFor(() => expect(onLogin).toHaveBeenCalledWith("alice", "secret"));
  });

  it("displays error message when error is set", () => {
    render(<LoginForm onLogin={vi.fn()} error="Invalid credentials" isLoading={false} />);
    expect(screen.getByRole("alert")).toHaveTextContent("Invalid credentials");
  });

  it("disables button while loading", () => {
    render(<LoginForm onLogin={vi.fn()} error={null} isLoading />);
    expect(screen.getByRole("button")).toBeDisabled();
  });
});
