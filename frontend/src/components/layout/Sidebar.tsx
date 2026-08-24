import React, { useEffect, useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';

const Sidebar: React.FC = () => {
  const location = useLocation();
  const navigate = useNavigate();
  const [roles, setRoles] = useState<string[]>([]);

  useEffect(() => {
    try {
      const storedRoles = localStorage.getItem('user_roles');
      if (storedRoles) {
        setRoles(JSON.parse(storedRoles));
      } else if (localStorage.getItem('access_token')) {
        // Fallback for existing sessions before we stored roles
        setRoles(['merchant']);
      }
    } catch (e) {
      console.error("Failed to parse roles", e);
    }
  }, [location.pathname]);

  const handleLogout = () => {
    localStorage.removeItem('access_token');
    localStorage.removeItem('user_roles');
    navigate('/login');
  };

  const navItems = [];
  if (roles.includes('merchant')) {
    navItems.push({ name: 'Merchant Dashboard', path: '/merchant' });
  }
  if (roles.includes('support')) {
    navItems.push({ name: 'Support Console', path: '/support' });
  }
  if (roles.includes('approver')) {
    navItems.push({ name: 'Approval Queue', path: '/approvals' });
  }

  // If no roles are loaded yet but there is a token, don't show an empty sidebar, show at least merchant
  if (navItems.length === 0 && localStorage.getItem('access_token')) {
    navItems.push({ name: 'Merchant Dashboard', path: '/merchant' });
  }

  const isActive = (path: string) => location.pathname.startsWith(path);

  return (
    <div className="w-64 bg-slate-900 text-slate-300 flex flex-col border-r border-slate-800 shrink-0">
      <div className="h-16 flex items-center px-6 border-b border-slate-800">
        <span className="text-white font-bold text-lg tracking-tight">DegradeWatch</span>
        <span className="ml-2 px-1.5 py-0.5 rounded text-[10px] font-bold bg-blue-900 text-blue-200 border border-blue-700">OPS</span>
      </div>
      
      <div className="flex-1 py-6 px-4 space-y-1">
        <div className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-3 px-2">Navigation</div>
        {navItems.map((item) => (
          <Link
            key={item.path}
            to={item.path}
            className={`block px-3 py-2 rounded-md text-sm font-medium transition-colors ${
              isActive(item.path)
                ? 'bg-blue-600/10 text-blue-400 border border-blue-600/20'
                : 'text-slate-400 hover:bg-slate-800 hover:text-slate-200 border border-transparent'
            }`}
          >
            {item.name}
          </Link>
        ))}
      </div>

      <div className="p-4 border-t border-slate-800">
        {localStorage.getItem('access_token') ? (
          <button 
            onClick={handleLogout}
            className="w-full text-left px-3 py-2 rounded-md text-sm font-medium text-slate-400 hover:bg-slate-800 hover:text-white transition-colors flex items-center"
          >
            Logout
          </button>
        ) : (
          <Link 
            to="/login"
            className="w-full block px-3 py-2 rounded-md text-sm font-medium text-slate-400 hover:bg-slate-800 hover:text-white transition-colors"
          >
            Login
          </Link>
        )}
      </div>
    </div>
  );
};

export default Sidebar;
