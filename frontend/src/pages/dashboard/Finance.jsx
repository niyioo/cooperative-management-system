import React, { useState, useEffect } from 'react';
import axiosInstance from '../../api/axios';
import { useAuth } from '../../hooks/useAuth';
import { 
    Search, Plus, TrendingUp, TrendingDown, DollarSign, 
    AlertCircle, Loader2, FileText, Download, Filter, CheckCircle 
} from 'lucide-react';
import { format } from 'date-fns';
import RecordEntryModal from '../../components/RecordEntryModal';
import ReceiptModal from '../../components/ReceiptModal'; // Import the new Receipt component

const Finance = () => {
    const { isManager } = useAuth();
    const [transactions, setTransactions] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');
    const [searchTerm, setSearchTerm] = useState('');

    // Modal & Toast State
    const [isModalOpen, setIsModalOpen] = useState(false);
    const [successMessage, setSuccessMessage] = useState('');

    // Receipt State
    const [selectedTx, setSelectedTx] = useState(null);
    const [isReceiptOpen, setIsReceiptOpen] = useState(false);

    const fetchLedger = async () => {
        try {
            setLoading(true);
            setError('');
            const response = await axiosInstance.get('/finance/ledger/');
            const data = response.data.results || response.data;
            setTransactions(Array.isArray(data) ? data : []);
        } catch (err) {
            console.error("Failed to fetch ledger:", err);
            setError('Failed to load financial records. Please try again later.');
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchLedger();
    }, []);

    // Quick Stats Calculations
    const totalIncome = transactions
        .filter(t => t.type === 'INCOME')
        .reduce((sum, t) => sum + parseFloat(t.amount || 0), 0);
        
    const totalExpense = transactions
        .filter(t => t.type === 'EXPENSE')
        .reduce((sum, t) => sum + parseFloat(t.amount || 0), 0);
        
    const netBalance = totalIncome - totalExpense;

    // Enhanced filter logic
    const filteredTransactions = transactions.filter(t => {
        const desc = t.description?.toLowerCase() || '';
        const refId = t.reference_id?.toLowerCase() || '';
        const category = t.category?.toLowerCase() || '';
        const search = searchTerm.toLowerCase();
        return desc.includes(search) || refId.includes(search) || category.includes(search);
    });

    const formatCurrency = (amount) => {
        return new Intl.NumberFormat('en-NG', { 
            style: 'currency', 
            currency: 'NGN',
            minimumFractionDigits: 2 
        }).format(amount);
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
                    <h1 className="text-2xl font-bold text-slate-900">Cooperative Finance Ledger</h1>
                    <p className="text-sm text-slate-500 mt-1">Real-time tracking of all income and expenditure.</p>
                </div>
                
                {isManager && (
                    <div className="flex space-x-3">
                        <button className="inline-flex items-center justify-center px-4 py-2 bg-white border border-slate-300 text-slate-700 text-sm font-bold rounded-lg hover:bg-slate-50 transition-all shadow-sm">
                            <Download className="h-4 w-4 mr-2" />
                            Export CSV
                        </button>
                        <button 
                            onClick={() => setIsModalOpen(true)}
                            className="inline-flex items-center justify-center px-4 py-2 bg-slate-900 text-white text-sm font-bold rounded-lg hover:bg-slate-800 transition-all shadow-md"
                        >
                            <Plus className="h-4 w-4 mr-2" />
                            Record Entry
                        </button>
                    </div>
                )}
            </div>

            {/* Error Message */}
            {error && (
                <div className="bg-red-50 border-l-4 border-red-500 p-4 rounded flex items-center">
                    <AlertCircle className="h-5 w-5 text-red-500 mr-2" />
                    <p className="text-sm text-red-700 font-medium">{error}</p>
                </div>
            )}

            {/* Stats Cards */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                <div className="bg-white p-6 rounded-2xl shadow-sm border border-slate-100">
                    <div className="flex items-center space-x-4">
                        <div className="bg-emerald-100 p-3 rounded-xl text-emerald-600">
                            <TrendingUp className="h-6 w-6" />
                        </div>
                        <div>
                            <p className="text-xs font-bold text-slate-400 uppercase tracking-wider">Gross Income</p>
                            <h3 className="text-2xl font-black text-emerald-600">{formatCurrency(totalIncome)}</h3>
                        </div>
                    </div>
                </div>
                
                <div className="bg-white p-6 rounded-2xl shadow-sm border border-slate-100">
                    <div className="flex items-center space-x-4">
                        <div className="bg-red-100 p-3 rounded-xl text-red-600">
                            <TrendingDown className="h-6 w-6" />
                        </div>
                        <div>
                            <p className="text-xs font-bold text-slate-400 uppercase tracking-wider">Total Expenses</p>
                            <h3 className="text-2xl font-black text-red-600">{formatCurrency(totalExpense)}</h3>
                        </div>
                    </div>
                </div>

                <div className={`bg-white p-6 rounded-2xl shadow-sm border-2 flex items-center space-x-4 ${netBalance >= 0 ? 'border-emerald-100' : 'border-red-100'}`}>
                    <div className={`p-3 rounded-xl ${netBalance >= 0 ? 'bg-emerald-50 text-emerald-600' : 'bg-red-50 text-red-600'}`}>
                        <DollarSign className="h-6 w-6" />
                    </div>
                    <div>
                        <p className="text-xs font-bold text-slate-400 uppercase tracking-wider">Net Surplus/Deficit</p>
                        <h3 className={`text-2xl font-black ${netBalance >= 0 ? 'text-slate-900' : 'text-red-600'}`}>
                            {formatCurrency(netBalance)}
                        </h3>
                    </div>
                </div>
            </div>

            {/* Main Content Card */}
            <div className="bg-white rounded-2xl shadow-sm border border-slate-200 overflow-hidden">
                {/* Table Header / Search */}
                <div className="p-4 border-b border-slate-200 bg-slate-50/50 flex items-center justify-between">
                    <div className="relative w-full max-w-md">
                        <Search className="absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
                        <input
                            type="text"
                            placeholder="Search by description, reference, or category..."
                            value={searchTerm}
                            onChange={(e) => setSearchTerm(e.target.value)}
                            className="block w-full pl-10 pr-3 py-2 border border-slate-300 rounded-xl bg-white text-sm outline-none focus:ring-2 focus:ring-blue-500 transition-all"
                        />
                    </div>
                    <div className="flex items-center space-x-2">
                        <span className="text-xs font-bold text-slate-400 uppercase hidden sm:inline">Filter By Type</span>
                        <button className="p-2 bg-white border border-slate-200 rounded-lg text-slate-400 hover:text-slate-600 shadow-sm">
                            <Filter className="h-4 w-4" />
                        </button>
                    </div>
                </div>

                {/* Ledger Table */}
                <div className="overflow-x-auto">
                    <table className="min-w-full divide-y divide-slate-200">
                        <thead className="bg-slate-50">
                            <tr>
                                <th className="px-6 py-4 text-left text-[10px] font-bold text-slate-500 uppercase tracking-widest">Date</th>
                                <th className="px-6 py-4 text-left text-[10px] font-bold text-slate-500 uppercase tracking-widest">Transaction Details</th>
                                <th className="px-6 py-4 text-left text-[10px] font-bold text-slate-500 uppercase tracking-widest">Category</th>
                                <th className="px-6 py-4 text-right text-[10px] font-bold text-slate-500 uppercase tracking-widest">Amount</th>
                                <th className="relative px-6 py-4"><span className="sr-only">Actions</span></th>
                            </tr>
                        </thead>
                        <tbody className="bg-white divide-y divide-slate-200">
                            {filteredTransactions.length > 0 ? (
                                filteredTransactions.map((tx) => (
                                    <tr key={tx.id} className="hover:bg-slate-50 transition-colors group">
                                        <td className="px-6 py-4 whitespace-nowrap text-sm text-slate-500 font-medium">
                                            {tx.date ? format(new Date(tx.date), 'MMM dd, yyyy') : 'N/A'}
                                        </td>
                                        <td className="px-6 py-4">
                                            <div className="text-sm font-bold text-slate-900">{tx.description}</div>
                                            <div className="text-[10px] text-slate-400 font-mono mt-0.5 tracking-tight">REF: {tx.reference_id}</div>
                                        </td>
                                        <td className="px-6 py-4 whitespace-nowrap">
                                            <span className="inline-flex items-center px-2 py-1 rounded-md text-[10px] font-bold bg-slate-100 text-slate-600 border border-slate-200 uppercase tracking-wider">
                                                {tx.category || 'General'}
                                            </span>
                                        </td>
                                        <td className="px-6 py-4 whitespace-nowrap text-right">
                                            <span className={`text-sm font-black ${tx.type === 'INCOME' ? 'text-emerald-600' : 'text-red-600'}`}>
                                                {tx.type === 'INCOME' ? '+' : '-'}{formatCurrency(tx.amount)}
                                            </span>
                                        </td>
                                        <td className="px-6 py-4 whitespace-nowrap text-right">
                                            <div className="flex items-center justify-end space-x-2 opacity-0 group-hover:opacity-100 transition-opacity">
                                                {/* TRIGGER RECEIPT MODAL HERE */}
                                                <button 
                                                    onClick={() => { setSelectedTx(tx); setIsReceiptOpen(true); }}
                                                    title="View Receipt" 
                                                    className="p-1.5 text-slate-400 hover:text-blue-600 hover:bg-blue-50 rounded-lg transition-all"
                                                >
                                                    <FileText className="h-4 w-4" />
                                                </button>
                                            </div>
                                        </td>
                                    </tr>
                                ))
                            ) : (
                                <tr>
                                    <td colSpan="5" className="px-6 py-12 text-center text-slate-500">
                                        <div className="flex flex-col items-center justify-center">
                                            <div className="bg-slate-100 p-3 rounded-full mb-3">
                                                <DollarSign className="h-8 w-8 text-slate-300" />
                                            </div>
                                            <p className="text-base font-medium text-slate-900">No ledger entries found</p>
                                            <p className="text-sm mt-1">Manual entries and system transactions will appear here.</p>
                                        </div>
                                    </td>
                                </tr>
                            )}
                        </tbody>
                    </table>
                </div>
            </div>

            {/* Success Toast Notification */}
            {successMessage && (
                <div className="fixed bottom-6 right-6 bg-slate-900 text-white px-6 py-3 rounded-xl shadow-2xl animate-in slide-in-from-bottom-5 z-50 flex items-center font-bold text-sm">
                    <CheckCircle className="h-4 w-4 text-emerald-400 mr-2" />
                    {successMessage}
                </div>
            )}

            {/* Record Entry Modal */}
            <RecordEntryModal 
                isOpen={isModalOpen}
                onClose={() => setIsModalOpen(false)}
                onSuccess={(msg) => {
                    setIsModalOpen(false);
                    setSuccessMessage(msg);
                    fetchLedger(); 
                    setTimeout(() => setSuccessMessage(''), 4000);
                }}
            />

            {/* Receipt Generator Modal */}
            <ReceiptModal 
                isOpen={isReceiptOpen} 
                onClose={() => setIsReceiptOpen(false)} 
                transaction={selectedTx} 
            />
        </div>
    );
};

export default Finance;