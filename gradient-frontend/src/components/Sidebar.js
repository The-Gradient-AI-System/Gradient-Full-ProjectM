import React, { useCallback, useEffect, useMemo, useState } from 'react';
import styled from 'styled-components';
import { FiUser } from 'react-icons/fi';
import { getManagersStatus, resolveAvatarUrl } from '../api/client';
import { useAuth } from '../context/AuthContext';
import { canViewStaffOnlineStatus, isAdmin, ROLE_ADMIN, staffRoleLabel } from '../utils/roles';

const STATUS_POLL_MS = Math.max(
  10000,
  Number.parseInt(process.env.REACT_APP_STATUS_POLL_MS || '30000', 10) || 30000
);

const SidebarContainer = styled.aside`
  width: 140px;
  padding: 0.75rem;
  background: ${({ theme }) => theme.colors.sidebarBackground};
  display: flex;
  flex-direction: column;
  border: 1px solid ${({ theme }) => theme.colors.border};
  border-radius: 16px;
  box-shadow: 0 10px 24px ${({ theme }) => theme.colors.shadow};
  position: sticky;
  top: 1.5rem;
  margin: 1.5rem 1.5rem 1.5rem 0;
  align-self: stretch;
  min-height: calc(100vh - 5rem);
  transition: background 0.3s ease, border-color 0.3s ease, box-shadow 0.3s ease;
`;

const Title = styled.h3`
  color: ${({ theme }) => theme.colors.text};
  margin-bottom: 1.5rem;
  font-weight: 600;
  letter-spacing: 0.3px;
  text-align: center;
`;

const ManagerList = styled.ul`
  list-style: none;
  padding: 0;
  margin: 0;
`;

const EmptyState = styled.p`
  margin: 0.5rem 0;
  color: ${({ theme }) => theme.colors.textSecondary};
  font-size: 0.9rem;
  text-align: center;
  line-height: 1.4;
`;

const ManagerItem = styled.li`
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.5rem;
  margin-bottom: 1.5rem;
  padding: 0.75rem 0.25rem;
  border-radius: 12px;
  background: transparent;
  transition: background 0.2s ease;

  &:hover {
    background: ${({ theme }) => theme.colors.hover};
  }
`;

const Avatar = styled.div`
  width: 60px;
  height: 60px;
  border-radius: 50%;
  background-color: #f1f3f6;
  margin-right: 0;
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 0 0 2px ${({ theme }) => theme.colors.border};
`;

const AvatarImage = styled.img`
  width: 100%;
  height: 100%;
  border-radius: 50%;
  object-fit: cover;
`;

const StatusIndicator = styled.span`
  position: absolute;
  right: -2px;
  bottom: -2px;
  width: 12px;
  height: 12px;
  border-radius: 50%;
  border: 2px solid ${({ theme }) => theme.colors.sidebarBackground};
  background-color: ${props => (props.status === 'online' ? '#21ff00' : props.status === 'away' ? '#9ca3af' : '#dc3545')};
`;

const ManagerInfo = styled.div`
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;

  p {
    margin: 0;
    color: ${({ theme }) => theme.colors.text};
    font-size: 1.1rem;
    font-weight: 600;
    text-align: center;
  }

  small {
    margin-top: 0.15rem;
    font-size: 0.72rem;
    font-weight: 500;
    color: ${({ theme }) => theme.colors.textSecondary};
    text-align: center;
  }
`;

const Sidebar = () => {
  const { user } = useAuth();
  const [managers, setManagers] = useState([]);
  const [loading, setLoading] = useState(false);
  const [errorText, setErrorText] = useState('');

  const canViewStatus = canViewStaffOnlineStatus(user?.role);
  const currentUserId = user?.id;

  const excludeSelfFromManagers = useCallback(
    (list) => {
      if (!isAdmin(user?.role) || currentUserId == null) {
        return list;
      }
      const selfId = Number(currentUserId);
      return list.filter((m) => Number(m.id) !== selfId);
    },
    [user?.role, currentUserId]
  );

  useEffect(() => {
    if (!canViewStatus) return;
    let cancelled = false;

    const loadManagers = async ({ showLoading = false } = {}) => {
      if (showLoading) {
        setLoading(true);
        setErrorText('');
      }
      try {
        const data = await getManagersStatus();
        if (!cancelled) {
          setManagers(excludeSelfFromManagers(data?.managers || []));
        }
      } catch (error) {
        if (!cancelled) {
          setManagers([]);
          setErrorText(error?.message || 'Не вдалося завантажити статуси працівників.');
        }
      } finally {
        if (!cancelled && showLoading) {
          setLoading(false);
        }
      }
    };

    const safeLoad = (options = {}) => {
      if (document.visibilityState !== 'visible') return;
      loadManagers(options);
    };

    safeLoad({ showLoading: true });
    const intervalId = window.setInterval(() => safeLoad(), STATUS_POLL_MS);
    const onVisibilityChange = () => {
      if (document.visibilityState === 'visible') {
        safeLoad();
      }
    };
    document.addEventListener('visibilitychange', onVisibilityChange);

    return () => {
      cancelled = true;
      window.clearInterval(intervalId);
      document.removeEventListener('visibilitychange', onVisibilityChange);
    };
  }, [canViewStatus, currentUserId, user?.role, excludeSelfFromManagers]);

  const preparedManagers = useMemo(
    () =>
      managers.map((member) => ({
        id: member.id,
        name: member.username || member.email || staffRoleLabel(member.role),
        role: member.role,
        avatar: resolveAvatarUrl(member.avatar_url) || '',
        status: member.is_online ? 'online' : 'offline',
      })),
    [managers]
  );

  if (!canViewStatus) {
    return null;
  }

  return (
    <SidebarContainer>
      <Title>Команда</Title>
      {loading ? (
        <EmptyState>Завантаження статусів...</EmptyState>
      ) : errorText ? (
        <EmptyState>{errorText}</EmptyState>
      ) : preparedManagers.length === 0 ? (
        <EmptyState>У системі поки немає менеджерів або адміністраторів.</EmptyState>
      ) : (
        <ManagerList>
          {preparedManagers.map((member) => (
            <ManagerItem key={member.id}>
              <Avatar>
                {member.avatar ? (
                  <AvatarImage src={member.avatar} alt={member.name} />
                ) : (
                  <FiUser size={26} color="#1b1c2f" />
                )}
                <StatusIndicator
                  status={member.status}
                  title={member.status === 'online' ? 'Онлайн' : 'Офлайн'}
                  aria-label={member.status === 'online' ? 'Онлайн' : 'Офлайн'}
                />
              </Avatar>
              <ManagerInfo>
                <p>{member.name}</p>
                {member.role === ROLE_ADMIN && (
                  <small>{staffRoleLabel(member.role)}</small>
                )}
              </ManagerInfo>
            </ManagerItem>
          ))}
        </ManagerList>
      )}
    </SidebarContainer>
  );
};

export default Sidebar;
