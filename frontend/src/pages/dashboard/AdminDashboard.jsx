import React, { useEffect, useState } from 'react';
import axiosInstance from '../../api/axios';
import { useAuth } from '../../hooks/useAuth';
import { useNavigate } from 'react-router-dom';
import { 
    Users, Wallet, Landmark, TrendingUp, Loader2, PieChart, AlertCircle, FileDown, CheckCircle
} from 'lucide-react';
import { 
    BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer 
} from 'recharts';
import MemberDashboard from './MemberDashboard';

const StatCard = ({ title, value, icon: Icon, colorClass }) => (
    <div className="bg-white rounded-xl shadow-sm border border-slate-100 p-6 flex items-center transition-transform hover:scale-[1.02]">
        <div className={`p-4 rounded-lg mr-4 ${colorClass}`}>
            <Icon className="h-6 w-6 text-white" />
        </div>
        <div>
            <p className="text-xs font-black text-slate-400 uppercase tracking-widest mb-1">{title}</p>
            <h3 className="text-2xl font-bold text-slate-800">{value}</h3>
        </div>
    </div>
);

const AdminDashboard = () => {
    const { user, isManager } = useAuth();
    const navigate = useNavigate();
    const [summary, setSummary] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');
    const [isGeneratingPdf, setIsGeneratingPdf] = useState(false);

    useEffect(() => {
        const fetchSummary = async () => {
            try {
                const response = await axiosInstance.get('/reports/dashboard-summary/');
                setSummary(response.data);
            } catch (err) {
                console.error("Dashboard fetch error:", err);
                setError('Live connection lost. Showing fallback data.');
                setSummary({
                    role: 'ADMIN',
                    members: { active: 0 },
                    financials: { total_savings: 0, total_loans_disbursed: 0, net_profit: 0 },
                    chart_data: [] 
                });
            } finally {
                setLoading(false);
            }
        };
        fetchSummary();
    }, []);

    const formatCurrency = (amount) => {
        const val = parseFloat(amount) || 0;
        return new Intl.NumberFormat('en-NG', { style: 'currency', currency: 'NGN' }).format(val);
    };

    const downloadFullReport = async () => {
        if (!summary) return;
        setIsGeneratingPdf(true);
        try {
            const response = await axiosInstance.get('/reports/dashboard-summary/export_pdf/', {
                responseType: 'blob',
            });

            const url = window.URL.createObjectURL(new Blob([response.data]));
            const link = document.createElement('a');
            link.href = url;
            link.setAttribute('download', `BravEdge_Executive_Report_${new Date().toISOString().split('T')[0]}.pdf`);
            document.body.appendChild(link);
            link.click();
            
            link.remove();
            window.URL.revokeObjectURL(url);
        } catch (e) {
            console.error("Backend PDF generation failed", e);
            alert('Failed to generate high-quality report. Please check server.');
        } finally {
            setIsGeneratingPdf(false);
        }
    };

    if (loading) return (
        <div className="flex h-[80vh] items-center justify-center">
            <Loader2 className="animate-spin h-10 w-10 text-blue-600" />
        </div>
    );

    if (!isManager) return <MemberDashboard />;

    return (
        <div className="space-y-6 animate-in fade-in duration-500">
            {/* Header */}
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                <div className="flex items-center space-x-3">
                    <div 
                        onClick={() => navigate('/settings')}
                        className="h-12 w-12 rounded-full bg-slate-900 flex items-center justify-center text-white font-bold cursor-pointer hover:ring-4 ring-blue-50 transition-all shadow-lg"
                    >
                        {user?.email?.[0].toUpperCase() || 'A'}
                    </div>
                    <div>
                        <h1 className="text-2xl font-black text-slate-900 tracking-tight">Cooperative Overview</h1>
                        <p className="text-xs font-bold text-blue-600 uppercase tracking-tighter">System Administrator</p>
                    </div>
                </div>
            </div>

            {error && (
                <div className="bg-amber-50 border-l-4 border-amber-500 p-4 rounded-r-lg flex items-center">
                    <AlertCircle className="h-5 w-5 text-amber-500 mr-2" />
                    <p className="text-xs font-bold text-amber-700 uppercase tracking-tight">{error}</p>
                </div>
            )}

            {/* Live Stats */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
                <StatCard title="Active Members" value={summary?.members?.active || 0} icon={Users} colorClass="bg-blue-600" />
                <StatCard title="Savings Pool" value={formatCurrency(summary?.financials?.total_savings)} icon={Wallet} colorClass="bg-emerald-600" />
                <StatCard title="Loans Active" value={formatCurrency(summary?.financials?.total_loans_disbursed)} icon={Landmark} colorClass="bg-indigo-600" />
                <StatCard title="Net Profit" value={formatCurrency(summary?.financials?.net_profit)} icon={TrendingUp} colorClass="bg-slate-900" />
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                {/* Financial Performance Chart */}
                <div className="lg:col-span-2 bg-white rounded-2xl shadow-sm border border-slate-100 p-6">
                    <div className="flex items-center justify-between mb-6">
                        <h2 className="text-lg font-bold text-slate-800">Financial Performance</h2>
                        <div className="flex items-center text-[10px] font-bold text-slate-400 uppercase tracking-widest">
                            <CheckCircle className="h-3 w-3 mr-1 text-emerald-500" /> Live Data
                        </div>
                    </div>
                    <div className="h-80">
                        <ResponsiveContainer width="100%" height="100%">
                            <BarChart data={summary?.chart_data || []}>
                                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                                <XAxis dataKey="month" axisLine={false} tickLine={false} tick={{fill: '#94a3b8', fontSize: 10, fontWeight: 'bold'}} />
                                <YAxis axisLine={false} tickLine={false} tick={{fill: '#94a3b8', fontSize: 10}} tickFormatter={(val) => `₦${val >= 1000 ? val/1000 + 'k' : val}`} />
                                <Tooltip cursor={{fill: '#f8fafc'}} contentStyle={{borderRadius: '12px', border: 'none', boxShadow: '0 10px 15px -3px rgb(0 0 0 / 0.1)'}} />
                                <Bar dataKey="income" name="Income" fill="#10b981" radius={[4, 4, 0, 0]} barSize={30} />
                                <Bar dataKey="expenses" name="Expenses" fill="#f43f5e" radius={[4, 4, 0, 0]} barSize={30} />
                                <Legend wrapperStyle={{paddingTop: '20px', fontSize: '12px', fontWeight: 'bold'}} />
                            </BarChart>
                        </ResponsiveContainer>
                    </div>
                </div>

                {/* Treasury Snapshot & Enhanced Button */}
                <div className="bg-slate-900 rounded-3xl p-8 text-white shadow-2xl flex flex-col justify-between">
                    <div>
                        <h2 className="text-xl font-black mb-8 flex items-center tracking-tight text-blue-400">
                            <PieChart className="h-6 w-6 mr-3" />
                            Treasury Snapshot
                        </h2>
                        <div className="space-y-6">
                            <div className="flex justify-between border-b border-slate-800 pb-4">
                                <span className="text-slate-400 text-xs font-bold uppercase tracking-widest">Share Capital</span>
                                <span className="font-bold text-white">{formatCurrency(summary?.financials?.total_shares)}</span>
                            </div>
                            <div className="flex justify-between border-b border-slate-800 pb-4">
                                <span className="text-slate-400 text-xs font-bold uppercase tracking-widest">Gross Income</span>
                                <span className="font-bold text-emerald-400">{formatCurrency(summary?.financials?.coop_income)}</span>
                            </div>
                            <div className="flex justify-between">
                                <span className="text-slate-400 text-xs font-bold uppercase tracking-widest">Total Expenses</span>
                                <span className="font-bold text-rose-400">{formatCurrency(summary?.financials?.coop_expenses)}</span>
                            </div>
                        </div>
                    </div>
                    
                    {/* Finer and Bolder Button */}
                    <button 
                        onClick={downloadFullReport}
                        disabled={isGeneratingPdf}
                        className="
                            w-full mt-12 py-4 px-6 
                            bg-white text-slate-900 
                            hover:bg-blue-50 hover:text-blue-700
                            active:scale-[0.98] 
                            rounded-2xl 
                            font-black uppercase tracking-widest text-[11px]
                            flex items-center justify-center 
                            transition-all duration-200
                            shadow-[0_0_20px_rgba(59,130,246,0.15)] 
                            hover:shadow-[0_0_25px_rgba(59,130,246,0.3)]
                            disabled:opacity-50 disabled:cursor-not-allowed
                            border border-transparent hover:border-blue-200
                        "
                    >
                        {isGeneratingPdf ? (
                            <Loader2 className="animate-spin h-5 w-5 mr-3" />
                        ) : (
                            <>
                                <FileDown className="h-5 w-5 mr-3 stroke-[2.5]" /> 
                                Generate Executive Report
                            </>
                        )}
                    </button>
                </div>
            </div>
        </div>
    );
};

export default AdminDashboard;