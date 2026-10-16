import {
  BarChart3,
  Contact,
  LayoutDashboard,
  LayoutGrid,
  Settings,
  Upload,
  Users,
  type LucideIcon,
} from 'lucide-react';

import { paths } from '@/routes/paths';
import type { Capability } from '@/types/auth';

export interface NavItem {
  to: string;
  labelKey: string;
  icon: LucideIcon;
  /** Hide the item unless the user has this capability. */
  capability?: Capability;
}

export const workspaceNav: NavItem[] = [
  { to: paths.contacts, labelKey: 'nav.contacts', icon: Contact },
  { to: paths.people, labelKey: 'nav.people', icon: Users },
  { to: paths.dashboard, labelKey: 'nav.dashboard', icon: LayoutDashboard },
  { to: paths.reports, labelKey: 'nav.reports', icon: BarChart3, capability: 'view_reports' },
  { to: paths.imports, labelKey: 'nav.imports', icon: Upload, capability: 'import' },
  { to: paths.apps, labelKey: 'nav.apps', icon: LayoutGrid, capability: 'manage_integrations' },
  { to: paths.settings, labelKey: 'nav.settings', icon: Settings },
];
