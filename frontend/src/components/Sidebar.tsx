import React from 'react';
import { NavLink, useLocation } from 'react-router-dom';
import { useEquipmentStore } from '../stores/equipmentStore';
import { ViewToggle } from './ViewToggle';

export const Sidebar: React.FC = () => {
  const wsConnected = useEquipmentStore(s => s.wsConnected);
  // The toggle only affects the lab overview, so it hides on other pages.
  const onLabPage = useLocation().pathname === '/';

  return (
    <aside className="sidebar">
      <div className="sidebar-title">MAKINO LAB</div>
      <div className="sidebar-subtitle">IIoT DASHBOARD</div>
      
      <div className="sidebar-divider" />
      
      <nav className="sidebar-nav">
        <NavLink 
          to="/" 
          className={({ isActive }) => `sidebar-link ${isActive ? 'active' : ''}`}
          end
        >
          LAB OVERVIEW
        </NavLink>
        <NavLink 
          to="/cameras" 
          className={({ isActive }) => `sidebar-link ${isActive ? 'active' : ''}`}
        >
          CAMERA FEEDS
        </NavLink>
      </nav>

      {onLabPage && <ViewToggle />}

      <div className="sidebar-status">
        <div className={`status-dot ${wsConnected ? 'connected' : 'disconnected'}`} />
        {wsConnected ? 'WS CONNECTED' : 'WS DISCONNECTED'}
      </div>
    </aside>
  );
};
