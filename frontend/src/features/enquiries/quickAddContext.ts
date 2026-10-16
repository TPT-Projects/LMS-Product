import { createContext } from 'react';

export interface QuickAddContextValue {
  open: () => void;
}

export const QuickAddContext = createContext<QuickAddContextValue | null>(null);
