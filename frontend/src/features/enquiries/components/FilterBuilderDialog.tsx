import { FolderPlus, Plus, Trash2 } from 'lucide-react';
import { useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';

import {
  Button,
  ChipGroup,
  DateInput,
  Dialog,
  Input,
  Select,
  type ChipChoice,
} from '@/components/ui';
import { activeFields, useCustomFields } from '@/features/customfields/api';
import { displayOption } from '@/features/customfields/values';
import { useStatuses } from '@/features/statuses/api';
import { useAllMembers } from '@/features/users/api';
import { cn } from '@/lib/cn';
import { SOURCES, type FilterGroup, type FilterRule } from '@/types/crm';

import {
  cleanTree,
  customFieldDefs,
  defaultValue,
  emptyGroup,
  isGroup,
  newRule,
  OPERATORS,
  STANDARD_FIELDS,
  valueInputFor,
  type FieldDef,
} from '../filters';

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  value: FilterGroup | null;
  onApply: (tree: FilterGroup | null) => void;
}

type Choice = ChipChoice;

export function FilterBuilderDialog({ open, onOpenChange, value, onApply }: Props) {
  const { t } = useTranslation();
  const statuses = useStatuses();
  const members = useAllMembers();
  const customFields = activeFields(useCustomFields().data);
  const [draft, setDraft] = useState<FilterGroup>(emptyGroup());
  const [wasOpen, setWasOpen] = useState(open);
  if (open !== wasOpen) {
    setWasOpen(open);
    if (open) setDraft(value ? structuredClone(value) : emptyGroup());
  }

  const fields = useMemo(
    () => [...STANDARD_FIELDS, ...customFieldDefs(customFields)],
    [customFields],
  );
  const fieldById = useMemo(() => new Map(fields.map((f) => [f.id, f])), [fields]);
  const fieldLabel = (f: FieldDef) => (f.labelKey ? t(f.labelKey) : (f.label ?? f.id));

  const choicesFor = (field: FieldDef): Choice[] => {
    switch (field.kind) {
      case 'status':
        return (statuses.data ?? []).map((s) => ({ value: String(s.id), label: s.name }));
      case 'owner':
        return [
          { value: 'me', label: t('filters.me') },
          ...(members.data?.results ?? []).map((m) => ({
            value: String(m.id),
            label: m.full_name,
          })),
        ];
      case 'source':
        return SOURCES.map((s) => ({ value: s, label: t(`sources.${s}`) }));
      default:
        return (field.options ?? []).map((o) => ({ value: o, label: displayOption(o) }));
    }
  };

  // --- tree editing (immutable updates by path) ---------------------------------------
  type Path = number[];
  const updateAt = (
    path: Path,
    fn: (node: FilterRule | FilterGroup) => FilterRule | FilterGroup | null,
  ) => {
    const walk = (group: FilterGroup, depth: number): FilterGroup => {
      const index = path[depth]!;
      const rules = [...group.rules];
      if (depth === path.length - 1) {
        const next = fn(rules[index]!);
        if (next === null) rules.splice(index, 1);
        else rules[index] = next;
      } else {
        rules[index] = walk(rules[index] as FilterGroup, depth + 1);
      }
      return { ...group, rules };
    };
    setDraft((d) => walk(d, 0));
  };

  const addTo = (path: Path, node: FilterRule | FilterGroup) => {
    if (path.length === 0) {
      setDraft((d) => ({ ...d, rules: [...d.rules, node] }));
      return;
    }
    updateAt(path, (group) => ({
      ...(group as FilterGroup),
      rules: [...(group as FilterGroup).rules, node],
    }));
  };

  const setOp = (path: Path, op: 'and' | 'or') =>
    path.length === 0
      ? setDraft((d) => ({ ...d, op }))
      : updateAt(path, (group) => ({ ...(group as FilterGroup), op }));

  // --- rendering ----------------------------------------------------------------------
  const renderValue = (rule: FilterRule, field: FieldDef, path: Path) => {
    const input = valueInputFor(field.kind, rule.operator);
    const set = (value: unknown) => updateAt(path, (r) => ({ ...(r as FilterRule), value }));
    const label = t('filters.value');
    switch (input) {
      case 'none':
        return null;
      case 'days':
        return (
          <div className="flex items-center gap-2">
            <Input
              aria-label={label}
              type="number"
              min={1}
              max={3650}
              className="w-24"
              value={String(rule.value ?? '')}
              onChange={(e) => set(Number(e.target.value))}
            />
            <span className="text-[13px] text-fg-muted">{t('filters.days')}</span>
          </div>
        );
      case 'date':
        return (
          <DateInput
            aria-label={label}
            value={String(rule.value ?? '')}
            onChange={(e) => set(e.target.value)}
          />
        );
      case 'date_range':
      case 'number_range': {
        const [low, high] = (rule.value as [string, string]) ?? ['', ''];
        const Field = input === 'date_range' ? DateInput : Input;
        return (
          <div className="flex items-center gap-2">
            <Field
              aria-label={t('filters.from')}
              value={String(low ?? '')}
              onChange={(e) => set([e.target.value, high])}
            />
            <span className="text-fg-subtle">–</span>
            <Field
              aria-label={t('filters.to')}
              value={String(high ?? '')}
              onChange={(e) => set([low, e.target.value])}
            />
          </div>
        );
      }
      case 'statuses':
      case 'owners':
      case 'sources':
      case 'options': {
        const selected = ((rule.value as unknown[]) ?? []).map(String);
        return (
          <ChipGroup
            choices={choicesFor(field)}
            selected={selected}
            onChange={(values) => set(input === 'statuses' ? values.map(Number) : values)}
          />
        );
      }
      case 'number':
        return (
          <Input
            aria-label={label}
            inputMode="decimal"
            value={String(rule.value ?? '')}
            onChange={(e) => set(e.target.value)}
          />
        );
      default:
        return (
          <Input
            aria-label={label}
            value={String(rule.value ?? '')}
            onChange={(e) => set(e.target.value)}
          />
        );
    }
  };

  const renderRule = (rule: FilterRule, path: Path) => {
    const field = fieldById.get(rule.field);
    if (!field) return null;
    return (
      <div className="space-y-2 rounded-lg border bg-surface p-3">
        <div className="flex flex-col gap-2 sm:flex-row">
          <Select
            aria-label={t('filters.field')}
            className="sm:w-48"
            value={rule.field}
            onChange={(e) => {
              const next = fieldById.get(e.target.value);
              if (next) updateAt(path, () => newRule(next));
            }}
          >
            <optgroup label={t('filters.standardFields')}>
              {STANDARD_FIELDS.map((f) => (
                <option key={f.id} value={f.id}>
                  {fieldLabel(f)}
                </option>
              ))}
            </optgroup>
            {customFields.length > 0 && (
              <optgroup label={t('filters.customFields')}>
                {customFieldDefs(customFields).map((f) => (
                  <option key={f.id} value={f.id}>
                    {fieldLabel(f)}
                  </option>
                ))}
              </optgroup>
            )}
          </Select>
          <Select
            aria-label={t('filters.operator')}
            className="sm:w-48"
            value={rule.operator}
            onChange={(e) => {
              const operator = e.target.value;
              const keep =
                valueInputFor(field.kind, operator) === valueInputFor(field.kind, rule.operator);
              updateAt(path, () => ({
                field: rule.field,
                operator,
                value: keep ? rule.value : defaultValue(valueInputFor(field.kind, operator)),
              }));
            }}
          >
            {OPERATORS[field.kind].map((op) => (
              <option key={op} value={op}>
                {t(`filters.ops.${op}`)}
              </option>
            ))}
          </Select>
          <Button
            variant="ghost"
            size="icon"
            className="self-end sm:ml-auto sm:self-auto"
            aria-label={t('filters.removeRule')}
            onClick={() => updateAt(path, () => null)}
          >
            <Trash2 className="size-4" />
          </Button>
        </div>
        {renderValue(rule, field, path)}
      </div>
    );
  };

  const renderGroup = (group: FilterGroup, path: Path) => (
    <div
      className={cn(
        'space-y-2',
        path.length > 0 && 'rounded-xl border border-dashed bg-subtle p-3',
      )}
    >
      <div className="flex flex-wrap items-center gap-2 text-[13px]">
        <span className="text-fg-muted">{t('filters.match')}</span>
        <Select
          aria-label={t('filters.match')}
          className="h-8 w-auto"
          value={group.op}
          onChange={(e) => setOp(path, e.target.value as 'and' | 'or')}
        >
          <option value="and">{t('filters.all')}</option>
          <option value="or">{t('filters.any')}</option>
        </Select>
        <span className="text-fg-muted">{t('filters.ofTheseRules')}</span>
        {path.length > 0 && (
          <Button
            variant="ghost"
            size="sm"
            className="ml-auto"
            onClick={() => updateAt(path, () => null)}
          >
            <Trash2 className="size-3.5" aria-hidden /> {t('filters.removeGroup')}
          </Button>
        )}
      </div>
      {group.rules.map((node, index) => (
        <div key={index}>
          {isGroup(node) ? renderGroup(node, [...path, index]) : renderRule(node, [...path, index])}
        </div>
      ))}
      <div className="flex flex-wrap gap-2">
        <Button
          variant="secondary"
          size="sm"
          onClick={() => addTo(path, newRule(STANDARD_FIELDS[0]!))}
        >
          <Plus className="size-3.5" aria-hidden /> {t('filters.addRule')}
        </Button>
        {path.length === 0 && (
          <Button
            variant="ghost"
            size="sm"
            onClick={() => addTo(path, { op: 'or', rules: [newRule(STANDARD_FIELDS[0]!)] })}
          >
            <FolderPlus className="size-3.5" aria-hidden /> {t('filters.addGroup')}
          </Button>
        )}
      </div>
    </div>
  );

  return (
    <Dialog
      open={open}
      onOpenChange={onOpenChange}
      title={t('filters.title')}
      description={t('filters.description')}
      className="sm:max-w-2xl"
      footer={
        <>
          <Button
            variant="ghost"
            className="sm:mr-auto"
            onClick={() => {
              onApply(null);
              onOpenChange(false);
            }}
          >
            {t('filters.clearAll')}
          </Button>
          <Button variant="secondary" onClick={() => onOpenChange(false)}>
            {t('common.cancel')}
          </Button>
          <Button
            onClick={() => {
              const tree = cleanTree(draft);
              onApply(tree.rules.length ? tree : null);
              onOpenChange(false);
            }}
          >
            {t('filters.apply')}
          </Button>
        </>
      }
    >
      {renderGroup(draft, [])}
    </Dialog>
  );
}
