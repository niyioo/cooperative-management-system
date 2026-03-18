import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import axiosInstance from '../../api/axios';
import { useAuth } from '../../hooks/useAuth';
import { 
    Wallet, PieChart, Landmark, Clock, ArrowRight, FileText, AlertCircle, Loader2, Download
} from 'lucide-react';
import { format } from 'date-fns';

const StatCard = ({ title, value, subtitle, icon: Icon, colorClass }) => (
    <div className="bg-white rounded-2xl shadow-sm border border-slate-100 p-6 flex flex-col justify-between hover:shadow-lg hover:-translate-y-1 transition-all duration-300">
        <div className="flex justify-between items-start mb-4">
            <div className={`p-3 rounded-xl shadow-sm ${colorClass}`}>
                <Icon className="h-6 w-6 text-white" />
            </div>
        </div>
        <div>
            <p className="text-xs font-black text-slate-400 uppercase tracking-widest mb-1">{title}</p>
            <h3 className="text-2xl font-bold text-slate-800">{value}</h3>
            {subtitle && <p className="text-[10px] font-bold text-slate-400 uppercase mt-2">{subtitle}</p>}
        </div>
    </div>
);

const MemberDashboard = () => {
    const { user } = useAuth();
    const navigate = useNavigate();
    const [summary, setSummary] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');
    const [isDownloading, setIsDownloading] = useState(false);

    useEffect(() => {
        const fetchSummary = async () => {
            try {
                const response = await axiosInstance.get('/reports/dashboard-summary/');
                setSummary(response.data);
            } catch (err) {
                console.error("Failed to fetch member summary", err);
                setError("Live connection lost. Displaying fallback data.");
                setSummary({
                    total_savings: 0,
                    total_shares_value: 0,
                    outstanding_loan_balance: 0,
                    pending_dues: 0,
                    recent_transactions: []
                });
            } finally {
                setLoading(false);
            }
        };
        fetchSummary();
    }, []);

    // ✅ FIXED: Handle Statement Download via Backend
    const handleDownloadStatement = async () => {
        setIsDownloading(true);
        try {
            const response = await axiosInstance.get('/reports/dashboard-summary/export_pdf/', {
                responseType: 'blob', // Critical for binary files
            });
            const url = window.URL.createObjectURL(new Blob([response.data]));
            const link = document.createElement('a');
            link.href = url;
            link.setAttribute('download', `My_BravEdge_Statement_${format(new Date(), 'yyyy-MM-dd')}.pdf`);
            document.body.appendChild(link);
            link.click();
            link.remove();
            window.URL.revokeObjectURL(url);
        } catch (err) {
            console.error("Statement download failed", err);
            alert("Failed to generate statement. Please try again later.");
        } finally {
            setIsDownloading(false);
        }
    };

    const formatCurrency = (amount) => {
        const validAmount = parseFloat(amount) || 0;
        return new Intl.NumberFormat('en-NG', { style: 'currency', currency: 'NGN' }).format(validAmount);
    };

    if (loading) return (
        <div className="flex h-[80vh] items-center justify-center">
            <Loader2 className="animate-spin h-10 w-10 text-blue-600" />
        </div>
    );

    return (
        <div className="space-y-6 animate-in fade-in duration-500">
            {/* Header Section */}
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-slate-900 p-8 rounded-3xl border border-slate-800 shadow-xl text-white">
                <div>
                    <h1 className="text-2xl font-black tracking-tight">
                        Welcome back, {user?.first_name || 'Member'}! 👋
                    </h1>
                    <p className="text-xs font-medium text-slate-400 mt-2 tracking-wide">
                        Here is your real-time cooperative financial summary.
                    </p>
                </div>
                <div className="flex space-x-3">
                    <button 
                        onClick={handleDownloadStatement}
                        disabled={isDownloading}
                        className="inline-flex items-center justify-center px-5 py-2.5 bg-white text-slate-900 text-sm font-black rounded-xl hover:bg-blue-50 transition-all active:scale-95 shadow-lg disabled:opacity-50"
                    >
                        {isDownloading ? <Loader2 className="animate-spin h-4 w-4 mr-2" /> : <Download className="h-4 w-4 mr-2" />}
                        Statement
                    </button>
                </div>
            </div>

            {error && (
                <div className="bg-amber-50 border-l-4 border-amber-500 p-4 rounded-r-lg flex items-center">
                    <AlertCircle className="h-5 w-5 text-amber-500 mr-2" />
                    <p className="text-xs font-bold text-amber-700 uppercase tracking-tight">{error}</p>
                </div>
            )}

            {/* Stats Grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
                <StatCard 
                    title="My Savings" 
                    value={formatCurrency(summary?.total_savings)} 
                    subtitle="Available Pool"
                    icon={Wallet} 
                    colorClass="bg-emerald-500" 
                />
                <StatCard 
                    title="Share Capital" 
                    value={formatCurrency(summary?.total_shares_value)} 
                    subtitle="Active Shares"
                    icon={PieChart} 
                    colorClass="bg-blue-600" 
                />
                <StatCard 
                    title="Outstanding Loan" 
                    value={formatCurrency(summary?.outstanding_loan_balance)} 
                    subtitle={summary?.outstanding_loan_balance > 0 ? "Active Balance" : "No active loans"}
                    icon={Landmark} 
                    colorClass="bg-indigo-600" 
                />
                <StatCard 
                    title="Pending Dues" 
                    value={formatCurrency(summary?.pending_dues || 0)} 
                    subtitle={summary?.pending_dues > 0 ? "Action required" : "All caught up!"}
                    icon={Clock} 
                    colorClass={summary?.pending_dues > 0 ? "bg-red-500" : "bg-slate-400"} 
                />
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                {/* Recent Transactions Table */}
                <div className="lg:col-span-2 bg-white rounded-3xl shadow-sm border border-slate-100 overflow-hidden">
                    <div className="p-6 border-b border-slate-50 flex justify-between items-center bg-slate-50/50">
                        <h2 className="text-sm font-black text-slate-800 uppercase tracking-widest">Recent Transactions</h2>
                        <button 
                            onClick={() => navigate('/finance-ledger')}
                            className="text-[10px] text-blue-600 hover:text-blue-800 font-bold uppercase tracking-widest flex items-center transition-colors"
                        >
                            View all <ArrowRight className="h-3 w-3 ml-1" />
                        </button>
                    </div>
                    <div className="overflow-x-auto">
                        <table className="min-w-full divide-y divide-slate-50">
                            <tbody className="bg-white divide-y divide-slate-50">
                                {summary?.recent_transactions?.length > 0 ? (
                                    summary.recent_transactions.map((tx) => (
                                        <tr key={tx.id} className="hover:bg-slate-50 transition-colors group">
                                            <td className="px-6 py-4 whitespace-nowrap">
                                                <div className="flex items-center">
                                                    <div className={`p-2.5 rounded-xl mr-4 shadow-sm transition-transform group-hover:scale-110 ${
                                                        tx.type === 'INCOME' || tx.type === 'DEPOSIT' ? 'bg-emerald-100 text-emerald-600' : 'bg-red-100 text-red-600'
                                                    }`}>
                                                        <FileText className="h-4 w-4" />
                                                    </div>
                                                    <div>
                                                        <p className="text-sm font-bold text-slate-800">{tx.description}</p>
                                                        <p className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mt-0.5">
                                                            {format(new Date(tx.date), 'MMM dd, yyyy')}
                                                        </p>
                                                    </div>
                                                </div>
                                            </td>
                                            <td className="px-6 py-4 whitespace-nowrap text-right">
                                                <span className={`text-sm font-black ${
                                                    tx.type === 'INCOME' || tx.type === 'DEPOSIT' ? 'text-emerald-500' : 'text-slate-900'
                                                }`}>
                                                    {tx.type === 'INCOME' || tx.type === 'DEPOSIT' ? '+' : '-'}{formatCurrency(tx.amount)}
                                                </span>
                                            </td>
                                        </tr>
                                    ))
                                ) : (
                                    <tr>
                                        <td colSpan="2" className="px-6 py-16 text-center">
                                            <div className="flex flex-col items-center justify-center text-slate-400">
                                                <FileText className="h-10 w-10 mb-3 opacity-10" />
                                                <p className="text-xs font-bold uppercase tracking-widest">No recent transactions found.</p>
                                            </div>
                                        </td>
                                    </tr>
                                )}
                            </tbody>
                        </table>
                    </div>
                </div>

                {/* Quick Actions Panel */}
                <div className="bg-slate-900 rounded-3xl shadow-xl border border-slate-800 p-8 text-white">
                    <h2 className="text-sm font-black uppercase tracking-widest mb-6 text-blue-400">Quick Actions</h2>
                    <div className="space-y-4">
                        <button 
                            onClick={() => navigate('/savings')}
                            className="w-full flex items-center justify-between p-4 bg-slate-800/50 rounded-2xl hover:bg-slate-800 transition-colors group border border-slate-700/50"
                        >
                            <div className="flex items-center">
                                <Wallet className="h-5 w-5 mr-3 text-emerald-400" />
                                <span className="font-bold text-sm tracking-tight">Make a Deposit</span>
                            </div>
                            <ArrowRight className="h-4 w-4 text-slate-500 group-hover:text-emerald-400 group-hover:translate-x-1 transition-all" />
                        </button>
                        
                        <button 
                            onClick={() => navigate('/loans')}
                            className="w-full flex items-center justify-between p-4 bg-slate-800/50 rounded-2xl hover:bg-slate-800 transition-colors group border border-slate-700/50"
                        >
                            <div className="flex items-center">
                                <Landmark className="h-5 w-5 mr-3 text-indigo-400" />
                                <span className="font-bold text-sm tracking-tight">Apply for a Loan</span>
                            </div>
                            <ArrowRight className="h-4 w-4 text-slate-500 group-hover:text-indigo-400 group-hover:translate-x-1 transition-all" />
                        </button>

                        <button 
                            onClick={() => navigate('/contributions')}
                            className="w-full flex items-center justify-between p-4 bg-slate-800/50 rounded-2xl hover:bg-slate-800 transition-colors group border border-slate-700/50"
                        >
                            <div className="flex items-center">
                                <Clock className="h-5 w-5 mr-3 text-amber-400" />
                                <span className="font-bold text-sm tracking-tight">Pay Dues</span>
                            </div>
                            <ArrowRight className="h-4 w-4 text-slate-500 group-hover:text-amber-400 group-hover:translate-x-1 transition-all" />
                        </button>
                    </div>
                </div>
            </div>
        </div>
    );
};

export default MemberDashboard;