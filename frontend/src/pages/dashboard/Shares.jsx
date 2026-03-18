import React, { useState, useEffect } from 'react';
import axiosInstance from '../../api/axios';
import { useAuth } from '../../hooks/useAuth';
import { 
    Search, Plus, PieChart, TrendingUp, AlertCircle, Loader2, ArrowRightLeft, Users
} from 'lucide-react';
import { format } from 'date-fns';
import BuySharesModal from '../../components/BuySharesModal';

const Shares = () => {
    const { isManager } = useAuth();
    const [shareAccounts, setShareAccounts] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');
    const [searchTerm, setSearchTerm] = useState('');

    // Modal & Toast State
    const [isModalOpen, setIsModalOpen] = useState(false);
    const [successMessage, setSuccessMessage] = useState('');

    // Extracted so we can refresh the table after buying shares
    const fetchShares = async () => {
        try {
            const response = await axiosInstance.get('/shares/accounts/');
            const data = response.data.results || response.data;
            setShareAccounts(data);
        } catch (err) {
            console.error("Failed to fetch shares:", err);
            setError('Failed to load share capital data. Please try again later.');
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchShares();
    }, []);

    // Quick Stats Calculations
    const totalShareCapital = shareAccounts.reduce((sum, acc) => sum + parseFloat(acc.total_value || 0), 0);
    const totalSharesIssued = shareAccounts.reduce((sum, acc) => sum + parseInt(acc.total_shares || 0, 10), 0);
    const activeShareholders = shareAccounts.filter(acc => acc.total_shares > 0).length;

    // Filter accounts based on search input
    const filteredAccounts = shareAccounts.filter(account => {
        const memberName = `${account.member?.first_name} ${account.member?.last_name}`.toLowerCase();
        const memberId = account.member?.membership_id?.toLowerCase() || '';
        const search = searchTerm.toLowerCase();
        return memberName.includes(search) || memberId.includes(search);
    });

    const formatCurrency = (amount) => {
        return new Intl.NumberFormat('en-NG', { style: 'currency', currency: 'NGN' }).format(amount);
    };

    if (loading) {
        return (
            <div className="flex h-full items-center justify-center">
                <Loader2 className="animate-spin h-8 w-8 text-blue-500" />
            </div>
        );
    }

    return (
        <div className="space-y-6">
            {/* Header Section */}
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                <div>
                    <h1 className="text-2xl font-bold text-slate-900">Share Capital Management</h1>
                    <p className="text-sm text-slate-500 mt-1">Track cooperative equity and individual member shareholdings.</p>
                </div>
                
                {isManager && (
                    <div className="flex space-x-3">
                        <button 
                            onClick={() => setIsModalOpen(true)}
                            className="inline-flex items-center justify-center px-4 py-2 bg-indigo-600 text-white text-sm font-medium rounded-lg hover:bg-indigo-700 transition-colors shadow-sm"
                        >
                            <Plus className="h-4 w-4 mr-2" />
                            Buy Shares
                        </button>
                    </div>
                )}
            </div>

            {/* Error State */}
            {error && (
                <div className="bg-red-50 border-l-4 border-red-500 p-4 rounded-r-lg">
                    <div className="flex items-center">
                        <AlertCircle className="h-5 w-5 text-red-500 mr-2" />
                        <p className="text-sm text-red-700">{error}</p>
                    </div>
                </div>
            )}

            {/* Top Stats Cards */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                <div className="bg-white p-6 rounded-xl shadow-sm border border-slate-200 flex items-center space-x-4">
                    <div className="bg-indigo-100 p-3 rounded-lg">
                        <PieChart className="h-6 w-6 text-indigo-600" />
                    </div>
                    <div>
                        <p className="text-sm font-medium text-slate-500">Total Share Capital</p>
                        <h3 className="text-2xl font-bold text-slate-900">{formatCurrency(totalShareCapital)}</h3>
                    </div>
                </div>
                
                <div className="bg-white p-6 rounded-xl shadow-sm border border-slate-200 flex items-center space-x-4">
                    <div className="bg-emerald-100 p-3 rounded-lg">
                        <TrendingUp className="h-6 w-6 text-emerald-600" />
                    </div>
                    <div>
                        <p className="text-sm font-medium text-slate-500">Total Shares Issued</p>
                        <h3 className="text-2xl font-bold text-slate-900">{totalSharesIssued.toLocaleString()} Units</h3>
                    </div>
                </div>

                <div className="bg-white p-6 rounded-xl shadow-sm border border-slate-200 flex items-center space-x-4">
                    <div className="bg-blue-100 p-3 rounded-lg">
                        <Users className="h-6 w-6 text-blue-600" />
                    </div>
                    <div>
                        <p className="text-sm font-medium text-slate-500">Active Shareholders</p>
                        <h3 className="text-2xl font-bold text-slate-900">{activeShareholders}</h3>
                    </div>
                </div>
            </div>

            {/* Main Content Card */}
            <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
                {/* Search & Filter Bar */}
                <div className="p-4 border-b border-slate-200 bg-slate-50/50 flex items-center justify-between">
                    <div className="relative w-full max-w-md">
                        <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                            <Search className="h-4 w-4 text-slate-400" />
                        </div>
                        <input
                            type="text"
                            placeholder="Search by shareholder name or ID..."
                            value={searchTerm}
                            onChange={(e) => setSearchTerm(e.target.value)}
                            className="block w-full pl-10 pr-3 py-2 border border-slate-300 rounded-lg leading-5 bg-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-indigo-500 sm:text-sm transition-colors"
                        />
                    </div>
                </div>

                {/* Data Table */}
                <div className="overflow-x-auto">
                    <table className="min-w-full divide-y divide-slate-200">
                        <thead className="bg-slate-50">
                            <tr>
                                <th scope="col" className="px-6 py-3 text-left text-xs font-semibold text-slate-500 uppercase tracking-wider">Shareholder</th>
                                <th scope="col" className="px-6 py-3 text-right text-xs font-semibold text-slate-500 uppercase tracking-wider">Shares Owned</th>
                                <th scope="col" className="px-6 py-3 text-right text-xs font-semibold text-slate-500 uppercase tracking-wider">Total Value</th>
                                <th scope="col" className="px-6 py-3 text-left text-xs font-semibold text-slate-500 uppercase tracking-wider">Last Activity</th>
                                <th scope="col" className="relative px-6 py-3"><span className="sr-only">Actions</span></th>
                            </tr>
                        </thead>
                        <tbody className="bg-white divide-y divide-slate-200">
                            {filteredAccounts.length > 0 ? (
                                filteredAccounts.map((account) => (
                                    <tr key={account.id} className="hover:bg-slate-50 transition-colors group">
                                        <td className="px-6 py-4 whitespace-nowrap">
                                            <div className="flex items-center">
                                                <div className="flex-shrink-0 h-8 w-8 bg-indigo-100 text-indigo-600 rounded-full flex items-center justify-center font-bold text-xs">
                                                    {account.member?.first_name?.charAt(0) || '-'}
                                                </div>
                                                <div className="ml-3">
                                                    <div className="text-sm font-medium text-slate-900">
                                                        {account.member?.first_name} {account.member?.last_name}
                                                    </div>
                                                    <div className="text-xs text-slate-500">ID: {account.member?.membership_id}</div>
                                                </div>
                                            </div>
                                        </td>
                                        <td className="px-6 py-4 whitespace-nowrap text-right">
                                            <span className="text-sm font-medium text-slate-900">{parseInt(account.total_shares).toLocaleString()}</span>
                                        </td>
                                        <td className="px-6 py-4 whitespace-nowrap text-right">
                                            <span className="text-sm font-bold text-slate-900">{formatCurrency(account.total_value)}</span>
                                        </td>
                                        <td className="px-6 py-4 whitespace-nowrap text-sm text-slate-500">
                                            {account.updated_at ? format(new Date(account.updated_at), 'MMM dd, yyyy') : 'N/A'}
                                        </td>
                                        <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                                            <div className="flex items-center justify-end space-x-2 opacity-0 group-hover:opacity-100 transition-opacity">
                                                {isManager && (
                                                    <button title="Transfer Shares" className="text-slate-400 hover:text-indigo-600 p-1 bg-slate-50 rounded transition-colors">
                                                        <ArrowRightLeft className="h-4 w-4" />
                                                    </button>
                                                )}
                                            </div>
                                        </td>
                                    </tr>
                                ))
                            ) : (
                                <tr>
                                    <td colSpan="5" className="px-6 py-12 text-center text-slate-500">
                                        <div className="flex flex-col items-center justify-center">
                                            <PieChart className="h-10 w-10 text-slate-300 mb-3" />
                                            <p className="text-base font-medium text-slate-900">No share records found</p>
                                            <p className="text-sm mt-1">When members purchase shares, their holdings will appear here.</p>
                                        </div>
                                    </td>
                                </tr>
                            )}
                        </tbody>
                    </table>
                </div>
            </div>

            {/* Success Toast */}
            {successMessage && (
                <div className="fixed bottom-4 right-4 bg-emerald-50 border-l-4 border-emerald-500 p-4 rounded shadow-lg animate-in fade-in slide-in-from-bottom-5 z-50">
                    <p className="text-sm text-emerald-700 font-medium">{successMessage}</p>
                </div>
            )}

            {/* Buy Shares Modal */}
            <BuySharesModal 
                isOpen={isModalOpen}
                onClose={() => setIsModalOpen(false)}
                onSuccess={(msg) => {
                    setIsModalOpen(false);
                    setSuccessMessage(msg);
                    fetchShares(); // Auto-refresh the capital totals!
                    setTimeout(() => setSuccessMessage(''), 5000);
                }}
            />
        </div>
    );
};

export default Shares;