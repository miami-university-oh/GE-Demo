import React from 'react';
import { useNavigate } from 'react-router-dom';

export const Header: React.FC = () => {
  const navigate = useNavigate();

  const handleLogout = () => {
    localStorage.removeItem('auth');
    navigate('/login');
  };

  return (
    <header className="header">

      <button 
        onClick={handleLogout}
        style={{
          background: 'none',
          border: 'none',
          color: 'var(--text-muted)',
          fontFamily: 'var(--font-mono)',
          fontSize: 10,
          cursor: 'pointer'
        }}
      >
        LOGOUT
      </button>
    </header>
  );
};
