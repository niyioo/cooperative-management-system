import React, { useState, useEffect } from 'react';
import axiosInstance from '../../api/axios';
import { useAuth } from '../../hooks/useAuth';
import { 
    User, Lock, Bell, Building, Save, Loader2, CheckCircle, AlertCircle
} from 'lucide-react';

const Settings = () => {
    const { isManager, user } = useAuth();
    const [activeTab, setActiveTab] = useState('profile');
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [successMessage, setSuccessMessage] = useState('');
    const [error, setError] = useState('');

    // State for System Settings (Admin Only)
    const [systemData, setSystemData] = useState({
        id: null,
        cooperative_name: 'BravEdge Solutions Cooperative',
        currency: 'NGN (₦)',
        registration_number: 'COOP-2026-001'
    });

    useEffect(() => {
        // Fetch System Settings if Manager
        if (isManager) {
            const fetchSettings = async () => {
                try {
                    const response = await axiosInstance.get('/core/settings/');
                    const data = response.data?.results || response.data;
                    if (data && data.length > 0) {
                        setSystemData(data[0]); // Grab the first settings instance
                    }
                } catch (err) {
                    console.error("Failed to load settings", err);
                }
            };
            fetchSettings();
        }
    }, [isManager]);

    const handleSave = async (e) => {
        e.preventDefault();
        setIsSubmitting(true);
        setError('');
        setSuccessMessage('');

        try {
            if (activeTab === 'system' && isManager) {
                // Update System Settings
                if (systemData.id) {
                    await axiosInstance.put(`/core/settings/${systemData.id}/`, systemData);
                } else {
                    await axiosInstance.post(`/core/settings/`, systemData);
                }
            } 
            // Add other tab save logic here (Profile, Security) as needed
            
            setSuccessMessage('Settings updated successfully!');
            setTimeout(() => setSuccessMessage(''), 4000);
        } catch (err) {
            setError('Failed to save changes. Please try again.');
        } finally {
            setIsSubmitting(false);
        }
    };

    return (
        <div className="space-y-6 max-w-6xl mx-auto">
            {/* Header */}
            <div>
                <h1 className="text-2xl font-bold text-slate-900">Account Settings</h1>
                <p className="text-sm text-slate-500 mt-1">Manage your profile, security, and system preferences.</p>
            </div>

            <div className="flex flex-col md:flex-row gap-6">
                {/* Settings Sidebar */}
                <div className="w-full md:w-64 flex-shrink-0">
                    <nav className="space-y-1">
                        <button 
                            onClick={() => setActiveTab('profile')}
                            className={`w-full flex items-center px-3 py-2.5 text-sm font-medium rounded-lg transition-colors ${activeTab === 'profile' ? 'bg-blue-50 text-blue-700' : 'text-slate-700 hover:bg-slate-50'}`}
                        >
                            <User className={`h-5 w-5 mr-3 ${activeTab === 'profile' ? 'text-blue-700' : 'text-slate-400'}`} />
                            My Profile
                        </button>
                        <button 
                            onClick={() => setActiveTab('security')}
                            className={`w-full flex items-center px-3 py-2.5 text-sm font-medium rounded-lg transition-colors ${activeTab === 'security' ? 'bg-blue-50 text-blue-700' : 'text-slate-700 hover:bg-slate-50'}`}
                        >
                            <Lock className={`h-5 w-5 mr-3 ${activeTab === 'security' ? 'text-blue-700' : 'text-slate-400'}`} />
                            Security & Password
                        </button>
                        <button 
                            onClick={() => setActiveTab('notifications')}
                            className={`w-full flex items-center px-3 py-2.5 text-sm font-medium rounded-lg transition-colors ${activeTab === 'notifications' ? 'bg-blue-50 text-blue-700' : 'text-slate-700 hover:bg-slate-50'}`}
                        >
                            <Bell className={`h-5 w-5 mr-3 ${activeTab === 'notifications' ? 'text-blue-700' : 'text-slate-400'}`} />
                            Notification Preferences
                        </button>
                        
                        {isManager && (
                            <>
                                <div className="pt-4 pb-2">
                                    <p className="px-3 text-xs font-semibold text-slate-500 uppercase tracking-wider">Admin Only</p>
                                </div>
                                <button 
                                    onClick={() => setActiveTab('system')}
                                    className={`w-full flex items-center px-3 py-2.5 text-sm font-medium rounded-lg transition-colors ${activeTab === 'system' ? 'bg-slate-800 text-white' : 'text-slate-700 hover:bg-slate-50'}`}
                                >
                                    <Building className={`h-5 w-5 mr-3 ${activeTab === 'system' ? 'text-white' : 'text-slate-400'}`} />
                                    System Settings
                                </button>
                            </>
                        )}
                    </nav>
                </div>

                {/* Settings Content Area */}
                <div className="flex-1 bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
                    <form onSubmit={handleSave} className="p-6 sm:p-8">
                        
                        {error && (
                            <div className="mb-6 bg-red-50 border-l-4 border-red-500 p-4 flex items-center">
                                <AlertCircle className="h-5 w-5 text-red-500 mr-2" />
                                <p className="text-sm text-red-700">{error}</p>
                            </div>
                        )}

                        {/* PROFILE TAB */}
                        {activeTab === 'profile' && (
                            <div className="space-y-6 animate-in fade-in duration-300">
                                <h2 className="text-lg font-medium text-slate-900 border-b border-slate-200 pb-4">Personal Information</h2>
                                <div className="grid grid-cols-1 gap-6 sm:grid-cols-2">
                                    <div className="sm:col-span-2">
                                        <label className="block text-sm font-medium text-slate-700 mb-1">Email Address</label>
                                        <input type="email" value={user?.email || ''} readOnly className="block w-full px-3 py-2 border border-slate-200 bg-slate-50 rounded-lg text-slate-500 sm:text-sm cursor-not-allowed" />
                                        <p className="mt-1 text-xs text-slate-500">Your email is tied to your login identity.</p>
                                    </div>
                                    <div className="sm:col-span-2">
                                        <label className="block text-sm font-medium text-slate-700 mb-1">Role</label>
                                        <input type="text" value={user?.role || 'Member'} readOnly className="block w-full px-3 py-2 border border-slate-200 bg-slate-50 rounded-lg text-slate-500 sm:text-sm font-mono cursor-not-allowed" />
                                    </div>
                                </div>
                            </div>
                        )}

                        {/* SECURITY TAB */}
                        {activeTab === 'security' && (
                            <div className="space-y-6 animate-in fade-in duration-300">
                                <h2 className="text-lg font-medium text-slate-900 border-b border-slate-200 pb-4">Change Password</h2>
                                <div className="space-y-4 max-w-md">
                                    <div>
                                        <label className="block text-sm font-medium text-slate-700 mb-1">Current Password</label>
                                        <input type="password" placeholder="••••••••" className="block w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-blue-500 focus:border-blue-500 sm:text-sm" />
                                    </div>
                                    <div>
                                        <label className="block text-sm font-medium text-slate-700 mb-1">New Password</label>
                                        <input type="password" placeholder="••••••••" className="block w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-blue-500 focus:border-blue-500 sm:text-sm" />
                                    </div>
                                    <div>
                                        <label className="block text-sm font-medium text-slate-700 mb-1">Confirm New Password</label>
                                        <input type="password" placeholder="••••••••" className="block w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-blue-500 focus:border-blue-500 sm:text-sm" />
                                    </div>
                                </div>
                            </div>
                        )}

                        {/* NOTIFICATIONS TAB */}
                        {activeTab === 'notifications' && (
                            <div className="space-y-6 animate-in fade-in duration-300">
                                <h2 className="text-lg font-medium text-slate-900 border-b border-slate-200 pb-4">Email Notifications</h2>
                                <div className="space-y-4">
                                    {['New Loan Applications', 'Savings Deposits', 'System Alerts', 'Monthly Statements'].map((item, i) => (
                                        <div key={i} className="flex items-start">
                                            <div className="flex items-center h-5">
                                                <input id={`notify-${i}`} type="checkbox" defaultChecked className="focus:ring-blue-500 h-4 w-4 text-blue-600 border-slate-300 rounded" />
                                            </div>
                                            <div className="ml-3 text-sm">
                                                <label htmlFor={`notify-${i}`} className="font-medium text-slate-700">{item}</label>
                                                <p className="text-slate-500">Receive an email when this event occurs.</p>
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        )}

                        {/* SYSTEM SETTINGS TAB */}
                        {activeTab === 'system' && isManager && (
                            <div className="space-y-6 animate-in fade-in duration-300">
                                <h2 className="text-lg font-medium text-slate-900 border-b border-slate-200 pb-4">Global Cooperative Settings</h2>
                                <div className="grid grid-cols-1 gap-6 sm:grid-cols-2">
                                    <div className="sm:col-span-2">
                                        <label className="block text-sm font-medium text-slate-700 mb-1">Cooperative Name</label>
                                        <input 
                                            type="text" 
                                            required
                                            value={systemData.cooperative_name} 
                                            onChange={e => setSystemData({...systemData, cooperative_name: e.target.value})}
                                            className="block w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-slate-900 focus:border-slate-900 sm:text-sm" 
                                        />
                                    </div>
                                    <div>
                                        <label className="block text-sm font-medium text-slate-700 mb-1">Currency</label>
                                        <select 
                                            value={systemData.currency}
                                            onChange={e => setSystemData({...systemData, currency: e.target.value})}
                                            className="block w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-slate-900 focus:border-slate-900 sm:text-sm"
                                        >
                                            <option value="NGN (₦)">NGN (₦)</option>
                                            <option value="USD ($)">USD ($)</option>
                                        </select>
                                    </div>
                                    <div>
                                        <label className="block text-sm font-medium text-slate-700 mb-1">Registration Number</label>
                                        <input 
                                            type="text" 
                                            value={systemData.registration_number} 
                                            onChange={e => setSystemData({...systemData, registration_number: e.target.value})}
                                            className="block w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-slate-900 focus:border-slate-900 sm:text-sm" 
                                        />
                                    </div>
                                </div>
                            </div>
                        )}

                        {/* Save Button */}
                        <div className="mt-8 pt-6 border-t border-slate-200 flex items-center justify-end">
                            <button
                                type="submit"
                                disabled={isSubmitting}
                                className={`inline-flex items-center px-4 py-2 text-sm font-medium text-white border border-transparent rounded-lg focus:outline-none focus:ring-2 focus:ring-offset-2 transition-colors ${activeTab === 'system' ? 'bg-slate-900 hover:bg-slate-800 focus:ring-slate-900' : 'bg-blue-600 hover:bg-blue-700 focus:ring-blue-500'} disabled:opacity-70`}
                            >
                                {isSubmitting ? (
                                    <><Loader2 className="animate-spin h-4 w-4 mr-2" /> Saving...</>
                                ) : (
                                    <><Save className="h-4 w-4 mr-2" /> Save Changes</>
                                )}
                            </button>
                        </div>
                    </form>
                </div>
            </div>

            {/* Success Toast */}
            {successMessage && (
                <div className="fixed bottom-4 right-4 bg-emerald-50 border-l-4 border-emerald-500 p-4 rounded shadow-lg animate-in fade-in slide-in-from-bottom-5 z-50 flex items-center">
                    <CheckCircle className="h-5 w-5 text-emerald-500 mr-2" />
                    <p className="text-sm text-emerald-700 font-medium">{successMessage}</p>
                </div>
            )}
        </div>
    );
};

export default Settings;