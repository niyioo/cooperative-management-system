import React from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';
import { 
    LayoutDashboard, Users, Wallet, Landmark, 
    PieChart, Receipt, FileBarChart, Settings, UserCircle 
} from 'lucide-react';

const Sidebar = () => {
    const { user, isSuperAdmin, isManager, isLoanOfficer } = useAuth();
    const navigate = useNavigate();

    // Define navigation links based on roles
    const navItems = [
        { name: 'Dashboard', path: '/dashboard', icon: LayoutDashboard, show: true },
        { name: 'Members', path: '/members', icon: Users, show: isManager || isSuperAdmin },
        { name: 'Savings', path: '/savings', icon: Wallet, show: true },
        { name: 'Loans', path: '/loans', icon: Landmark, show: true },
        { name: 'Shares', path: '/shares', icon: PieChart, show: true },
        { name: 'Contributions', path: '/contributions', icon: Receipt, show: true },
        { name: 'Finance Ledger', path: '/finance', icon: FileBarChart, show: isManager || isSuperAdmin },
        { name: 'Settings', path: '/settings', icon: Settings, show: isSuperAdmin || isManager }, // Opened to managers too
    ];

    return (
        <div className="hidden md:flex flex-col w-64 bg-slate-900 h-full text-slate-300 transition-all duration-300 flex-shrink-0 border-r border-slate-800">
            {/* Brand Logo Header */}
            <div className="h-20 flex items-center px-6 bg-slate-950 font-black text-2xl tracking-tighter text-white border-b border-slate-800">
                <span className="text-blue-500 mr-1.5 italic">B</span>ravEdge
            </div>
            
            {/* Main Navigation */}
            <div className="flex-1 overflow-y-auto py-6">
                <nav className="space-y-1.5 px-4">
                    {navItems.filter(item => item.show).map((item) => {
                        const Icon = item.icon;
                        return (
                            <NavLink
                                key={item.name}
                                to={item.path}
                                className={({ isActive }) =>
                                    `group flex items-center px-4 py-3 text-sm font-bold rounded-xl transition-all duration-200 ${
                                        isActive
                                            ? 'bg-blue-600 text-white shadow-lg shadow-blue-900/20'
                                            : 'text-slate-400 hover:bg-slate-800 hover:text-white'
                                    }`
                                }
                            >
                                <Icon className={`flex-shrink-0 mr-3 h-5 w-5 transition-colors duration-200`} />
                                <span className="tracking-tight">{item.name}</span>
                            </NavLink>
                        );
                    })}
                </nav>
            </div>
            
            {/* Live Profile Section (Clickable) */}
            <div 
                onClick={() => navigate('/settings')}
                className="p-4 bg-slate-950 border-t border-slate-800 cursor-pointer hover:bg-slate-900 transition-all group"
            >
                <div className="flex items-center p-2 rounded-xl transition-colors group-hover:bg-slate-800/50">
                    <div className="relative">
                        <div className="h-10 w-10 rounded-full bg-gradient-to-tr from-blue-600 to-indigo-400 flex items-center justify-center text-white font-black text-sm shadow-inner ring-2 ring-slate-800 group-hover:ring-blue-500 transition-all">
                            {user?.email?.charAt(0).toUpperCase() || 'A'}
                        </div>
                        <div className="absolute bottom-0 right-0 h-3 w-3 bg-emerald-500 border-2 border-slate-950 rounded-full shadow-sm"></div>
                    </div>
                    
                    <div className="ml-3 overflow-hidden">
                        <p className="text-xs font-black text-white truncate w-32 tracking-tight group-hover:text-blue-400 transition-colors">
                            {user?.email}
                        </p>
                        <p className="text-[10px] font-bold text-slate-500 uppercase tracking-widest leading-none mt-1">
                            {user?.role?.replace('_', ' ')}
                        </p>
                    </div>
                    
                    <div className="ml-auto opacity-0 group-hover:opacity-100 transition-opacity">
                        <Settings className="h-4 w-4 text-slate-500" />
                    </div>
                </div>
            </div>
        </div>
    );
};

export default Sidebar;