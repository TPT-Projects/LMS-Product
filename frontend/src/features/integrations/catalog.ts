import { FileSpreadsheet, MessageCircle, PhoneCall, type LucideIcon } from 'lucide-react';

/**
 * Every app shown in Apps. Names, descriptions, features and setup steps are in
 * `locales/en.json` under `apps.catalog.<key>`. "available" apps can be connected now;
 * the backend (`apps/integrations` and Meta) decides what really connects.
 */
export const CATEGORIES = ['lead_sources', 'messaging', 'calling'] as const;
export type Category = (typeof CATEGORIES)[number];

export interface AppLogoSpec {
  bg: string;
  icon?: LucideIcon;
  text?: string;
}

export interface AppField {
  key: string;
  type: 'text' | 'secret' | 'select';
  options?: string[];
  optional?: boolean;
}

export interface AppDef {
  key: string;
  category: Category;
  logo: AppLogoSpec;
  availability: 'available' | 'coming_soon';
  /**
   * meta: Facebook login popup for lead ads (Page, forms, sync).
   * embedded: WhatsApp Embedded Signup (new number or WhatsApp Business app number).
   * facebook / google: login popup, then the app's Manage page.
   * credentials: a short form, checked with the provider.
   */
  connect?: 'meta' | 'embedded' | 'facebook' | 'google' | 'credentials';
  fields?: AppField[];
  docsUrl?: string;
  /** Shown in the "Get started" checklist. */
  recommended?: boolean;
}

export const APPS: AppDef[] = [
  {
    key: 'meta',
    category: 'lead_sources',
    logo: { bg: '#1877F2', text: 'f' },
    availability: 'available',
    connect: 'meta',
    recommended: true,
  },
  {
    key: 'whatsapp',
    category: 'messaging',
    logo: { bg: '#25D366', icon: MessageCircle },
    availability: 'available',
    connect: 'embedded',
    recommended: true,
  },
  {
    key: 'exotel',
    category: 'calling',
    logo: { bg: '#1D4ED8', icon: PhoneCall },
    availability: 'available',
    connect: 'credentials',
    fields: [
      { key: 'region', type: 'select', options: ['in', 'sg'] },
      { key: 'account_sid', type: 'text' },
      { key: 'api_key', type: 'text' },
      { key: 'api_token', type: 'secret' },
    ],
    docsUrl: 'https://developer.exotel.com/api',
    recommended: true,
  },
  {
    key: 'google_sheets',
    category: 'lead_sources',
    logo: { bg: '#0F9D58', icon: FileSpreadsheet },
    availability: 'available',
    connect: 'google',
  },
  // --- coming soon -------------------------------------------------------------------
  {
    key: 'google_ads',
    category: 'lead_sources',
    logo: { bg: '#4285F4', text: 'G' },
    availability: 'coming_soon',
  },
  {
    key: 'linkedin',
    category: 'lead_sources',
    logo: { bg: '#0A66C2', text: 'in' },
    availability: 'coming_soon',
  },
];

export function findApp(key: string | undefined): AppDef | undefined {
  return APPS.find((app) => app.key === key);
}

/** Apps with their own Manage section once connected. */
export const MANAGED_APPS = new Set(['whatsapp', 'exotel', 'google_sheets']);
