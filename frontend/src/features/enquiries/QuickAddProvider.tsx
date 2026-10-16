import { useMemo, useState, type ReactNode } from 'react';

import { useAuth } from '@/features/auth/useAuth';
import { useHotkeys } from '@/hooks/useHotkeys';

import { EnquiryFormDialog } from './components/EnquiryFormDialog';
import { QuickAddContext } from './quickAddContext';

/** Global quick add (spec section 8): the "+" button and the Q shortcut. */
export function QuickAddProvider({ children }: { children: ReactNode }) {
  const { can } = useAuth();
  const [open, setOpen] = useState(false);
  const allowed = can('edit_enquiries');

  useHotkeys(allowed ? { q: () => setOpen(true), '+': () => setOpen(true) } : {});
  const value = useMemo(() => ({ open: () => allowed && setOpen(true) }), [allowed]);

  return (
    <QuickAddContext.Provider value={value}>
      {children}
      {allowed && <EnquiryFormDialog open={open} onOpenChange={setOpen} />}
    </QuickAddContext.Provider>
  );
}
