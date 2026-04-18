import React, { useContext } from 'react';
import styled from 'styled-components';
import { FiSun, FiMoon } from 'react-icons/fi';
import { ThemeContext } from '../context/ThemeContext';

const ToggleButton = styled.button`
  background: ${({ theme }) => theme.colors.hover};
  border: 1px solid ${({ theme }) => theme.colors.border};
  color: ${({ theme }) => (theme.mode === 'dark' ? '#f0f0f0' : '#fdb813')};
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0.5rem;
  border-radius: 50%;
  transition: all 0.3s ease;
  margin-right: 1rem; /* Space from other header elements if needed, or margin-left if on the right */

  &:hover {
    background: ${({ theme }) => theme.colors.border};
    transform: scale(1.1);
  }

  svg {
    font-size: 1.2rem;
  }
`;

const ThemeToggle = () => {
  const { themeMode, toggleTheme } = useContext(ThemeContext);

  return (
    <ToggleButton onClick={toggleTheme} title={themeMode === 'light' ? "Switch to Dark Mode" : "Switch to Light Mode"}>
      {themeMode === 'light' ? <FiMoon color="#2B3674" /> : <FiSun color="#fdb813" />}
    </ToggleButton>
  );
};

export default ThemeToggle;
