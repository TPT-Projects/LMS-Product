import { describe, expect, it } from 'vitest';

import { assignableRoles, canChangeRoleOf } from './roles';

describe('role rules (mirror the API)', () => {
  it('only an owner can give the owner role', () => {
    expect(assignableRoles('owner')).toContain('owner');
    expect(assignableRoles('admin')).toEqual(['admin', 'manager', 'agent', 'viewer']);
  });

  it('nobody changes their own role, admins cannot touch owners', () => {
    expect(canChangeRoleOf('owner', 'agent', true)).toBe(false);
    expect(canChangeRoleOf('admin', 'owner', false)).toBe(false);
    expect(canChangeRoleOf('admin', 'agent', false)).toBe(true);
  });
});
