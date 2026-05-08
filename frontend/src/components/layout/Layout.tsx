import React from 'react';
import { Outlet } from 'react-router-dom';
import Sidebar from './Sidebar';
import Topbar from './Topbar';

const Layout: React.FC = () => {
  return (
    <div className="layout-wrapper" style={{ display: 'flex', minHeight: '100vh' }}>
      <Sidebar />
      <div className="main-content" style={{ 
        flex: 1, 
        marginLeft: 'var(--sidebar-width)', 
        paddingTop: 'var(--topbar-height)',
        backgroundColor: 'var(--bg-main)',
        minHeight: '100vh'
      }}>
        <Topbar />
        <main style={{ padding: '2rem' }}>
          <Outlet />
        </main>
      </div>
    </div>
  );
};

export default Layout;
