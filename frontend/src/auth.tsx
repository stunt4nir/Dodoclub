import React, { createContext, useContext, useEffect, useState, useCallback } from 'react';
import { api, setToken, getToken, clearToken } from './api';

export type Position = 'GK' | 'CB' | 'LB' | 'RB' | 'CDM' | 'CM' | 'CAM' | 'LW' | 'RW' | 'ST' | 'DEF' | 'MID' | 'FWD' | 'ANY';

export type User = {
  id: string;
  email: string;
  name: string;
  profile_picture: string | null;
  shirt_number: number | null;
  preferred_position: Position | null;
  preferred_positions?: Position[];
  role: 'admin' | 'user';
  can_edit_matches: boolean;
  goals: number;
  assists: number;
  matches_played: number;
  wins: number;
  draws: number;
  losses: number;
  league_points: number;
  rating: number;
};

type AuthCtx = {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, name: string, shirt?: number) => Promise<void>;
  logout: () => Promise<void>;
  refresh: () => Promise<void>;
};

const Ctx = createContext<AuthCtx | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    const tok = await getToken();
    if (!tok) {
      setUser(null);
      setLoading(false);
      return;
    }
    try {
      const me = await api<User>('/auth/me');
      setUser(me);
    } catch {
      await clearToken();
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const login = async (email: string, password: string) => {
    const res = await api<{ token: string; user: User }>('/auth/login', {
      method: 'POST',
      body: { email, password },
      auth: false,
    });
    await setToken(res.token);
    setUser(res.user);
  };

  const register = async (email: string, password: string, name: string, shirt?: number) => {
    const res = await api<{ token: string; user: User }>('/auth/register', {
      method: 'POST',
      body: { email, password, name, shirt_number: shirt },
      auth: false,
    });
    await setToken(res.token);
    setUser(res.user);
  };

  const logout = async () => {
    await clearToken();
    setUser(null);
  };

  return (
    <Ctx.Provider value={{ user, loading, login, register, logout, refresh }}>
      {children}
    </Ctx.Provider>
  );
}

export function useAuth() {
  const v = useContext(Ctx);
  if (!v) throw new Error('useAuth must be inside AuthProvider');
  return v;
}
