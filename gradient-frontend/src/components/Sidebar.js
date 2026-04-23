import React, { useEffect, useMemo, useState } from 'react';
import styled from 'styled-components';
import { FiUser } from 'react-icons/fi';
import { getManagers } from '../api/client';
import { useAuth } from '../context/AuthContext';

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
`;

const Sidebar = () => {
  const { user } = useAuth();
  const [managers, setManagers] = useState([]);
  const [loading, setLoading] = useState(false);
  const [errorText, setErrorText] = useState('');

  const isAdmin = user?.role === 'admin';

  useEffect(() => {
    if (!isAdmin) return;
    let cancelled = false;
    const loadManagers = async () => {
      setLoading(true);
      setErrorText('');
      try {
        const data = await getManagers();
        if (!cancelled) {
          setManagers(data?.managers || []);
        }
      } catch (error) {
        if (!cancelled) {
          setManagers([]);
          setErrorText(error?.message || 'Не вдалося завантажити менеджерів.');
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    };
    loadManagers();
    return () => {
      cancelled = true;
    };
  }, [isAdmin]);

  const preparedManagers = useMemo(
    () =>
      managers.map((manager) => ({
        id: manager.id,
        name: manager.username || manager.email || 'Менеджер',
        avatar: manager.avatar_url || '',
        status: manager.is_active ? 'online' : 'away',
      })),
    [managers]
  );

  if (!isAdmin) {
    return null;
  }

  return (
    <SidebarContainer>
      <Title>Менеджери</Title>
      {loading ? (
        <EmptyState>Завантаження менеджерів...</EmptyState>
      ) : errorText ? (
        <EmptyState>{errorText}</EmptyState>
      ) : preparedManagers.length === 0 ? (
        <EmptyState>У базі даних поки немає менеджерів.</EmptyState>
      ) : (
        <ManagerList>
          {preparedManagers.map((manager) => (
            <ManagerItem key={manager.id}>
              <Avatar>
                {manager.avatar ? (
                  <AvatarImage src={manager.avatar} alt={manager.name} />
                ) : (
                  <FiUser size={26} color="#1b1c2f" />
                )}
                <StatusIndicator status={manager.status} />
              </Avatar>
              <ManagerInfo>
                <p>{manager.name}</p>
              </ManagerInfo>
            </ManagerItem>
          ))}
        </ManagerList>
      )}
    </SidebarContainer>
  );
};

export default Sidebar;
