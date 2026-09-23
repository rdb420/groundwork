import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { api, type Me } from "./api";

type Ctx = { me: Me | null; loading: boolean; refresh: () => Promise<void> };
const SessionCtx = createContext<Ctx>({ me: null, loading: true, refresh: async () => {} });

export function SessionProvider({ children }: { children: ReactNode }) {
  const [me, setMe] = useState<Me | null>(null);
  const [loading, setLoading] = useState(true);
  const refresh = async () => {
    try {
      setMe(await api.get<Me>("/api/auth/me"));
    } catch {
      setMe(null);
    } finally {
      setLoading(false);
    }
  };
  useEffect(() => {
    if (location.pathname.startsWith("/login") || location.pathname.startsWith("/auth")) setLoading(false);
    else void refresh();
  }, []);
  return <SessionCtx.Provider value={{ me, loading, refresh }}>{children}</SessionCtx.Provider>;
}

export const useSession = () => useContext(SessionCtx);
