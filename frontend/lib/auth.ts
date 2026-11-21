import { Profile } from "./types";

const API_BASE = (process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000").replace(/\/$/, "");

export type AuthUser = {
  email: string;
  created_at: string;
};

export type AuthStatus = {
  authenticated: boolean;
  user: AuthUser | null;
};

export type AccountProfile = { profile: Profile | null; updated_at: string | null };

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}/api/v1/auth/${path}`, {
    ...init,
    cache: "no-store",
    credentials: "include",
    headers: {
      Accept: "application/json",
      ...(init?.body ? { "Content-Type": "application/json" } : {}),
    },
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = typeof payload?.detail === "string" ? payload.detail : "Authentication request failed.";
    throw new Error(detail);
  }
  return payload as T;
}

export function signUp(email: string, password: string) {
  return request<AuthStatus>("signup", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
}

export function logIn(email: string, password: string) {
  return request<AuthStatus>("login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
}

export function getAuthStatus() {
  return request<AuthStatus>("me");
}

export function getAccountProfile() {
  return request<AccountProfile>("profile");
}

export function saveAccountProfile(profile: Profile) {
  return request<AccountProfile>("profile", {
    method: "PUT",
    body: JSON.stringify({ profile }),
  });
}

export function changePassword(currentPassword: string, newPassword: string) {
  return request<{ updated: boolean }>("change-password", {
    method: "POST",
    body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }),
  });
}

export function logOut() {
  return request<{ authenticated: boolean }>("logout", { method: "POST" });
}

