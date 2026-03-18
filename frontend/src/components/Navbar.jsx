import React, { useState } from 'react';
import { useAuth } from '../hooks/useAuth';
import { Bell, LogOut, Menu, Search, X, CheckCircle, Clock } from 'lucide-react';

const Navbar = () => {
    const { logout, user } = useAuth();
    const [showNotifications, setShowNotifications] = useState(false);

    // Mock live notifications - in production, fetch these from /notifications/
    const notifications = [
        { id: 1, title: 'New Loan Request', time: '5m ago', icon: Clock, color: 'text-amber-500' },
        { id: 2, title: 'Deposit Confirmed', time: '1h ago', icon: CheckCircle, color: 'text-emerald-500' },
    ];

    return (
        <header className="h-16 bg-white border-b border-slate-200 flex items-center justify-between px-4 sm:px-6 lg:px-8 sticky top-0 z-30 shadow-sm shadow-slate-100/50">
            
            {/* Left: Mobile Menu & Search */}
            <div className="flex items-center flex-1">
                <button className="md:hidden p-2 -ml-2 text-slate-500 hover:text-slate-900 transition-colors">
                    <Menu className="h-6 w-6" />
                </button>
                
                {/* Quick Search - Visual only for now */}
                <div className="hidden sm:flex items-center relative ml-4 w-full max-w-xs group">
                    <Search className="absolute left-3 h-4 w-4 text-slate-400 group-focus-within:text-blue-500 transition-colors" />
                    <input 
                        type="text" 
                        placeholder="Search members or transactions..."
                        className="w-full bg-slate-50 border-none rounded-xl py-2 pl-10 pr-4 text-xs focus:ring-2 focus:ring-blue-500/20 focus:bg-white transition-all outline-none text-slate-600 font-medium"
                    />
                </div>
            </div>
            
            {/* Right: Actions */}
            <div className="flex items-center space-x-2 sm:space-x-5">
                
                {/* Live Notifications Popover */}
                <div className="relative">
                    <button 
                        onClick={() => setShowNotifications(!showNotifications)}
                        className={`p-2 rounded-xl transition-all relative ${showNotifications ? 'bg-blue-50 text-blue-600' : 'text-slate-400 hover:bg-slate-50 hover:text-slate-600'}`}
                    >
                        <span className="absolute top-2 right-2.5 block h-2 w-2 rounded-full bg-red-500 ring-2 ring-white"></span>
                        <Bell className="h-5 w-5" />
                    </button>

                    {showNotifications && (
                        <>
                            <div className="fixed inset-0 z-10" onClick={() => setShowNotifications(false)}></div>
                            <div className="absolute right-0 mt-3 w-80 bg-white border border-slate-100 rounded-2xl shadow-2xl z-20 overflow-hidden animate-in fade-in zoom-in-95 duration-200">
                                <div className="p-4 border-b border-slate-50 flex items-center justify-between bg-slate-50/50">
                                    <h3 className="text-xs font-black uppercase tracking-widest text-slate-500">Notifications</h3>
                                    <span className="text-[10px] font-bold text-blue-600 cursor-pointer">Mark all read</span>
                                </div>
                                <div className="max-h-64 overflow-y-auto">
                                    {notifications.map(n => (
                                        <div key={n.id} className="p-4 hover:bg-slate-50 flex items-start space-x-3 cursor-pointer transition-colors">
                                            <n.icon className={`h-5 w-5 ${n.color} mt-0.5`} />
                                            <div>
                                                <p className="text-sm font-bold text-slate-800">{n.title}</p>
                                                <p className="text-[10px] text-slate-400 font-medium mt-0.5">{n.time}</p>
                                            </div>
                                        </div>
                                    ))}
                                </div>
                                <div className="p-3 bg-slate-50 text-center border-t border-slate-100">
                                    <button className="text-[10px] font-black uppercase text-slate-400 hover:text-blue-600 transition-colors">View All History</button>
                                </div>
                            </div>
                        </>
                    )}
                </div>
                
                <div className="h-6 w-px bg-slate-200 hidden sm:block"></div>
                
                {/* Logout with Confirmation style */}
                <button 
                    onClick={logout}
                    className="group flex items-center space-x-2 py-2 px-3 sm:px-4 rounded-xl bg-white border border-slate-200 hover:border-red-100 hover:bg-red-50 transition-all active:scale-95"
                >
                    <span className="text-xs font-black text-slate-600 group-hover:text-red-600 hidden sm:inline transition-colors">Logout</span>
                    <LogOut className="h-4 w-4 text-slate-400 group-hover:text-red-500 transition-colors" />
                </button>
            </div>
        </header>
    );
};

export default Navbar;