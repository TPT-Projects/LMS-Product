import { ArrowDown, ArrowUp, GripVertical, Lock } from 'lucide-react';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';

import { Button, Checkbox, Dialog } from '@/components/ui';
import { cn } from '@/lib/cn';

import { defaultLayout, move, type ColumnOption } from './columns';

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  options: ColumnOption[];
  /** Currently visible, user-chosen column ids in order (fixed columns excluded). */
  value: string[];
  onSave: (columns: string[]) => void;
}

type Row = { id: string; visible: boolean };

function toRows(options: ColumnOption[], visible: string[]): Row[] {
  const movable = options.filter((o) => !o.fixed);
  const shown = visible.filter((id) => movable.some((o) => o.id === id));
  const hidden = movable.filter((o) => !shown.includes(o.id)).map((o) => o.id);
  return [
    ...shown.map((id) => ({ id, visible: true })),
    ...hidden.map((id) => ({ id, visible: false })),
  ];
}

/**
 * Choose and order columns. Fixed columns are listed but locked.
 * Reorder by dragging the handle, or with the arrow buttons (keyboard friendly).
 */
export function ColumnsDialog({ open, onOpenChange, options, value, onSave }: Props) {
  const { t } = useTranslation();
  const [rows, setRows] = useState<Row[]>(() => toRows(options, value));
  const [dragIndex, setDragIndex] = useState<number | null>(null);
  const [wasOpen, setWasOpen] = useState(open);
  if (open !== wasOpen) {
    setWasOpen(open);
    if (open) setRows(toRows(options, value));
  }

  const label = (id: string) => options.find((o) => o.id === id)?.label ?? id;
  const fixedStart = options.filter((o) => o.fixed === 'start');
  const fixedEnd = options.filter((o) => o.fixed === 'end');

  const FixedRow = ({ option }: { option: ColumnOption }) => (
    <li className="flex items-center gap-2.5 rounded-lg bg-subtle px-2.5 py-2 text-fg-muted">
      <Lock className="size-3.5 shrink-0" aria-hidden />
      <span className="flex-1">{option.label}</span>
      <span className="text-xs">{t('columns.alwaysShown')}</span>
    </li>
  );

  return (
    <Dialog
      open={open}
      onOpenChange={onOpenChange}
      title={t('columns.title')}
      description={t('columns.description')}
      footer={
        <>
          <Button
            variant="ghost"
            className="sm:mr-auto"
            onClick={() => setRows(toRows(options, defaultLayout(options)))}
          >
            {t('columns.reset')}
          </Button>
          <Button variant="secondary" onClick={() => onOpenChange(false)}>
            {t('common.cancel')}
          </Button>
          <Button
            onClick={() => {
              onSave(rows.filter((r) => r.visible).map((r) => r.id));
              onOpenChange(false);
            }}
          >
            {t('common.save')}
          </Button>
        </>
      }
    >
      <ul className="space-y-1">
        {fixedStart.map((o) => (
          <FixedRow key={o.id} option={o} />
        ))}
      </ul>
      <ul className="my-1 space-y-1" aria-label={t('columns.movable')}>
        {rows.map((row, index) => (
          <li
            key={row.id}
            draggable
            onDragStart={() => setDragIndex(index)}
            onDragOver={(e) => {
              e.preventDefault();
              if (dragIndex !== null && dragIndex !== index) {
                setRows((r) => move(r, dragIndex, index));
                setDragIndex(index);
              }
            }}
            onDragEnd={() => setDragIndex(null)}
            className={cn(
              'flex items-center gap-2 rounded-lg border px-2 py-1.5',
              dragIndex === index && 'border-accent bg-accent-soft',
            )}
          >
            <GripVertical className="size-4 shrink-0 cursor-grab text-fg-subtle" aria-hidden />
            <label className="flex min-w-0 flex-1 cursor-pointer items-center gap-2.5">
              <Checkbox
                checked={row.visible}
                onChange={() =>
                  setRows((r) =>
                    r.map((x) => (x.id === row.id ? { ...x, visible: !x.visible } : x)),
                  )
                }
              />
              <span className={cn('truncate', !row.visible && 'text-fg-muted')}>
                {label(row.id)}
              </span>
            </label>
            <Button
              variant="ghost"
              size="icon"
              className="size-7"
              aria-label={t('columns.moveUp', { name: label(row.id) })}
              disabled={index === 0}
              onClick={() => setRows((r) => move(r, index, index - 1))}
            >
              <ArrowUp className="size-3.5" />
            </Button>
            <Button
              variant="ghost"
              size="icon"
              className="size-7"
              aria-label={t('columns.moveDown', { name: label(row.id) })}
              disabled={index === rows.length - 1}
              onClick={() => setRows((r) => move(r, index, index + 1))}
            >
              <ArrowDown className="size-3.5" />
            </Button>
          </li>
        ))}
      </ul>
      <ul className="space-y-1">
        {fixedEnd.map((o) => (
          <FixedRow key={o.id} option={o} />
        ))}
      </ul>
    </Dialog>
  );
}
