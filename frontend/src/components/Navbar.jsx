import React, { useState } from 'react';
import { useAuth } from '../hooks/useAuth';
import { useNotifications } from '../hooks/useNotifications'; // ✅ Using the real hook
import { 
    Bell, LogOut, Menu, Search, X, CheckCircle, 
    Clock, AlertCircle, TrendingUp, Wallet 
} from 'lucide-react';
import axiosInstance from '../api/axios';

const Navbar = ({ onMenuClick }) => {
    const { logout } = useAuth();
    const { notifications, unreadCount, refresh } = useNotifications(); // ✅ Real Data
    const [showNotifications, setShowNotifications] = useState(false);

    // Helper to pick icons based on the backend 'type'
    const getIcon = (type) => {
        switch (type) {
            case 'LOAN': return { icon: Landmark, color: 'text-amber-500' };
            case 'SAVINGS': return { icon: Wallet, color: 'text-emerald-500' };
            case 'SYSTEM': return { icon: AlertCircle, color: 'text-blue-500' };
            default: return { icon: Bell, color: 'text-slate-400' };
        }
    };

    const handleMarkAllRead = async () => {
        try {
            await axiosInstance.post('/notifications/mark_all_read/');
            refresh(); // Update the list immediately
        } catch (error) {
            console.error("Failed to clear notifications", error);
        }
    };

    return (
        <header className="h-16 bg-white border-b border-slate-200 flex items-center justify-between px-4 sm:px-6 lg:px-8 sticky top-0 z-30 shadow-sm shadow-slate-100/50">
            
            <div className="flex items-center flex-1">
                <button 
                    onClick={onMenuClick}
                    className="md:hidden p-2 -ml-2 text-slate-500 hover:text-slate-900 transition-colors active:bg-slate-100 rounded-lg"
                >
                    <Menu className="h-6 w-6" />
                </button>
                
                <div className="hidden sm:flex items-center relative ml-4 w-full max-w-xs group">
                    <Search className="absolute left-3 h-4 w-4 text-slate-400 group-focus-within:text-blue-500 transition-colors" />
                    <input 
                        type="text" 
                        placeholder="Search members or transactions..."
                        className="w-full bg-slate-50 border-none rounded-xl py-2 pl-10 pr-4 text-xs focus:ring-2 focus:ring-blue-500/20 focus:bg-white transition-all outline-none text-slate-600 font-medium"
                    />
                </div>
            </div>
            
            <div className="flex items-center space-x-2 sm:space-x-5">
                
                {/* Real-Time Notifications Popover */}
                <div className="relative">
                    <button 
                        onClick={() => setShowNotifications(!showNotifications)}
                        className={`p-2 rounded-xl transition-all relative ${showNotifications ? 'bg-blue-50 text-blue-600' : 'text-slate-400 hover:bg-slate-50 hover:text-slate-600'}`}
                    >
                        {/* ✅ Red dot only shows if unreadCount > 0 */}
                        {unreadCount > 0 && (
                            <span className="absolute top-2 right-2.5 block h-2.5 w-2.5 rounded-full bg-red-500 ring-2 ring-white animate-pulse"></span>
                        )}
                        <Bell className="h-5 w-5" />
                    </button>

                    {showNotifications && (
                        <>
                            <div className="fixed inset-0 z-10" onClick={() => setShowNotifications(false)}></div>
                            <div className="absolute right-0 mt-3 w-80 bg-white border border-slate-100 rounded-2xl shadow-2xl z-20 overflow-hidden animate-in fade-in zoom-in-95 duration-200">
                                <div className="p-4 border-b border-slate-50 flex items-center justify-between bg-slate-50/50">
                                    <h3 className="text-xs font-black uppercase tracking-widest text-slate-500">
                                        Notifications ({unreadCount})
                                    </h3>
                                    <button 
                                        onClick={handleMarkAllRead}
                                        className="text-[10px] font-bold text-blue-600 hover:text-blue-800 transition-colors"
                                    >
                                        Mark all read
                                    </button>
                                </div>
                                <div className="max-h-64 overflow-y-auto">
                                    {notifications.length > 0 ? (
                                        notifications.map(n => {
                                            const meta = getIcon(n.notification_type);
                                            return (
                                                <div key={n.id} className="p-4 hover:bg-slate-50 flex items-start space-x-3 cursor-pointer transition-colors border-b border-slate-50 last:border-0">
                                                    <meta.icon className={`h-5 w-5 ${meta.color} mt-0.5`} />
                                                    <div>
                                                        <p className="text-sm font-bold text-slate-800 leading-tight">{n.title}</p>
                                                        <p className="text-[11px] text-slate-500 mt-1 line-clamp-2">{n.message}</p>
                                                        <p className="text-[9px] text-slate-400 font-bold uppercase mt-1.5 tracking-tighter">
                                                            {new Date(n.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                                                        </p>
                                                    </div>
                                                </div>
                                            );
                                        })
                                    ) : (
                                        <div className="p-8 text-center">
                                            <CheckCircle className="h-8 w-8 text-slate-200 mx-auto mb-2" />
                                            <p className="text-xs font-bold text-slate-400">All caught up!</p>
                                        </div>
                                    )}
                                </div>
                                <div className="p-3 bg-slate-50 text-center border-t border-slate-100">
                                    <button className="text-[10px] font-black uppercase text-slate-400 hover:text-blue-600 transition-colors">
                                        View All History
                                    </button>
                                </div>
                            </div>
                        </>
                    )}
                </div>
                
                <div className="h-6 w-px bg-slate-200 hidden sm:block"></div>
                
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