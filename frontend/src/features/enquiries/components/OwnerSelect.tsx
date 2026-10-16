import { forwardRef } from 'react';
import { useTranslation } from 'react-i18next';

import { Select, type SelectProps } from '@/components/ui/Input';
import { useAllMembers } from '@/features/users/api';

/** Workspace members as a select. Empty value = Unassigned. */
export const OwnerSelect = forwardRef<
  HTMLSelectElement,
  SelectProps & { allowUnassigned?: boolean }
>(function OwnerSelect({ allowUnassigned = true, ...props }, ref) {
  const { t } = useTranslation();
  const members = useAllMembers();
  return (
    <Select ref={ref} {...props}>
      {allowUnassigned && <option value="">{t('enquiries.unassigned')}</option>}
      {members.data?.results.map((m) => (
        <option key={m.id} value={m.id}>
          {m.full_name}
        </option>
      ))}
    </Select>
  );
});
