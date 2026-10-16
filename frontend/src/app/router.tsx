import { BarChart3, LayoutDashboard } from 'lucide-react';
import { lazy, Suspense } from 'react';
import { createBrowserRouter, Navigate, Outlet } from 'react-router-dom';

import { AppShell } from '@/components/layout/AppShell';
import { FullPageSpinner, Spinner } from '@/components/ui';
import { GuestRoute, ProtectedRoute, RequireCapability } from '@/routes/guards';
import { paths } from '@/routes/paths';

import NotFoundPage from './NotFoundPage';

// Pages are split into their own chunks so the first load stays small.
const LoginPage = lazy(() => import('@/features/auth/pages/LoginPage'));
const SignupPage = lazy(() => import('@/features/auth/pages/SignupPage'));
const ForgotPasswordPage = lazy(() => import('@/features/auth/pages/ForgotPasswordPage'));
const ResetPasswordPage = lazy(() => import('@/features/auth/pages/ResetPasswordPage'));
const AcceptInvitePage = lazy(() => import('@/features/auth/pages/AcceptInvitePage'));
const EnquiriesPage = lazy(() => import('@/features/enquiries/pages/EnquiriesPage'));
const EnquiryDetailPage = lazy(() => import('@/features/enquiries/pages/EnquiryDetailPage'));
const ContactsPage = lazy(() => import('@/features/contacts/pages/ContactsPage'));
const ContactDetailPage = lazy(() => import('@/features/contacts/pages/ContactDetailPage'));
const ViewsPage = lazy(() => import('@/features/views/pages/ViewsPage'));
const ImportsPage = lazy(() => import('@/features/imports/pages/ImportsPage'));
const ImportWizardPage = lazy(() => import('@/features/imports/pages/ImportWizardPage'));
const ImportDetailPage = lazy(() => import('@/features/imports/pages/ImportDetailPage'));
const AppsMarketplacePage = lazy(() => import('@/features/integrations/pages/AppsMarketplacePage'));
const PeoplePage = lazy(() => import('@/features/users/pages/PeoplePage'));
const AppDetailPage = lazy(() => import('@/features/integrations/pages/AppDetailPage'));
const MetaSettingsPage = lazy(() => import('@/features/meta/pages/MetaSettingsPage'));
const MetaSetupPage = lazy(() => import('@/features/meta/pages/MetaSetupPage'));
const MetaOAuthDonePage = lazy(() => import('@/features/meta/pages/MetaOAuthDonePage'));
const MetaFormMappingPage = lazy(() => import('@/features/meta/pages/MetaFormMappingPage'));
const NotificationsPage = lazy(() => import('@/features/notifications/pages/NotificationsPage'));
const StatusesSettingsPage = lazy(() => import('@/features/statuses/pages/StatusesSettingsPage'));
const CustomFieldsSettingsPage = lazy(
  () => import('@/features/customfields/pages/CustomFieldsSettingsPage'),
);
const ComingSoonPage = lazy(() => import('@/features/placeholders/ComingSoonPage'));
const SettingsLayout = lazy(() => import('@/features/settings/SettingsLayout'));
const WorkspaceSettingsPage = lazy(
  () => import('@/features/workspace/pages/WorkspaceSettingsPage'),
);
const UsersPage = lazy(() => import('@/features/users/pages/UsersPage'));
const TeamsPage = lazy(() => import('@/features/teams/pages/TeamsPage'));

function PageSuspense() {
  return (
    <Suspense
      fallback={
        <div className="flex justify-center py-20 text-fg-muted">
          <Spinner />
        </div>
      }
    >
      <Outlet />
    </Suspense>
  );
}

function AuthSuspense() {
  return (
    <Suspense fallback={<FullPageSpinner />}>
      <Outlet />
    </Suspense>
  );
}

export const router = createBrowserRouter([
  {
    element: <AuthSuspense />,
    children: [
      {
        element: <GuestRoute />,
        children: [
          { path: paths.login, element: <LoginPage /> },
          { path: paths.signup, element: <SignupPage /> },
          { path: paths.forgotPassword, element: <ForgotPasswordPage /> },
          { path: paths.resetPassword, element: <ResetPasswordPage /> },
        ],
      },
      // Reachable whether or not someone is logged in.
      { path: paths.acceptInvite, element: <AcceptInvitePage /> },
      // The Facebook login popup lands here, then reports to the main window and closes.
      { path: paths.metaOAuthDone, element: <MetaOAuthDonePage /> },
    ],
  },
  {
    element: <ProtectedRoute />,
    children: [
      {
        element: <AppShell />,
        children: [
          {
            element: <PageSuspense />,
            children: [
              { index: true, element: <Navigate to={`${paths.enquiries}?view=all`} replace /> },
              { path: paths.enquiries, element: <EnquiriesPage /> },
              { path: `${paths.enquiries}/:id`, element: <EnquiryDetailPage /> },
              { path: paths.contacts, element: <ContactsPage /> },
              { path: `${paths.contacts}/:id`, element: <ContactDetailPage /> },
              { path: paths.views, element: <ViewsPage /> },
              {
                path: paths.dashboard,
                element: (
                  <ComingSoonPage
                    icon={LayoutDashboard}
                    titleKey="nav.dashboard"
                    descriptionKey="dashboard.description"
                    emptyKey="dashboard.empty"
                  />
                ),
              },
              {
                path: paths.reports,
                element: (
                  <RequireCapability capability="view_reports">
                    <ComingSoonPage
                      icon={BarChart3}
                      titleKey="nav.reports"
                      descriptionKey="reports.description"
                      emptyKey="reports.empty"
                    />
                  </RequireCapability>
                ),
              },
              {
                path: paths.imports,
                element: (
                  <RequireCapability capability="import">
                    <ImportsPage />
                  </RequireCapability>
                ),
              },
              {
                path: paths.importNew,
                element: (
                  <RequireCapability capability="import">
                    <ImportWizardPage />
                  </RequireCapability>
                ),
              },
              {
                path: `${paths.imports}/:id`,
                element: (
                  <RequireCapability capability="import">
                    <ImportDetailPage />
                  </RequireCapability>
                ),
              },
              { path: paths.notifications, element: <NotificationsPage /> },
              { path: paths.people, element: <PeoplePage /> },
              {
                path: paths.apps,
                element: (
                  <RequireCapability capability="manage_integrations">
                    <AppsMarketplacePage />
                  </RequireCapability>
                ),
              },
              {
                path: `${paths.apps}/:app`,
                element: (
                  <RequireCapability capability="manage_integrations">
                    <AppDetailPage />
                  </RequireCapability>
                ),
              },
              {
                path: paths.settings,
                element: <SettingsLayout />,
                children: [
                  { index: true, element: <Navigate to={paths.settingsWorkspace} replace /> },
                  { path: paths.settingsWorkspace, element: <WorkspaceSettingsPage /> },
                  { path: paths.settingsUsers, element: <UsersPage /> },
                  { path: paths.settingsTeams, element: <TeamsPage /> },
                  { path: paths.settingsStatuses, element: <StatusesSettingsPage /> },
                  { path: paths.settingsCustomFields, element: <CustomFieldsSettingsPage /> },
                  {
                    path: paths.settingsMeta,
                    element: (
                      <RequireCapability capability="manage_meta">
                        <MetaSettingsPage />
                      </RequireCapability>
                    ),
                  },
                  {
                    path: paths.settingsMetaSetup,
                    element: (
                      <RequireCapability capability="manage_meta">
                        <MetaSetupPage />
                      </RequireCapability>
                    ),
                  },
                  {
                    path: `${paths.settingsMeta}/forms/:id`,
                    element: (
                      <RequireCapability capability="manage_meta">
                        <MetaFormMappingPage />
                      </RequireCapability>
                    ),
                  },
                ],
              },
              { path: '*', element: <NotFoundPage /> },
            ],
          },
        ],
      },
    ],
  },
]);
