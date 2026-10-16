import { Columns3 } from 'lucide-react';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';

import { Button } from '@/components/ui';

import type { ColumnOption } from './columns';
import { ColumnsDialog } from './ColumnsDialog';

interface Props {
  options: ColumnOption[];
  visible: string[]; // full resolved list, including fixed ids
  onSave: (columns: string[]) => void;
}

/** "Columns" toolbar button + dialog. */
export function ColumnsButton({ options, visible, onSave }: Props) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const fixed = new Set(options.filter((o) => o.fixed).map((o) => o.id));
  return (
    <>
      <Button variant="ghost" size="sm" onClick={() => setOpen(true)}>
        <Columns3 className="size-3.5" aria-hidden />
        {t('columns.button')}
      </Button>
      <ColumnsDialog
        open={open}
        onOpenChange={setOpen}
        options={options}
        value={visible.filter((id) => !fixed.has(id))}
        onSave={onSave}
      />
    </>
  );
}
