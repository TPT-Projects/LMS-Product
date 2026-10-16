/** Types for the CRM API (enquiries, contacts, statuses, custom fields, views). */

export type StatusColor = 'gray' | 'blue' | 'amber' | 'violet' | 'green' | 'red';

export interface StatusRef {
  id: number;
  name: string;
  color: StatusColor;
  is_closed: boolean;
}

export interface Status extends StatusRef {
  order: number;
  is_default: boolean;
  is_won: boolean;
}

export interface UserRef {
  id: number;
  full_name: string;
  email: string;
}

export type Source = 'manual' | 'meta' | 'import';
export const SOURCES: Source[] = ['manual', 'meta', 'import'];

export type CustomValue = string | number | boolean | string[] | null;

export interface Enquiry {
  id: number;
  name: string;
  phone: string;
  phone_e164: string;
  email: string;
  status: StatusRef;
  primary_owner: UserRef | null;
  source: Source;
  campaign_name: string;
  adset_name: string;
  ad_name: string;
  form_id: string;
  is_repeat: boolean;
  contact_id: number;
  secondary_owners: UserRef[];
  next_followup_at: string | null;
  /** Earliest open follow-up (drives the Action badge). */
  /** The latest call (logged or Exotel auto-call): shown when nothing is scheduled. */
  last_call?: { at: string; outcome: string } | null;
  next_followup: {
    id: number | null;
    title: string;
    due_at: string;
    /** Exotel auto-call of it: no_answer / busy / failed = "call not connected". */
    auto_call_status?: string | null;
  } | null;
  custom_fields: Record<string, CustomValue>;
  created_at: string;
  updated_at: string;
}

export interface EnquiryDetail extends Enquiry {
  leadgen_id: string | null;
  created_by: UserRef | null;
  contact: {
    id: number;
    name: string;
    phone_e164: string | null;
    email: string | null;
    enquiry_count: number;
  };
  permissions: { can_edit: boolean; can_delete: boolean; can_reassign: boolean };
}

export interface Contact {
  id: number;
  name: string;
  phone_e164: string | null;
  email: string | null;
  enquiry_count: number;
  /** Status of the contact's latest enquiry. */
  status: StatusRef | null;
  created_at: string;
  updated_at: string;
}

export interface ContactDetail extends Contact {
  enquiries: Enquiry[];
}

export interface Note {
  id: number;
  body: string;
  has_audio: boolean;
  audio_content_type: string;
  audio_duration_seconds: number | null;
  author: UserRef | null;
  created_at: string;
}

export const CALL_OUTCOMES = [
  'connected',
  'no_answer',
  'busy',
  'callback_requested',
  'not_interested',
  'wrong_number',
] as const;
export type CallOutcome = (typeof CALL_OUTCOMES)[number];

export interface CallLog {
  id: number;
  outcome: CallOutcome;
  duration_seconds: number;
  notes: string;
  called_at: string;
  user: UserRef | null;
  provider: string | null;
}

export interface FollowUp {
  id: number;
  title: string;
  due_at: string;
  assignee: UserRef | null;
  done_at: string | null;
  is_done: boolean;
  /** Exotel auto-call of this scheduled call: pending, started, cancelled, ... or null. */
  auto_call_status: string | null;
  created_at: string;
}

export interface Attachment {
  id: number;
  file_name: string;
  size: number;
  content_type: string;
  uploaded_by: UserRef | null;
  created_at: string;
}

export interface ActivityEvent {
  id: string;
  type: string;
  actor: { type: 'user' | 'system'; id: number | null; name: string };
  created_at: string;
  details: Record<string, unknown>;
}

export interface FormResponse {
  form_id: string;
  campaign_name?: string;
  created_time?: string;
  answers: { question: string; label: string; values: string[]; display: string }[];
}

export const FIELD_TYPES = [
  'text',
  'number',
  'currency',
  'date',
  'dropdown',
  'multi_select',
  'checkbox',
] as const;
export type FieldType = (typeof FIELD_TYPES)[number];

export interface CustomField {
  id: number;
  key: string;
  label: string;
  type: FieldType;
  options: string[];
  is_required: boolean;
  is_active: boolean;
  order: number;
}

// --- filters (mirror apps/enquiries/filters.py) --------------------------------------
export interface FilterRule {
  field: string;
  operator: string;
  value?: unknown;
}

export interface FilterGroup {
  op: 'and' | 'or';
  rules: (FilterRule | FilterGroup)[];
}

export interface SavedViewFilters {
  filter?: FilterGroup | null;
  q?: string;
}

export interface SavedView {
  id: number;
  name: string;
  filters: SavedViewFilters;
  sort: string;
  is_shared: boolean;
  owner: { id: number; full_name: string };
  is_owner: boolean;
  is_pinned: boolean;
  created_at: string;
  updated_at: string;
}

export interface ViewCounts {
  system: Record<string, number>;
  saved: Record<string, number>;
}

export interface SearchResults {
  q: string;
  enquiries: {
    id: number;
    name: string;
    phone_e164: string;
    email: string;
    campaign_name: string;
    status: { id: number; name: string; color: StatusColor };
    created_at: string;
  }[];
  contacts: {
    id: number;
    name: string;
    phone_e164: string | null;
    email: string | null;
    enquiry_count: number;
  }[];
}
