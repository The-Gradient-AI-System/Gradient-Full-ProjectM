export const lightTheme = {
  mode: 'light',
  colors: {
    background: '#F4F7FE', // Light grey/blueish background
    surface: '#FFFFFF',
    primary: '#4BA3FF',
    text: '#2B3674',
    textSecondary: '#A3AED0',
    headerBackground: '#FFFFFF',
    sidebarBackground: '#FFFFFF',
    border: 'rgba(0, 0, 0, 0.06)',
    hover: 'rgba(0, 0, 0, 0.04)',
    cardBackground: '#FFFFFF',
    shadow: 'rgba(112, 144, 176, 0.08)',
  }
};

export const darkTheme = {
  mode: 'dark',
  colors: {
    background: '#1a1b2d', // Main body bg from index.css
    surface: '#2A2D3A', // AppContainer bg from App.js (though App.js was #2A2D3A, check index.css #1a1b2d)
    // Wait, App.js AppContainer is #2A2D3A, index.css body is #1a1b2d.
    // Let's stick to what we saw.
    primary: '#4BA3FF',
    text: '#f0f0f0',
    textSecondary: '#a9a9a9',
    headerBackground: 'linear-gradient(180deg, #1b1c2f 0%, #18192b 100%)',
    sidebarBackground: 'rgba(255, 255, 255, 0.04)',
    border: 'rgba(255, 255, 255, 0.06)',
    hover: 'rgba(255, 255, 255, 0.04)',
    cardBackground: '#2b2e42', // Greyish dark blue, softer than before
    shadow: 'rgba(0, 0, 0, 0.2)',
  }
};
