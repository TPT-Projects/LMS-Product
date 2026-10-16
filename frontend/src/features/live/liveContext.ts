import { createContext, useContext } from 'react';

export type LiveStatus = 'connecting' | 'open' | 'closed';

export interface LiveEvent {
  event: 'notification' | 'enquiry.created' | 'pong' | string;
  data?: Record<string, unknown>;
}

export interface LiveContextValue {
  status: LiveStatus;
  /** New leads that arrived while this tab was open (cleared when the list refreshes). */
  newLeads: number;
  clearNewLeads: () => void;
  subscribe: (listener: (event: LiveEvent) => void) => () => void;
}

export const LiveContext = createContext<LiveContextValue | null>(null);

export function useLive(): LiveContextValue {
  const ctx = useContext(LiveContext);
  if (!ctx) throw new Error('useLive must be used inside <LiveEventsProvider>');
  return ctx;
}
