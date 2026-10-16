/**
 * Filter builder model. Mirrors the backend whitelist in apps/enquiries/filters.py,
 * so the UI only offers field/operator pairs the API accepts.
 */
import type {
  CustomField,
  FieldType,
  FilterGroup,
  FilterRule,
  SavedViewFilters,
  Source,
} from '@/types/crm';

export type FieldKind = 'text' | 'status' | 'owner' | 'source' | 'bool' | 'datetime' | FieldType;

export interface FieldDef {
  id: string; // "name" or "cf:<key>"
  kind: FieldKind;
  labelKey?: string; // standard fields
  label?: string; // custom fields
  options?: string[];
}

export const STANDARD_FIELDS: FieldDef[] = [
  { id: 'name', kind: 'text', labelKey: 'filters.fields.name' },
  { id: 'phone', kind: 'text', labelKey: 'filters.fields.phone' },
  { id: 'email', kind: 'text', labelKey: 'filters.fields.email' },
  { id: 'status', kind: 'status', labelKey: 'filters.fields.status' },
  { id: 'owner', kind: 'owner', labelKey: 'filters.fields.owner' },
  { id: 'source', kind: 'source', labelKey: 'filters.fields.source' },
  { id: 'campaign', kind: 'text', labelKey: 'filters.fields.campaign' },
  { id: 'adset', kind: 'text', labelKey: 'filters.fields.adset' },
  { id: 'ad', kind: 'text', labelKey: 'filters.fields.ad' },
  { id: 'form', kind: 'text', labelKey: 'filters.fields.form' },
  { id: 'is_repeat', kind: 'bool', labelKey: 'filters.fields.isRepeat' },
  { id: 'created_at', kind: 'datetime', labelKey: 'filters.fields.createdAt' },
  { id: 'updated_at', kind: 'datetime', labelKey: 'filters.fields.updatedAt' },
];

export function customFieldDefs(fields: CustomField[]): FieldDef[] {
  return fields.map((f) => ({
    id: `cf:${f.key}`,
    kind: f.type,
    label: f.label,
    options: f.options,
  }));
}

export const OPERATORS: Record<FieldKind, string[]> = {
  text: ['contains', 'not_contains', 'eq', 'neq', 'starts_with', 'is_empty', 'is_not_empty'],
  status: ['in', 'not_in'],
  owner: ['in', 'not_in', 'is_empty', 'is_not_empty'],
  source: ['in', 'not_in'],
  bool: ['is_true', 'is_false'],
  datetime: ['today', 'last_days', 'on', 'before', 'after', 'between'],
  number: ['eq', 'neq', 'gt', 'gte', 'lt', 'lte', 'between', 'is_empty', 'is_not_empty'],
  currency: ['eq', 'neq', 'gt', 'gte', 'lt', 'lte', 'between', 'is_empty', 'is_not_empty'],
  date: ['today', 'last_days', 'on', 'before', 'after', 'between', 'is_empty', 'is_not_empty'],
  dropdown: ['in', 'not_in', 'is_empty', 'is_not_empty'],
  multi_select: ['contains_any', 'contains', 'is_empty', 'is_not_empty'],
  checkbox: ['is_true', 'is_false'],
};

/** What kind of input an operator needs. */
export type ValueInput =
  | 'none'
  | 'text'
  | 'number'
  | 'number_range'
  | 'date'
  | 'date_range'
  | 'days'
  | 'statuses'
  | 'owners'
  | 'sources'
  | 'options';

const NO_VALUE = new Set(['is_empty', 'is_not_empty', 'is_true', 'is_false', 'today']);

export function valueInputFor(kind: FieldKind, operator: string): ValueInput {
  if (NO_VALUE.has(operator)) return 'none';
  if (operator === 'last_days') return 'days';
  if (kind === 'status') return 'statuses';
  if (kind === 'owner') return 'owners';
  if (kind === 'source') return 'sources';
  if (kind === 'dropdown' || kind === 'multi_select') return 'options';
  if (kind === 'datetime' || kind === 'date') return operator === 'between' ? 'date_range' : 'date';
  if (kind === 'number' || kind === 'currency')
    return operator === 'between' ? 'number_range' : 'number';
  return 'text';
}

export function defaultValue(input: ValueInput): unknown {
  switch (input) {
    case 'none':
      return undefined;
    case 'days':
      return 7;
    case 'number_range':
    case 'date_range':
      return ['', ''];
    case 'statuses':
    case 'owners':
    case 'sources':
    case 'options':
      return [];
    default:
      return '';
  }
}

export function newRule(field: FieldDef): FilterRule {
  const operator = OPERATORS[field.kind][0]!;
  return { field: field.id, operator, value: defaultValue(valueInputFor(field.kind, operator)) };
}

export function emptyGroup(op: 'and' | 'or' = 'and'): FilterGroup {
  return { op, rules: [] };
}

export function isGroup(node: FilterRule | FilterGroup): node is FilterGroup {
  return 'rules' in node;
}

export function countRules(node: FilterRule | FilterGroup | null | undefined): number {
  if (!node) return 0;
  if (isGroup(node)) return node.rules.reduce((sum, child) => sum + countRules(child), 0);
  return 1;
}

function isComplete(rule: FilterRule): boolean {
  const v = rule.value;
  if (v === undefined) return true;
  if (Array.isArray(v)) return v.length > 0 && v.every((x) => x !== '' && x !== null);
  return v !== '' && v !== null;
}

/** Drop unfinished rules and empty groups before sending to the API. */
export function cleanTree(group: FilterGroup): FilterGroup {
  const rules: (FilterRule | FilterGroup)[] = [];
  for (const node of group.rules) {
    if (isGroup(node)) {
      const child = cleanTree(node);
      if (child.rules.length) rules.push(child);
    } else if (isComplete(node)) {
      rules.push(node);
    }
  }
  return { op: group.op, rules };
}

/**
 * Everything currently applied (base saved view + quick filters + builder) as one
 * tree, so "Save as view" keeps exactly what the user sees.
 */
export function toSavableFilters(
  params: {
    q?: string;
    status?: number[];
    owner?: string[];
    source?: Source[];
    filter?: FilterGroup | null;
  },
  base: FilterGroup | null,
): SavedViewFilters {
  const rules: (FilterRule | FilterGroup)[] = [];
  if (base && countRules(base)) rules.push(base);
  if (params.status?.length) rules.push({ field: 'status', operator: 'in', value: params.status });
  if (params.owner?.length) rules.push({ field: 'owner', operator: 'in', value: params.owner });
  if (params.source?.length) rules.push({ field: 'source', operator: 'in', value: params.source });
  if (params.filter && countRules(params.filter)) rules.push(params.filter);
  return { filter: rules.length ? { op: 'and', rules } : null, q: params.q ?? '' };
}
