import { useContext } from 'react';

import { QuickAddContext } from './quickAddContext';

/** Open the global "New enquiry" dialog from anywhere (also: the Q shortcut). */
export function useQuickAdd() {
  const ctx = useContext(QuickAddContext);
  if (!ctx) throw new Error('useQuickAdd must be used inside <QuickAddProvider>');
  return ctx;
}
