import React, { useState, useEffect } from 'react';
import axiosInstance from '../../api/axios';
import { useAuth } from '../../hooks/useAuth';
import { 
    Search, Plus, ArrowDownCircle, ArrowUpCircle, History, AlertCircle, Loader2, Wallet, TrendingUp
} from 'lucide-react';
import { format } from 'date-fns';
import TransactionModal from '../../components/TransactionModal';

const Savings = () => {
    const { isManager } = useAuth();
    const [accounts, setAccounts] = useState([]); // Default to empty array
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');
    const [searchTerm, setSearchTerm] = useState('');
    
    // Modal State
    const [isModalOpen, setIsModalOpen] = useState(false);
    const [transactionType, setTransactionType] = useState('DEPOSIT');
    const [successMessage, setSuccessMessage] = useState('');

    const fetchSavings = async () => {
        try {
            setLoading(true);
            setError('');
            // This hits: /api/v1/savings/accounts/ based on your urls.py
            const response = await axiosInstance.get('/savings/accounts/');
            const data = response.data.results || response.data;
            
            // Critical Check: Ensure we only store an array
            setAccounts(Array.isArray(data) ? data : []);
        } catch (err) {
            console.error("Failed to fetch savings:", err);
            setError('Failed to load savings data. Please ensure the backend server is running.');
            setAccounts([]); 
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchSavings();
    }, []);

    // Stats Calculations with safety guards
    const totalSavingsPool = accounts.reduce((sum, acc) => sum + parseFloat(acc.balance || 0), 0);
    const activeAccountsCount = accounts.filter(acc => parseFloat(acc.balance) > 0).length;

    // Filter accounts with protection against undefined member objects
    const filteredAccounts = accounts.filter(account => {
        const firstName = account.member?.first_name || '';
        const lastName = account.member?.last_name || '';
        const memberName = `${firstName} ${lastName}`.toLowerCase();
        const memberId = account.member?.membership_id?.toLowerCase() || '';
        const accNum = account.account_number?.toLowerCase() || '';
        const search = searchTerm.toLowerCase();
        
        return memberName.includes(search) || memberId.includes(search) || accNum.includes(search);
    });

    const formatCurrency = (amount) => {
        return new Intl.NumberFormat('en-NG', { 
            style: 'currency', 
            currency: 'NGN',
            minimumFractionDigits: 2 
        }).format(amount || 0);
    };

    if (loading) {
        return (
            <div className="flex h-64 items-center justify-center">
                <Loader2 className="animate-spin h-8 w-8 text-blue-500" />
            </div>
        );
    }

    return (
        <div className="space-y-6">
            {/* Header Section */}
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                <div>
                    <h1 className="text-2xl font-black text-slate-900 tracking-tight">Savings Management</h1>
                    <p className="text-sm text-slate-500 font-medium">Global view of member wallets and total liquidity.</p>
                </div>
                
                {isManager && (
                    <div className="flex space-x-3">
                        <button 
                            onClick={() => { setTransactionType('DEPOSIT'); setIsModalOpen(true); }}
                            className="inline-flex items-center px-4 py-2 bg-emerald-600 text-white text-sm font-bold rounded-xl hover:bg-emerald-700 transition-all shadow-lg shadow-emerald-100"
                        >
                            <ArrowDownCircle className="h-4 w-4 mr-2" />
                            Record Deposit
                        </button>
                        <button 
                            onClick={() => { setTransactionType('WITHDRAWAL'); setIsModalOpen(true); }}
                            className="inline-flex items-center px-4 py-2 bg-white border border-slate-200 text-slate-700 text-sm font-bold rounded-xl hover:bg-slate-50 transition-all shadow-sm"
                        >
                            <ArrowUpCircle className="h-4 w-4 mr-2 text-amber-500" />
                            Withdraw
                        </button>
                    </div>
                )}
            </div>

            {/* Stats Overview */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div className="bg-white p-6 rounded-2xl shadow-sm border border-slate-100 flex items-center space-x-4">
                    <div className="bg-blue-100 p-3 rounded-xl text-blue-600">
                        <Wallet className="h-6 w-6" />
                    </div>
                    <div>
                        <p className="text-xs font-bold text-slate-400 uppercase tracking-widest">Total Savings Pool</p>
                        <h3 className="text-2xl font-black text-slate-900">{formatCurrency(totalSavingsPool)}</h3>
                    </div>
                </div>
                <div className="bg-white p-6 rounded-2xl shadow-sm border border-slate-100 flex items-center space-x-4">
                    <div className="bg-emerald-100 p-3 rounded-xl text-emerald-600">
                        <TrendingUp className="h-6 w-6" />
                    </div>
                    <div>
                        <p className="text-xs font-bold text-slate-400 uppercase tracking-widest">Active Accounts</p>
                        <h3 className="text-2xl font-black text-slate-900">{activeAccountsCount} Members</h3>
                    </div>
                </div>
            </div>

            {/* Main Table Card */}
            <div className="bg-white rounded-2xl shadow-sm border border-slate-200 overflow-hidden">
                <div className="p-4 border-b border-slate-200 bg-slate-50/50 flex items-center">
                    <div className="relative w-full max-w-md">
                        <Search className="absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
                        <input
                            type="text"
                            placeholder="Search by name, account # or ID..."
                            value={searchTerm}
                            onChange={(e) => setSearchTerm(e.target.value)}
                            className="block w-full pl-10 pr-3 py-2 border border-slate-300 rounded-xl bg-white text-sm outline-none focus:ring-2 focus:ring-blue-500 transition-all"
                        />
                    </div>
                </div>

                <div className="overflow-x-auto">
                    <table className="min-w-full divide-y divide-slate-200">
                        <thead className="bg-slate-50">
                            <tr>
                                <th className="px-6 py-4 text-left text-[10px] font-bold text-slate-500 uppercase tracking-widest">Member</th>
                                <th className="px-6 py-4 text-left text-[10px] font-bold text-slate-500 uppercase tracking-widest">Account No.</th>
                                <th className="px-6 py-4 text-right text-[10px] font-bold text-slate-500 uppercase tracking-widest">Balance</th>
                                <th className="px-6 py-4 text-left text-[10px] font-bold text-slate-500 uppercase tracking-widest">Last Activity</th>
                                <th className="relative px-6 py-4"><span className="sr-only">Actions</span></th>
                            </tr>
                        </thead>
                        <tbody className="bg-white divide-y divide-slate-100">
                            {filteredAccounts.length > 0 ? (
                                filteredAccounts.map((account) => (
                                    <tr key={account.id} className="hover:bg-slate-50 transition-colors group">
                                        <td className="px-6 py-4 whitespace-nowrap">
                                            <div className="flex items-center">
                                                <div className="h-8 w-8 bg-blue-50 text-blue-600 rounded-full flex items-center justify-center font-bold text-xs border border-blue-100">
                                                    {account.member?.first_name?.[0]}{account.member?.last_name?.[0]}
                                                </div>
                                                <div className="ml-3">
                                                    <div className="text-sm font-bold text-slate-900">{account.member?.first_name} {account.member?.last_name}</div>
                                                    <div className="text-[10px] text-slate-400 font-mono">ID: {account.member?.membership_id}</div>
                                                </div>
                                            </div>
                                        </td>
                                        <td className="px-6 py-4 whitespace-nowrap font-mono text-xs text-slate-600">
                                            {account.account_number || 'PENDING'}
                                        </td>
                                        <td className="px-6 py-4 whitespace-nowrap text-right">
                                            <span className="text-sm font-black text-slate-900">{formatCurrency(account.balance)}</span>
                                        </td>
                                        <td className="px-6 py-4 whitespace-nowrap text-xs text-slate-500 font-medium">
                                            {account.updated_at ? format(new Date(account.updated_at), 'MMM dd, yyyy') : 'No history'}
                                        </td>
                                        <td className="px-6 py-4 whitespace-nowrap text-right">
                                            <button className="p-1.5 text-slate-400 hover:text-blue-600 hover:bg-blue-50 rounded-lg transition-all opacity-0 group-hover:opacity-100">
                                                <History className="h-4 w-4" />
                                            </button>
                                        </td>
                                    </tr>
                                ))
                            ) : (
                                <tr>
                                    <td colSpan="5" className="px-6 py-12 text-center text-slate-500 italic">
                                        <div className="flex flex-col items-center justify-center">
                                            <Wallet className="h-8 w-8 text-slate-200 mb-2" />
                                            <p className="text-sm">No savings accounts match your search.</p>
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
                <div className="fixed bottom-6 right-6 bg-slate-900 text-white px-6 py-3 rounded-xl shadow-2xl animate-in slide-in-from-bottom-5 z-[60] flex items-center font-bold text-sm">
                    <TrendingUp className="h-4 w-4 text-emerald-400 mr-2" />
                    {successMessage}
                </div>
            )}

            {/* Transaction Modal */}
            <TransactionModal 
                isOpen={isModalOpen}
                onClose={() => setIsModalOpen(false)}
                type={transactionType}
                // We pass accounts here to the modal
                accounts={accounts} 
                onSuccess={(msg) => {
                    setSuccessMessage(msg);
                    fetchSavings(); // Refresh data after transaction
                    setTimeout(() => setSuccessMessage(''), 4000);
                }}
            />
        </div>
    );
};

export default Savings;