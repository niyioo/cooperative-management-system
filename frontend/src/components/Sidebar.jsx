import React from 'react';
import { NavLink } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';
import { 
    LayoutDashboard, Users, Wallet, Landmark, 
    PieChart, Receipt, FileBarChart, Settings 
} from 'lucide-react';

const Sidebar = () => {
    const { user, isSuperAdmin, isManager, isLoanOfficer } = useAuth();

    // Define navigation links based on roles
    const navItems = [
        { name: 'Dashboard', path: '/dashboard', icon: LayoutDashboard, show: true },
        { name: 'Members', path: '/members', icon: Users, show: isManager || isSuperAdmin },
        { name: 'Savings', path: '/savings', icon: Wallet, show: true },
        { name: 'Loans', path: '/loans', icon: Landmark, show: isLoanOfficer || true },
        { name: 'Shares', path: '/shares', icon: PieChart, show: true },
        { name: 'Contributions', path: '/contributions', icon: Receipt, show: true },
        { name: 'Finance Ledger', path: '/finance', icon: FileBarChart, show: isManager || isSuperAdmin },
        { name: 'Settings', path: '/settings', icon: Settings, show: isSuperAdmin },
    ];

    return (
        <div className="hidden md:flex flex-col w-64 bg-slate-900 h-full text-slate-300 transition-all duration-300 flex-shrink-0">
            <div className="h-16 flex items-center px-6 bg-slate-950 font-bold text-xl tracking-tight text-white border-b border-slate-800">
                <span className="text-blue-500 mr-2">C</span>Manager
            </div>
            
            <div className="flex-1 overflow-y-auto py-4">
                <nav className="space-y-1 px-3">
                    {navItems.filter(item => item.show).map((item) => {
                        const Icon = item.icon;
                        return (
                            <NavLink
                                key={item.name}
                                to={item.path}
                                className={({ isActive }) =>
                                    `group flex items-center px-3 py-2.5 text-sm font-medium rounded-md transition-colors ${
                                        isActive
                                            ? 'bg-blue-600 text-white'
                                            : 'text-slate-300 hover:bg-slate-800 hover:text-white'
                                    }`
                                }
                            >
                                <Icon className="flex-shrink-0 -ml-1 mr-3 h-5 w-5" />
                                <span className="truncate">{item.name}</span>
                            </NavLink>
                        );
                    })}
                </nav>
            </div>
            
            <div className="p-4 bg-slate-950 border-t border-slate-800">
                <div className="flex items-center">
                    <div className="h-8 w-8 rounded-full bg-blue-500 flex items-center justify-center text-white font-bold text-sm">
                        {user?.email?.charAt(0).toUpperCase() || 'U'}
                    </div>
                    <div className="ml-3">
                        <p className="text-sm font-medium text-white truncate w-40">{user?.email}</p>
                        <p className="text-xs text-slate-400 capitalize">{user?.role?.replace('_', ' ').toLowerCase()}</p>
                    </div>
                </div>
            </div>
        </div>
    );
};

export default Sidebar;