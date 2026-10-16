import { api } from '@/lib/api/client';
import type { AuthResponse, Role, Session } from '@/types/auth';

import type {
  AcceptInviteValues,
  ForgotPasswordValues,
  LoginValues,
  ResetPasswordValues,
  SignupValues,
} from './schemas';

export interface InvitePreview {
  email: string;
  role: Role;
  workspace_name: string;
  invited_by: string | null;
  has_account: boolean;
}

export const authApi = {
  signup: (values: SignupValues) =>
    api.post<AuthResponse>('/auth/signup', values).then((r) => r.data),
  login: (values: LoginValues & { tenant_id?: number }) =>
    api.post<AuthResponse>('/auth/login', values).then((r) => r.data),
  logout: (refresh: string) => api.post('/auth/logout', { refresh }),
  me: () => api.get<Session>('/auth/me').then((r) => r.data),
  switchWorkspace: (tenant_id: number) =>
    api.post<AuthResponse>('/auth/switch-workspace', { tenant_id }).then((r) => r.data),
  forgotPassword: (values: ForgotPasswordValues) => api.post('/auth/forgot-password', values),
  resetPassword: (values: ResetPasswordValues & { uid: string; token: string }) =>
    api.post('/auth/reset-password', {
      uid: values.uid,
      token: values.token,
      password: values.password,
    }),
  invitePreview: (token: string) =>
    api.get<InvitePreview>('/auth/accept-invite', { params: { token } }).then((r) => r.data),
  acceptInvite: (values: AcceptInviteValues & { token: string }) =>
    api.post<AuthResponse>('/auth/accept-invite', values).then((r) => r.data),
};
