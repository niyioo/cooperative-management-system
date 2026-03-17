import React, { useEffect, useState } from 'react';
import axiosInstance from '../../api/axios';
import { useAuth } from '../../hooks/useAuth';
import { 
    Users, Wallet, Landmark, TrendingUp, Loader2 
} from 'lucide-react';
import { 
    BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer 
} from 'recharts';

const StatCard = ({ title, value, icon: Icon, colorClass }) => (
    <div className="bg-white rounded-xl shadow-sm border border-slate-100 p-6 flex items-center">
        <div className={`p-4 rounded-lg mr-4 ${colorClass}`}>
            <Icon className="h-6 w-6 text-white" />
        </div>
        <div>
            <p className="text-sm font-medium text-slate-500 mb-1">{title}</p>
            <h3 className="text-2xl font-bold text-slate-800">{value}</h3>
        </div>
    </div>
);

const AdminDashboard = () => {
    const { user, isManager } = useAuth();
    const [summary, setSummary] = useState(null);
    const [loading, setLoading] = useState(true);

    // Mock data for the chart to make the dashboard look complete 
    // In production, this would come from a specific time-series endpoint
    const mockChartData = [
        { month: 'Jan', income: 4000, expenses: 2400 },
        { month: 'Feb', income: 3000, expenses: 1398 },
        { month: 'Mar', income: 2000, expenses: 9800 },
        { month: 'Apr', income: 2780, expenses: 3908 },
        { month: 'May', income: 1890, expenses: 4800 },
        { month: 'Jun', income: 2390, expenses: 3800 },
        { month: 'Jul', income: 3490, expenses: 4300 },
    ];

    useEffect(() => {
        const fetchSummary = async () => {
            try {
                const response = await axiosInstance.get('/reports/dashboard-summary/');
                setSummary(response.data);
            } catch (error) {
                console.error("Failed to fetch dashboard summary", error);
            } finally {
                setLoading(false);
            }
        };

        fetchSummary();
    }, []);

    const formatCurrency = (amount) => {
        return new Intl.NumberFormat('en-NG', { style: 'currency', currency: 'NGN' }).format(amount || 0);
    };

    if (loading) {
        return (
            <div className="flex h-full items-center justify-center">
                <Loader2 className="animate-spin h-8 w-8 text-blue-500" />
            </div>
        );
    }

    if (!isManager && summary?.role === 'MEMBER') {
        // Fallback for regular members
        return (
            <div>
                <h1 className="text-2xl font-bold text-slate-900 mb-6">Welcome back, Member</h1>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                    <StatCard title="Total Savings" value={formatCurrency(summary.total_savings)} icon={Wallet} colorClass="bg-blue-500" />
                    <StatCard title="Total Shares Value" value={formatCurrency(summary.total_shares_value)} icon={PieChart} colorClass="bg-purple-500" />
                    <StatCard title="Outstanding Loan" value={formatCurrency(summary.outstanding_loan_balance)} icon={Landmark} colorClass="bg-red-500" />
                </div>
            </div>
        );
    }

    return (
        <div className="space-y-6">
            <div className="flex items-center justify-between">
                <h1 className="text-2xl font-bold text-slate-900">Cooperative Overview</h1>
                <span className="bg-blue-100 text-blue-800 text-xs font-semibold px-2.5 py-0.5 rounded">
                    Admin Privileges
                </span>
            </div>

            {/* Top Stats Grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
                <StatCard 
                    title="Active Members" 
                    value={summary?.members?.active || 0} 
                    icon={Users} 
                    colorClass="bg-blue-500" 
                />
                <StatCard 
                    title="Total Savings Pool" 
                    value={formatCurrency(summary?.financials?.total_savings)} 
                    icon={Wallet} 
                    colorClass="bg-emerald-500" 
                />
                <StatCard 
                    title="Active Loans Disbursed" 
                    value={formatCurrency(summary?.financials?.total_loans_disbursed)} 
                    icon={Landmark} 
                    colorClass="bg-indigo-500" 
                />
                <StatCard 
                    title="Net Profit (Income - Exp.)" 
                    value={formatCurrency(summary?.financials?.net_profit)} 
                    icon={TrendingUp} 
                    colorClass="bg-violet-500" 
                />
            </div>

            {/* Charts & Details Section */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mt-6">
                
                {/* Main Chart */}
                <div className="lg:col-span-2 bg-white rounded-xl shadow-sm border border-slate-100 p-6">
                    <h2 className="text-lg font-semibold text-slate-800 mb-4">Financial Growth (Mock Trend)</h2>
                    <div className="h-80">
                        <ResponsiveContainer width="100%" height="100%">
                            <BarChart data={mockChartData} margin={{ top: 5, right: 30, left: 20, bottom: 5 }}>
                                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" />
                                <XAxis dataKey="month" axisLine={false} tickLine={false} />
                                <YAxis axisLine={false} tickLine={false} tickFormatter={(val) => `₦${val/1000}k`} />
                                <Tooltip cursor={{fill: '#f8fafc'}} />
                                <Legend />
                                <Bar dataKey="income" name="Income" fill="#3b82f6" radius={[4, 4, 0, 0]} />
                                <Bar dataKey="expenses" name="Expenses" fill="#ef4444" radius={[4, 4, 0, 0]} />
                            </BarChart>
                        </ResponsiveContainer>
                    </div>
                </div>

                {/* Quick Snapshot List */}
                <div className="bg-white rounded-xl shadow-sm border border-slate-100 p-6">
                    <h2 className="text-lg font-semibold text-slate-800 mb-4">Financial Snapshot</h2>
                    <div className="space-y-4">
                        <div className="flex justify-between items-center pb-4 border-b border-slate-100">
                            <span className="text-slate-500">Total Share Capital</span>
                            <span className="font-semibold text-slate-800">{formatCurrency(summary?.financials?.total_shares)}</span>
                        </div>
                        <div className="flex justify-between items-center pb-4 border-b border-slate-100">
                            <span className="text-slate-500">Outstanding Loan Balance</span>
                            <span className="font-semibold text-amber-600">{formatCurrency(summary?.financials?.outstanding_loans)}</span>
                        </div>
                        <div className="flex justify-between items-center pb-4 border-b border-slate-100">
                            <span className="text-slate-500">Total Coop Income</span>
                            <span className="font-semibold text-emerald-600">{formatCurrency(summary?.financials?.coop_income)}</span>
                        </div>
                        <div className="flex justify-between items-center">
                            <span className="text-slate-500">Total Coop Expenses</span>
                            <span className="font-semibold text-red-600">{formatCurrency(summary?.financials?.coop_expenses)}</span>
                        </div>
                    </div>
                    
                    <button className="w-full mt-6 bg-slate-50 hover:bg-slate-100 text-slate-700 font-medium py-2 px-4 rounded-lg border border-slate-200 transition-colors">
                        Generate Full Report
                    </button>
                </div>
            </div>
        </div>
    );
};

export default AdminDashboard;