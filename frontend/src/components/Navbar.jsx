import React from 'react';
import { useAuth } from '../hooks/useAuth';
import { Bell, LogOut, Menu } from 'lucide-react';

const Navbar = () => {
    const { logout } = useAuth();

    return (
        <header className="h-16 bg-white border-b border-slate-200 flex items-center justify-between px-4 sm:px-6 lg:px-8 z-10">
            <div className="flex items-center">
                <button className="md:hidden text-slate-500 hover:text-slate-700 focus:outline-none focus:ring-2 focus:ring-inset focus:ring-blue-500">
                    <Menu className="h-6 w-6" />
                </button>
            </div>
            
            <div className="flex items-center space-x-4">
                <button className="text-slate-400 hover:text-slate-500 p-1 rounded-full focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 relative">
                    <span className="absolute top-0 right-0 block h-2 w-2 rounded-full bg-red-400 ring-2 ring-white"></span>
                    <Bell className="h-6 w-6" />
                </button>
                
                <div className="h-8 w-px bg-slate-200 mx-2"></div>
                
                <button 
                    onClick={logout}
                    className="flex items-center text-sm font-medium text-slate-700 hover:text-red-600 transition-colors"
                >
                    <LogOut className="h-5 w-5 mr-1.5 text-slate-400 hover:text-red-600 transition-colors" />
                    Logout
                </button>
            </div>
        </header>
    );
};

export default Navbar;