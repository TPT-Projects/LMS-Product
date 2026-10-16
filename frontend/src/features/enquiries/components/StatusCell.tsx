import { useState } from 'react';

import { useAuth } from '@/features/auth/useAuth';
import type { Enquiry, StatusRef } from '@/types/crm';

import { useUpdateEnquiry } from '../api';
import { StatusMenu } from './StatusMenu';

/** Status in the enquiries list: change it right there, without opening the enquiry. */
export function StatusCell({ enquiry }: { enquiry: Enquiry }) {
  const { can } = useAuth();
  const update = useUpdateEnquiry(enquiry.id);
  // Shown at once; the list refetches after the save (or goes back on an error).
  const [shown, setShown] = useState<StatusRef | null>(null);
  const status = shown && update.isPending ? shown : enquiry.status;

  return (
    <div onClick={(e) => e.stopPropagation()} className="inline-flex">
      <StatusMenu
        status={status}
        disabled={!can('edit_enquiries') || update.isPending}
        onChange={(statusId, next) => {
          if (statusId === enquiry.status.id) return;
          if (next) setShown(next);
          update.mutate({ status_id: statusId });
        }}
      />
    </div>
  );
}
