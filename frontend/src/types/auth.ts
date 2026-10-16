export const ROLES = ['owner', 'admin', 'manager', 'agent', 'viewer'] as const;
export type Role = (typeof ROLES)[number];

/** Mirrors `apps/permissions/roles.py` on the backend. */
export type Capability =
  | 'manage_billing'
  | 'manage_users'
  | 'manage_settings'
  | 'manage_meta'
  | 'manage_integrations'
  | 'edit_enquiries'
  | 'delete_enquiries'
  | 'reassign_owners'
  | 'import'
  | 'export'
  | 'view_reports';

export type DedupeKey = 'phone' | 'email';

export interface Workspace {
  id: number;
  name: string;
  timezone: string;
  dedupe_key: DedupeKey;
  default_country: string;
  plan: string;
}

export interface WorkspaceSummary {
  id: number;
  name: string;
  role: Role;
}

export interface SessionUser {
  id: number;
  email: string;
  full_name: string;
}

export interface Session {
  user: SessionUser;
  workspace: Workspace;
  role: Role;
  capabilities: Capability[];
  workspaces: WorkspaceSummary[];
}

export interface AuthResponse {
  access: string;
  refresh: string;
  session: Session;
}
