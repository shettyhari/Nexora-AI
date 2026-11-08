"use client";

import { createContext, useContext, useEffect, useState, ReactNode } from "react";
import { User, Profile, UserPreference } from "@/types/user";
import { api } from "@/lib/api";
import { STORAGE_KEYS } from "@/lib/constants";

interface AuthContextType {
  user: User | null;
  loading: boolean;
  login: (data: { login: string; password: string }) => Promise<void>;
  register: (data: { email: string; username: string; password: string; display_name?: string }) => Promise<void>;
  logout: () => Promise<void>;
  refreshUser: () => Promise<void>;
  updateProfile: (data: Partial<Profile>) => Promise<void>;
  updatePreferences: (data: Partial<UserPreference>) => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  const refreshUser = async () => {
    const token = typeof window !== "undefined" ? localStorage.getItem(STORAGE_KEYS.TOKEN) : null;
    if (!token) {
      setUser(null);
      setLoading(false);
      return;
    }

    try {
      const userData = await api.getMe();
      setUser(userData);
    } catch {
      setUser(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    refreshUser();
  }, []);

  const login = async (data: { login: string; password: string }) => {
    await api.login(data);
    await refreshUser();
  };

  const register = async (data: { email: string; username: string; password: string; display_name?: string }) => {
    await api.register(data);
    await refreshUser();
  };

  const logout = async () => {
    await api.logout();
    setUser(null);
  };

  const updateProfile = async (data: Partial<Profile>) => {
    const updated = await api.updateProfile(data);
    if (user) {
      setUser({ ...user, profile: updated });
    }
  };

  const updatePreferences = async (data: Partial<UserPreference>) => {
    const updated = await api.updatePreferences(data);
    if (user) {
      setUser({ ...user, preferences: updated });
    }
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        loading,
        login,
        register,
        logout,
        refreshUser,
        updateProfile,
        updatePreferences,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
