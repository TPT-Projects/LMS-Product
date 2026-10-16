import { ROLES, type Role } from '@/types/auth';

const RANK: Record<Role, number> = { owner: 50, admin: 40, manager: 30, agent: 20, viewer: 10 };

/** Roles the actor may give (mirrors the backend rule: never above your own; only an Owner gives Owner). */
export function assignableRoles(actor: Role): Role[] {
  return ROLES.filter(
    (role) => RANK[role] <= RANK[actor] && (role !== 'owner' || actor === 'owner'),
  );
}

/** Whether the actor may change the target's role at all. */
export function canChangeRoleOf(actor: Role, target: Role, isSelf: boolean): boolean {
  if (isSelf) return false;
  if (target === 'owner' && actor !== 'owner') return false;
  return RANK[target] <= RANK[actor];
}
