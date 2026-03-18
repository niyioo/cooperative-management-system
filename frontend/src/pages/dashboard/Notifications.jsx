import React, { useState, useEffect } from 'react';
import axiosInstance from '../../api/axios';
import { 
    Bell, CheckCircle, AlertTriangle, Info, AlertOctagon, Trash2, Check, Loader2
} from 'lucide-react';
import { formatDistanceToNow } from 'date-fns';

const Notifications = () => {
    const [notifications, setNotifications] = useState([]);
    const [loading, setLoading] = useState(true);

    const fetchNotifications = async () => {
        try {
            const response = await axiosInstance.get('/core/notifications/');
            const data = response.data?.results || response.data;
            if (Array.isArray(data)) {
                setNotifications(data);
            }
        } catch (err) {
            console.error("Failed to fetch notifications", err);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchNotifications();
    }, []);

    const markAsRead = async (id) => {
        // Optimistic UI update
        setNotifications(notifications.map(n => n.id === id ? { ...n, is_read: true } : n));
        try {
            await axiosInstance.post(`/core/notifications/${id}/mark_read/`);
        } catch (err) {
            console.error("Failed to mark as read", err);
            fetchNotifications(); // Revert on failure
        }
    };

    const markAllAsRead = async () => {
        setNotifications(notifications.map(n => ({ ...n, is_read: true })));
        try {
            await axiosInstance.post('/core/notifications/mark_all_read/');
        } catch (err) {
            console.error("Failed to mark all as read", err);
            fetchNotifications();
        }
    };

    const deleteNotification = async (id) => {
        setNotifications(notifications.filter(n => n.id !== id));
        try {
            await axiosInstance.delete(`/core/notifications/${id}/`);
        } catch (err) {
            console.error("Failed to delete notification", err);
            fetchNotifications();
        }
    };

    const getIcon = (type) => {
        switch (type) {
            case 'SUCCESS': return <CheckCircle className="h-6 w-6 text-emerald-500" />;
            case 'WARNING': return <AlertTriangle className="h-6 w-6 text-amber-500" />;
            case 'ERROR': return <AlertOctagon className="h-6 w-6 text-red-500" />;
            default: return <Info className="h-6 w-6 text-blue-500" />;
        }
    };

    const getBgColor = (type) => {
        switch (type) {
            case 'SUCCESS': return 'bg-emerald-50';
            case 'WARNING': return 'bg-amber-50';
            case 'ERROR': return 'bg-red-50';
            default: return 'bg-blue-50';
        }
    };

    const unreadCount = notifications.filter(n => !n.is_read).length;

    if (loading) {
        return <div className="flex h-full items-center justify-center"><Loader2 className="animate-spin h-8 w-8 text-blue-500" /></div>;
    }

    return (
        <div className="space-y-6 max-w-4xl mx-auto">
            {/* Header */}
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                <div>
                    <h1 className="text-2xl font-bold text-slate-900 flex items-center">
                        Notifications
                        {unreadCount > 0 && (
                            <span className="ml-3 px-2.5 py-0.5 rounded-full text-xs font-medium bg-red-100 text-red-800">
                                {unreadCount} New
                            </span>
                        )}
                    </h1>
                    <p className="text-sm text-slate-500 mt-1">Stay updated on cooperative activities and alerts.</p>
                </div>
                
                {unreadCount > 0 && (
                    <button 
                        onClick={markAllAsRead}
                        className="inline-flex items-center px-4 py-2 bg-white border border-slate-300 text-slate-700 text-sm font-medium rounded-lg hover:bg-slate-50 transition-colors shadow-sm"
                    >
                        <Check className="h-4 w-4 mr-2 text-slate-400" />
                        Mark all as read
                    </button>
                )}
            </div>

            {/* Notifications List */}
            <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
                {notifications.length > 0 ? (
                    <ul className="divide-y divide-slate-100">
                        {notifications.map((notification) => (
                            <li 
                                key={notification.id} 
                                className={`p-4 sm:px-6 hover:bg-slate-50 transition-colors group ${!notification.is_read ? 'bg-slate-50/50' : 'bg-white'}`}
                            >
                                <div className="flex items-start space-x-4">
                                    <div className={`flex-shrink-0 p-2 rounded-full ${getBgColor(notification.type)}`}>
                                        {getIcon(notification.type)}
                                    </div>
                                    <div className="flex-1 min-w-0">
                                        <p className={`text-sm font-medium ${!notification.is_read ? 'text-slate-900' : 'text-slate-700'}`}>
                                            {notification.title}
                                        </p>
                                        <p className="text-sm text-slate-500 mt-1">
                                            {notification.message}
                                        </p>
                                        <p className="text-xs text-slate-400 mt-2">
                                            {formatDistanceToNow(new Date(notification.created_at), { addSuffix: true })}
                                        </p>
                                    </div>
                                    <div className="flex-shrink-0 flex items-center space-x-2 opacity-0 group-hover:opacity-100 transition-opacity">
                                        {!notification.is_read && (
                                            <button 
                                                onClick={() => markAsRead(notification.id)}
                                                title="Mark as read" 
                                                className="p-1.5 text-blue-600 hover:bg-blue-50 rounded-md transition-colors"
                                            >
                                                <CheckCircle className="h-4 w-4" />
                                            </button>
                                        )}
                                        <button 
                                            onClick={() => deleteNotification(notification.id)}
                                            title="Delete" 
                                            className="p-1.5 text-slate-400 hover:text-red-600 hover:bg-red-50 rounded-md transition-colors"
                                        >
                                            <Trash2 className="h-4 w-4" />
                                        </button>
                                    </div>
                                </div>
                            </li>
                        ))}
                    </ul>
                ) : (
                    <div className="p-12 text-center flex flex-col items-center">
                        <div className="bg-slate-50 p-4 rounded-full mb-4">
                            <Bell className="h-8 w-8 text-slate-300" />
                        </div>
                        <h3 className="text-base font-medium text-slate-900">All caught up!</h3>
                        <p className="text-sm text-slate-500 mt-1">You have no new notifications right now.</p>
                    </div>
                )}
            </div>
        </div>
    );
};

export default Notifications;