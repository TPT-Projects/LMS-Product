import { createContext } from 'react';

import type { AuthResponse, Capability, Session } from '@/types/auth';

export type AuthStatus = 'loading' | 'authenticated' | 'anonymous';

export interface AuthContextValue {
  status: AuthStatus;
  session: Session | null;
  /** Store tokens + session from any endpoint that logs the user in. */
  startSession: (response: AuthResponse) => void;
  logout: () => Promise<void>;
  switchWorkspace: (tenantId: number) => Promise<void>;
  reloadSession: () => Promise<void>;
  can: (capability: Capability) => boolean;
}

export const AuthContext = createContext<AuthContextValue | null>(null);
