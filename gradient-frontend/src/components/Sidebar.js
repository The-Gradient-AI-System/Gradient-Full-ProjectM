import React from 'react';
import styled from 'styled-components';
import { FiUser } from 'react-icons/fi';

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

const managers = [
  { name: 'Ярослав Коваль', status: 'online' },
  { name: 'Олексій Крупа', status: 'online' },
  { name: 'Анна Вовк', status: 'offline' },
  { name: 'Вікторія Шишка', status: 'away' },
];

const Sidebar = () => {
  return (
    <SidebarContainer>
      <Title>Менеджери</Title>
      <ManagerList>
        {managers.map((manager, index) => (
          <ManagerItem key={index}>
            <Avatar>
              <FiUser size={26} color="#1b1c2f" />
              <StatusIndicator status={manager.status} />
            </Avatar>
            <ManagerInfo>
              <p>{manager.name}</p>
            </ManagerInfo>
          </ManagerItem>
        ))}
      </ManagerList>
    </SidebarContainer>
  );
};

export default Sidebar;
