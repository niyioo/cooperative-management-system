import React, { useState, useEffect, useCallback } from 'react';
import axiosInstance from '../../api/axios';
import RecordTransactionModal from '../../components/RecordTransactionModal';
import { 
    Search, Download, Plus, ArrowUpRight, ArrowDownRight, Loader2, Filter, AlertCircle
} from 'lucide-react';
import { format } from 'date-fns';

const FinanceLedger = () => {
    const [transactions, setTransactions] = useState([]);
    const [loading, setLoading] = useState(true);
    const [searchTerm, setSearchTerm] = useState('');
    const [filterType, setFilterType] = useState('ALL'); 
    const [error, setError] = useState(null);
    const [isModalOpen, setIsModalOpen] = useState(false);
    const [exporting, setExporting] = useState(false);

    const fetchLedger = useCallback(async () => {
        try {
            setError(null);
            const response = await axiosInstance.get('/finance/ledger/');
            const data = Array.isArray(response.data) ? response.data : 
                         (response.data.results && Array.isArray(response.data.results)) ? response.data.results : [];
            setTransactions(data);
        } catch (error) {
            console.error("Failed to fetch ledger:", error);
            setError("Could not load transaction data. Check your connection.");
            setTransactions([]); 
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        fetchLedger();
    }, [fetchLedger]);

    const handleExport = async () => {
        setExporting(true);
        try {
            const response = await axiosInstance.get('/finance/ledger/export_pdf/', {
                responseType: 'blob',
                params: {
                    type: filterType !== 'ALL' ? filterType : '',
                    search: searchTerm
                }
            });
            const url = window.URL.createObjectURL(new Blob([response.data]));
            const link = document.createElement('a');
            link.href = url;
            link.setAttribute('download', `BravEdge_Statement_${format(new Date(), 'yyyyMMdd')}.pdf`);
            document.body.appendChild(link);
            link.click();
            link.remove();
        } catch (err) {
            console.error("Export failed", err);
            alert("Failed to generate PDF report.");
        } finally {
            setExporting(false);
        }
    };

    const formatCurrency = (amount) => {
        return new Intl.NumberFormat('en-NG', { style: 'currency', currency: 'NGN' }).format(amount || 0);
    };

    const filteredTransactions = (Array.isArray(transactions) ? transactions : []).filter(tx => {
        const matchesFilter = filterType === 'ALL' || tx.type === filterType;
        const ref = tx.reference_id || '';
        const cat = tx.category || '';
        const member = tx.member_name || '';
        const desc = tx.description || '';

        const matchesSearch = 
            ref.toLowerCase().includes(searchTerm.toLowerCase()) ||
            cat.toLowerCase().includes(searchTerm.toLowerCase()) ||
            member.toLowerCase().includes(searchTerm.toLowerCase()) ||
            desc.toLowerCase().includes(searchTerm.toLowerCase());
        
        return matchesFilter && matchesSearch;
    });

    if (loading) return (
        <div className="flex h-[80vh] items-center justify-center">
            <Loader2 className="animate-spin h-10 w-10 text-blue-600" />
        </div>
    );

    return (
        <div className="space-y-6 animate-in fade-in duration-500">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                <div>
                    <h1 className="text-2xl font-black text-slate-900 tracking-tight">Finance Ledger</h1>
                    <p className="text-xs font-bold text-slate-400 uppercase tracking-widest mt-1">Master Account History</p>
                </div>
                <div className="flex space-x-3">
                    <button 
                        onClick={handleExport}
                        disabled={exporting}
                        className="px-4 py-2.5 bg-white border border-slate-200 text-slate-700 text-sm font-bold rounded-xl hover:bg-slate-50 transition-colors flex items-center shadow-sm disabled:opacity-50"
                    >
                        {exporting ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <Download className="h-4 w-4 mr-2" />}
                        Export PDF
                    </button>
                    <button 
                        onClick={() => setIsModalOpen(true)}
                        className="px-5 py-2.5 bg-blue-600 text-white text-sm font-black rounded-xl hover:bg-blue-700 transition-all shadow-lg shadow-blue-500/30 flex items-center active:scale-95"
                    >
                        <Plus className="h-4 w-4 mr-2" /> Record Transaction
                    </button>
                </div>
            </div>

            {error && (
                <div className="bg-red-50 border-l-4 border-red-500 p-4 rounded-r-lg flex items-center text-red-700">
                    <AlertCircle className="h-5 w-5 mr-3" />
                    <p className="text-sm font-bold uppercase tracking-tight">{error}</p>
                </div>
            )}

            <div className="flex flex-col sm:flex-row justify-between items-center gap-4 bg-white p-4 rounded-2xl border border-slate-100 shadow-sm">
                <div className="relative w-full sm:w-96 group">
                    <Search className="absolute left-3 top-2.5 h-4 w-4 text-slate-400 group-focus-within:text-blue-500 transition-colors" />
                    <input 
                        type="text" 
                        placeholder="Search by ID, Category, or Member..."
                        value={searchTerm}
                        onChange={(e) => setSearchTerm(e.target.value)}
                        className="w-full pl-10 pr-4 py-2 bg-slate-50 border border-slate-200 rounded-xl text-sm focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 outline-none transition-all"
                    />
                </div>

                <div className="flex bg-slate-100 p-1 rounded-xl w-full sm:w-auto">
                    {['ALL', 'INCOME', 'EXPENSE'].map((type) => (
                        <button
                            key={type}
                            onClick={() => setFilterType(type)}
                            className={`flex-1 sm:flex-none px-4 py-1.5 text-xs font-black uppercase tracking-widest rounded-lg transition-all ${
                                filterType === type 
                                    ? 'bg-white text-slate-900 shadow-sm' 
                                    : 'text-slate-500 hover:text-slate-700'
                            }`}
                        >
                            {type}
                        </button>
                    ))}
                </div>
            </div>

            <div className="bg-white rounded-3xl shadow-sm border border-slate-100 overflow-hidden">
                <div className="overflow-x-auto">
                    <table className="min-w-full divide-y divide-slate-100">
                        <thead className="bg-slate-50/50">
                            <tr>
                                <th className="px-6 py-4 text-left text-[10px] font-black text-slate-400 uppercase tracking-widest">Transaction</th>
                                <th className="px-6 py-4 text-left text-[10px] font-black text-slate-400 uppercase tracking-widest">Category / Member</th>
                                <th className="px-6 py-4 text-left text-[10px] font-black text-slate-400 uppercase tracking-widest">Date & Time</th>
                                <th className="px-6 py-4 text-right text-[10px] font-black text-slate-400 uppercase tracking-widest">Amount</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-50 bg-white">
                            {filteredTransactions.length > 0 ? (
                                filteredTransactions.map((tx) => (
                                    <tr key={tx.id} className="hover:bg-slate-50 transition-colors group">
                                        <td className="px-6 py-4 whitespace-nowrap">
                                            <div className="flex items-center">
                                                <div className={`p-2 rounded-xl mr-3 shadow-sm ${
                                                    tx.type === 'INCOME' ? 'bg-emerald-100 text-emerald-600' : 'bg-red-100 text-red-600'
                                                }`}>
                                                    {tx.type === 'INCOME' ? <ArrowDownRight className="h-4 w-4" /> : <ArrowUpRight className="h-4 w-4" />}
                                                </div>
                                                <div>
                                                    <p className="text-sm font-bold text-slate-900 font-mono tracking-tight">{tx.reference_id}</p>
                                                    <p className="text-[10px] font-bold uppercase tracking-widest text-slate-400 mt-0.5">{tx.type}</p>
                                                </div>
                                            </div>
                                        </td>
                                        <td className="px-6 py-4">
                                            <p className="text-sm font-bold text-slate-800">{tx.category}</p>
                                            <p className="text-xs text-slate-500 mt-0.5 truncate max-w-xs">{tx.description}</p>
                                            <span className="inline-block mt-1 px-2 py-0.5 bg-slate-100 text-slate-600 text-[10px] font-bold rounded uppercase tracking-wider">
                                                {tx.member_name}
                                            </span>
                                        </td>
                                        <td className="px-6 py-4 whitespace-nowrap">
                                            <p className="text-sm font-bold text-slate-800">{tx.date ? format(new Date(tx.date), 'MMM dd, yyyy') : 'N/A'}</p>
                                            <p className="text-xs text-slate-400 mt-0.5">{tx.created_at ? format(new Date(tx.created_at), 'h:mm a') : ''}</p>
                                        </td>
                                        <td className="px-6 py-4 whitespace-nowrap text-right">
                                            <span className={`text-base font-black tracking-tight ${
                                                tx.type === 'INCOME' ? 'text-emerald-500' : 'text-slate-900'
                                            }`}>
                                                {tx.type === 'INCOME' ? '+' : '-'}{formatCurrency(tx.amount)}
                                            </span>
                                        </td>
                                    </tr>
                                ))
                            ) : (
                                <tr>
                                    <td colSpan="4" className="px-6 py-16 text-center text-slate-400">
                                        <Filter className="h-10 w-10 mb-4 opacity-20 mx-auto" />
                                        <p className="text-sm font-bold">No transactions found</p>
                                    </td>
                                </tr>
                            )}
                        </tbody>
                    </table>
                </div>
            </div>

            <RecordTransactionModal 
                isOpen={isModalOpen} 
                onClose={() => setIsModalOpen(false)} 
                onSuccess={() => {
                    setIsModalOpen(false);
                    fetchLedger(); 
                }}
            />
        </div>
    );
};

export default FinanceLedger;