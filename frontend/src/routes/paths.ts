/** Every URL in the app, in one place. */
export const paths = {
  login: '/login',
  signup: '/signup',
  forgotPassword: '/forgot-password',
  resetPassword: '/reset-password',
  acceptInvite: '/accept-invite',

  home: '/',
  enquiries: '/enquiries',
  contacts: '/contacts',
  dashboard: '/dashboard',
  reports: '/reports',
  imports: '/imports',
  importNew: '/imports/new',
  notifications: '/notifications',
  apps: '/apps',
  people: '/users',
  views: '/views',

  settings: '/settings',
  settingsWorkspace: '/settings/workspace',
  settingsUsers: '/settings/users',
  settingsTeams: '/settings/teams',
  settingsStatuses: '/settings/statuses',
  settingsCustomFields: '/settings/custom-fields',
  settingsMeta: '/settings/integrations/meta',
  settingsMetaSetup: '/settings/integrations/meta/setup',
  metaOAuthDone: '/meta/oauth-done',
} as const;

/** System Smart Views (spec section 8). Filtering happens on the server. */
export const smartViews = [
  { id: 'all', labelKey: 'nav.views.all' },
  { id: 'mine', labelKey: 'nav.views.mine' },
  { id: 'unassigned', labelKey: 'nav.views.unassigned' },
  { id: 'calls-today', labelKey: 'nav.views.callsToday' },
] as const;

export type SmartViewId = (typeof smartViews)[number]['id'];
