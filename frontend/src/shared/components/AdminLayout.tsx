import React, { useState, useEffect } from 'react';
import { NavLink, Outlet } from 'react-router-dom';
import { Mic, Activity, Moon, Sun } from 'lucide-react';
import { Tooltip } from './Tooltip';
import './AdminLayout.css';

export const AdminLayout: React.FC = () => {
  const [theme, setTheme] = useState<'light' | 'dark'>('dark');

  useEffect(() => {
    // Check if user has a preference in localStorage
    const savedTheme = localStorage.getItem('kimet-theme');
    if (savedTheme === 'light' || savedTheme === 'dark') {
      setTheme(savedTheme);
      document.documentElement.setAttribute('data-theme', savedTheme);
    } else {
      // Default to dark
      document.documentElement.setAttribute('data-theme', 'dark');
    }
  }, []);

  const toggleTheme = () => {
    const newTheme = theme === 'dark' ? 'light' : 'dark';
    setTheme(newTheme);
    localStorage.setItem('kimet-theme', newTheme);
    document.documentElement.setAttribute('data-theme', newTheme);
  };

  return (
    <div className="admin-layout">
      <nav className="top-navbar">
        <div className="navbar-brand">
          <img src="/kimet-logo.png" alt="KIMET.AI Logo" className="kimet-logo-img" />
          <span className="navbar-brand-text">KIMET.AI</span>
        </div>
        <div className="navbar-actions">
          <Tooltip text={`Switch to ${theme === 'dark' ? 'Light' : 'Dark'} Mode`}>
            <button className="theme-toggle" onClick={toggleTheme}>
              {theme === 'dark' ? <Sun size={24} /> : <Moon size={24} />}
            </button>
          </Tooltip>
        </div>
      </nav>

      <div className="admin-body">
        <aside className="sidebar">
          <nav className="sidebar-nav">
            <Tooltip text="Voice Cloning">
              <NavLink 
                to="/admin/voice" 
                className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}
              >
                <Mic size={24} />
              </NavLink>
            </Tooltip>

            <Tooltip text="Candidate Monitoring">
              <NavLink 
                to="/admin/monitoring/default" 
                className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}
              >
                <Activity size={24} />
              </NavLink>
            </Tooltip>
          </nav>
        </aside>

        <main className="main-content">
          <Outlet />
        </main>
      </div>
    </div>
  );
};
