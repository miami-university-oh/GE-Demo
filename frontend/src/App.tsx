import React from 'react';
import { Routes, Route, Navigate, Outlet } from 'react-router-dom';
import { Sidebar } from './components/Sidebar';
import { Header } from './components/Header';
import { Login } from './pages/Login';
import { MakinoLab } from './pages/MakinoLab';
import { Cameras } from './pages/Cameras';

const ProtectedRoute = () => {
  const isAuth = localStorage.getItem('auth') === 'true';
  if (!isAuth) {
    return <Navigate to="/login" replace />;
  }

  return (
    <div className="app-layout">
      <Sidebar />
      <Header />
      <main className="main-content">
        <Outlet />
      </main>
    </div>
  );
};

export const App: React.FC = () => {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route element={<ProtectedRoute />}>
        <Route path="/" element={<MakinoLab />} />
        <Route path="/cameras" element={<Cameras />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
};

export default App;
