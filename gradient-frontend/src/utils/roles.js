export const ROLE_OWNER = 'owner';
export const ROLE_ADMIN = 'admin';
export const ROLE_MANAGER = 'manager';

export const isOwner = (role) => role === ROLE_OWNER;

export const isAdmin = (role) => role === ROLE_ADMIN;

export const canManageManagers = (role) =>
  [ROLE_OWNER, ROLE_ADMIN].includes(role);

export const canAccessSettings = (role) =>
  [ROLE_OWNER, ROLE_ADMIN].includes(role);

export const canEditPrompts = (role) => role === ROLE_OWNER;

export const canViewStaffOnlineStatus = (role) =>
  [ROLE_OWNER, ROLE_ADMIN].includes(role);

export const roleDisplayLabel = (role) => {
  if (role === ROLE_OWNER) return 'Власник';
  if (role === ROLE_ADMIN) return 'Адміністратор';
  if (role === ROLE_MANAGER) return 'Менеджер';
  return role || '';
};

export const staffRoleLabel = (role) => {
  if (role === ROLE_ADMIN) return 'Адміністратор';
  return 'Менеджер';
};
