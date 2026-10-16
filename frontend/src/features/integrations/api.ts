import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { useAuth } from '@/features/auth/useAuth';
import { api } from '@/lib/api/client';

export type AppConnectionState = 'connected' | 'error' | 'needs_setup' | 'not_connected';

/** One app's status in this workspace (GET /integrations). Secrets are never returned. */
export interface AppStatus {
  app: string;
  status: AppConnectionState;
  account_label?: string;
  connected_at?: string | null;
  connected_by?: string;
  last_checked_at?: string | null;
  last_error?: string;
  config: Record<string, string>;
  /** Secret fields that are stored (shown as "saved"; leave blank to keep). */
  secrets_set: string[];
  settings?: Record<string, unknown>;
  synced_at?: string | null;
}

export const integrationKeys = { all: ['integrations'] as const };

/** Owner/Admin only; others never call the endpoint. Keyed by app. */
export function useIntegrations() {
  const { can } = useAuth();
  return useQuery({
    queryKey: integrationKeys.all,
    queryFn: () =>
      api
        .get<{ apps: AppStatus[] }>('/integrations')
        .then(
          (r) =>
            Object.fromEntries(r.data.apps.map((a) => [a.app, a])) as Record<string, AppStatus>,
        ),
    enabled: can('manage_integrations'),
    staleTime: 30_000,
  });
}

function useRefresh() {
  const queryClient = useQueryClient();
  return () => queryClient.invalidateQueries({ queryKey: integrationKeys.all });
}

/** Connect or update: the server checks the details with the provider before saving. */
export function useConnectApp(app: string) {
  const refresh = useRefresh();
  return useMutation({
    mutationFn: (values: Record<string, string>) =>
      api.post<AppStatus>(`/integrations/${app}`, { values }).then((r) => r.data),
    onSuccess: refresh,
  });
}

export function useCheckApp(app: string) {
  const refresh = useRefresh();
  return useMutation({
    mutationFn: () => api.post<AppStatus>(`/integrations/${app}/check`).then((r) => r.data),
    onSuccess: refresh,
  });
}

export function useDisconnectApp(app: string) {
  const refresh = useRefresh();
  return useMutation({
    mutationFn: () => api.delete(`/integrations/${app}`),
    onSuccess: refresh,
  });
}

export function isLive(status: AppConnectionState | undefined): boolean {
  return status === 'connected' || status === 'error' || status === 'needs_setup';
}

// --- Exotel ---------------------------------------------------------------------------------------
export interface ExotelNumber {
  id: number;
  phone_number: string;
  friendly_name: string;
  region: string;
  country: string;
  capabilities: { voice?: boolean; sms?: boolean };
  added_manually: boolean;
  is_active: boolean;
  /** When the LMS first saw the number active (stored in UTC). */
  active_since: string;
  last_seen_at: string;
}

/** Calling hours, workspace time zone. days: 0 = Monday. */
export interface CallWindow {
  enabled: boolean;
  days: number[];
  start: string;
  end: string;
}

export interface ExotelSettings {
  default_caller: string;
  auto_call_followups: boolean;
  /** Minutes to wait before calling a new lead (1, 2 or 5). */
  new_lead_delay: number;
  call_window: CallWindow;
  fallback_agent: number | null;
}

export interface ExotelManage {
  numbers: ExotelNumber[];
  refreshed_at: string | null;
  settings: ExotelSettings;
}

export interface AutoCallForm {
  id: number;
  name: string;
  form_id: string;
  leads_received: number;
  auto_call: boolean;
}

export interface AutoCallRow {
  id: number;
  enquiry_id: number;
  enquiry_name: string;
  reason: 'new_lead' | 'followup' | 'status';
  status: string;
  agent: string;
  customer_phone: string;
  scheduled_at: string;
  started_at: string | null;
  duration_seconds: number;
  error: string;
}

const exotelKeys = {
  manage: ['integrations', 'exotel', 'manage'] as const,
  forms: ['integrations', 'exotel', 'forms'] as const,
  calls: ['integrations', 'exotel', 'calls'] as const,
};

export function useExotel() {
  return useQuery({
    queryKey: exotelKeys.manage,
    queryFn: () => api.get<ExotelManage>('/integrations/exotel/manage').then((r) => r.data),
  });
}

function useExotelMutation<T>(fn: (input: T) => Promise<ExotelManage>) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: fn,
    onSuccess: (data) => {
      queryClient.setQueryData(exotelKeys.manage, data);
      void queryClient.invalidateQueries({ queryKey: integrationKeys.all, exact: true });
    },
  });
}

export function useExotelSettings() {
  return useExotelMutation((changes: Partial<ExotelSettings>) =>
    api.patch<ExotelManage>('/integrations/exotel/manage', changes).then((r) => r.data),
  );
}

export function useRefreshExotel() {
  return useExotelMutation(() =>
    api.post<ExotelManage>('/integrations/exotel/refresh').then((r) => r.data),
  );
}

export function useAddExotelNumber() {
  return useExotelMutation((input: { phone_number: string; friendly_name?: string }) =>
    api.post<ExotelManage>('/integrations/exotel/numbers', input).then((r) => r.data),
  );
}

export function useDeleteExotelNumber() {
  return useExotelMutation((id: number) =>
    api.delete<ExotelManage>(`/integrations/exotel/numbers/${id}`).then((r) => r.data),
  );
}

export function useAutoCallForms() {
  return useQuery({
    queryKey: exotelKeys.forms,
    queryFn: () =>
      api
        .get<{ page_name: string; forms: AutoCallForm[] }>('/integrations/exotel/forms')
        .then((r) => r.data),
  });
}

export function useToggleAutoCallForm() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, autoCall }: { id: number; autoCall: boolean }) =>
      api.patch(`/integrations/exotel/forms/${id}`, { auto_call: autoCall }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: exotelKeys.forms }),
  });
}

export function useAutoCalls() {
  return useQuery({
    queryKey: exotelKeys.calls,
    queryFn: () =>
      api.get<{ results: AutoCallRow[] }>('/integrations/exotel/calls').then((r) => r.data.results),
    refetchInterval: 30_000,
  });
}

// --- WhatsApp (Facebook login) -------------------------------------------------------------------------
export interface WhatsAppNumber {
  id: string;
  display_phone_number: string;
  verified_name: string;
  quality_rating: string;
  status?: string;
  /** NOT_APPLICABLE = not registered on the Cloud API yet. */
  platform_type?: string;
}

export interface WhatsAppManage {
  accounts: { id: string; name: string; numbers: WhatsAppNumber[] }[];
  phone_number_id: string;
  token_expires_at: string | null;
  refreshed_at: string | null;
  flow: '' | 'new' | 'coexistence';
  setup_issues: string[];
  two_step_pin: string;
}

const whatsappKey = ['integrations', 'whatsapp', 'manage'] as const;

export function useWhatsApp() {
  return useQuery({
    queryKey: whatsappKey,
    queryFn: () => api.get<WhatsAppManage>('/integrations/whatsapp/manage').then((r) => r.data),
  });
}

function useWhatsAppMutation<T>(fn: (input: T) => Promise<WhatsAppManage>) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: fn,
    onSuccess: (data) => {
      queryClient.setQueryData(whatsappKey, data);
      void queryClient.invalidateQueries({ queryKey: integrationKeys.all, exact: true });
    },
  });
}

export function useChooseWhatsAppNumber() {
  return useWhatsAppMutation((phoneNumberId: string) =>
    api
      .patch<WhatsAppManage>('/integrations/whatsapp/manage', { phone_number_id: phoneNumberId })
      .then((r) => r.data),
  );
}

export function useRegisterWhatsAppNumber() {
  return useWhatsAppMutation((phoneNumberId: string) =>
    api
      .post<WhatsAppManage>(`/integrations/whatsapp/numbers/${phoneNumberId}/register`)
      .then((r) => r.data),
  );
}

export function useRefreshWhatsApp() {
  return useWhatsAppMutation(() =>
    api.post<WhatsAppManage>('/integrations/whatsapp/refresh').then((r) => r.data),
  );
}

// --- Google Sheets -----------------------------------------------------------------------------------
export interface Spreadsheet {
  id: string;
  name: string;
  modified_at: string | null;
  owner: string;
}

export type SheetField = 'name' | 'phone' | 'email';
export type SheetMapping = Partial<Record<SheetField, string>>;

export interface SheetTab {
  title: string;
  rows: number | null;
  headers: string[];
  mapping: SheetMapping;
}

export interface SheetLink {
  id: number;
  /** import: rows become enquiries. export: enquiries are written to the sheet. */
  direction: 'import' | 'export';
  form: number | null;
  form_name: string;
  spreadsheet_id: string;
  spreadsheet_name: string;
  sheet_title: string;
  headers: string[];
  mapping: SheetMapping;
  rows_imported: number;
  last_row: number;
  is_active: boolean;
  last_synced_at: string | null;
  last_error: string;
}

const sheetKeys = {
  spreadsheets: (q: string) => ['integrations', 'sheets', 'files', q] as const,
  tabs: (id: string) => ['integrations', 'sheets', 'tabs', id] as const,
  links: ['integrations', 'sheets', 'links'] as const,
};

export function useSpreadsheets(q: string, enabled: boolean) {
  return useQuery({
    queryKey: sheetKeys.spreadsheets(q),
    queryFn: () =>
      api
        .get<{ results: Spreadsheet[] }>('/integrations/google_sheets/spreadsheets', {
          params: { q: q || undefined },
        })
        .then((r) => r.data.results),
    enabled,
    placeholderData: keepPreviousData,
  });
}

export function useSheetTabs(spreadsheetId: string | null) {
  return useQuery({
    queryKey: sheetKeys.tabs(spreadsheetId ?? ''),
    queryFn: () =>
      api
        .get<{ results: SheetTab[] }>(
          `/integrations/google_sheets/spreadsheets/${spreadsheetId}/tabs`,
        )
        .then((r) => r.data.results),
    enabled: Boolean(spreadsheetId),
  });
}

export function useSheetLinks() {
  return useQuery({
    queryKey: sheetKeys.links,
    queryFn: () =>
      api
        .get<{ results: SheetLink[] }>('/integrations/google_sheets/links')
        .then((r) => r.data.results),
  });
}

function useSheetMutation<T, R>(fn: (input: T) => Promise<R>) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: fn,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: sheetKeys.links });
      void queryClient.invalidateQueries({ queryKey: ['enquiries'] });
    },
  });
}

export function useCreateSheetLink() {
  return useSheetMutation(
    (input: {
      spreadsheet_id: string;
      spreadsheet_name: string;
      sheet_title: string;
      mapping: SheetMapping;
      import_existing: boolean;
    }) =>
      api
        .post<SheetLink & { imported: number }>('/integrations/google_sheets/links', input)
        .then((r) => r.data),
  );
}

/** Send a form's leads (or all enquiries) to a sheet, kept up to date. */
export function useCreateSheetExport() {
  return useSheetMutation(
    (input: { form: number | null; spreadsheet_id?: string; new_title?: string }) =>
      api.post<SheetLink>('/integrations/google_sheets/exports', input).then((r) => r.data),
  );
}

export function useSyncSheetLink() {
  return useSheetMutation((id: number) =>
    api
      .post<SheetLink & { imported: number }>(`/integrations/google_sheets/links/${id}/sync`)
      .then((r) => r.data),
  );
}

export function useUpdateSheetLink() {
  return useSheetMutation(({ id, isActive }: { id: number; isActive: boolean }) =>
    api
      .patch<SheetLink>(`/integrations/google_sheets/links/${id}`, { is_active: isActive })
      .then((r) => r.data),
  );
}

/** Send another form's leads to this sheet (the sheet is rewritten). */
export function useChangeSheetForm() {
  return useSheetMutation(({ id, form }: { id: number; form: number | null }) =>
    api.patch<SheetLink>(`/integrations/google_sheets/links/${id}`, { form }).then((r) => r.data),
  );
}

export function useDeleteSheetLink() {
  return useSheetMutation((id: number) => api.delete(`/integrations/google_sheets/links/${id}`));
}
