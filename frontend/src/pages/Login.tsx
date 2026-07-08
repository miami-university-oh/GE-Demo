import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';

export const Login: React.FC = () => {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const navigate = useNavigate();

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (username === 'admin' && password === 'makino2024') {
      localStorage.setItem('auth', 'true');
      navigate('/');
    } else {
      setError('INVALID CREDENTIALS');
    }
  };

  return (
    <div className="login-page">
      <div className="login-form">
        <div className="login-title">AUTHENTICATION REQUIRED</div>
        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label className="form-label">OPERATOR ID</label>
            <input 
              type="text" 
              className="form-input" 
              value={username}
              onChange={e => setUsername(e.target.value)}
              autoComplete="off"
            />
          </div>
          <div className="form-group">
            <label className="form-label">PASSCODE</label>
            <input 
              type="password" 
              className="form-input" 
              value={password}
              onChange={e => setPassword(e.target.value)}
            />
          </div>
          <button type="submit" className="form-button">AUTHENTICATE</button>
          {error && <div className="form-error">{error}</div>}
        </form>
      </div>
    </div>
  );
};
