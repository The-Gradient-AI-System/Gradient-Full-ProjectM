import React, { createContext, useState, useEffect } from 'react';

export const ThemeContext = createContext();

export const ThemeProviderWrapper = ({ children }) => {
  const [themeMode, setThemeMode] = useState('dark');

  useEffect(() => {
    const savedTheme = localStorage.getItem('theme');
    if (savedTheme) {
      setThemeMode(savedTheme);
    }
  }, []);

  const toggleTheme = () => {
    const newTheme = themeMode === 'light' ? 'dark' : 'light';
    setThemeMode(newTheme);
    localStorage.setItem('theme', newTheme);
  };

  return (
    <ThemeContext.Provider value={{ themeMode, toggleTheme }}>
      {children}
    </ThemeContext.Provider>
  );
};
