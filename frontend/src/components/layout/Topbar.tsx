import React from 'react';
import { Bell, Search, User } from 'lucide-react';
import { useAuth } from '../../store/authContext';

const Topbar: React.FC = () => {
  const { user } = useAuth();

  return (
    <header className="topbar flex items-center justify-between glass px-8" style={{
      height: 'var(--topbar-height)',
      position: 'fixed',
      top: 0,
      right: 0,
      left: 'var(--sidebar-width)',
      zIndex: 90,
      borderBottom: '1px solid var(--border)',
    }}>
      <div className="search-bar flex items-center gap-2 px-4 py-2 bg-slate-100 rounded-xl" style={{ width: '400px' }}>
        <Search size={18} className="text-slate-400" />
        <input 
          type="text" 
          placeholder="Search tickets, agents..." 
          className="bg-transparent border-none w-full text-sm"
        />
      </div>

      <div className="flex items-center gap-6">
        <button className="relative text-slate-500 hover:text-slate-700">
          <Bell size={22} />
          <span className="absolute -top-1 -right-1 w-2 h-2 bg-red-500 rounded-full border-2 border-white"></span>
        </button>
        
        <div className="flex items-center gap-3 pl-6 border-l border-slate-200">
          <div className="text-right hidden md:block">
            <p className="text-sm font-semibold leading-none mb-1">{user?.full_name || 'User'}</p>
            <p className="text-xs text-slate-500 leading-none">{user?.role}</p>
          </div>
          <div className="w-10 h-10 rounded-full bg-slate-200 flex items-center justify-center text-slate-600 overflow-hidden">
            {user?.full_name ? (
              <span className="font-bold">{user.full_name.charAt(0)}</span>
            ) : (
              <User size={20} />
            )}
          </div>
        </div>
      </div>
    </header>
  );
};

export default Topbar;
