import React, { useState, useEffect } from 'react';
import { 
    X, DollarSign, AlertCircle, Loader2, FileText, Tag, 
    Calendar, TrendingUp, TrendingDown, Hash, CheckCircle 
} from 'lucide-react';
import axiosInstance from '../api/axios';

const RecordEntryModal = ({ isOpen, onClose, onSuccess }) => {
    const [formData, setFormData] = useState({
        type: 'INCOME',
        category: '',
        amount: '',
        date: '',
        description: '',
        reference_id: ''
    });
    
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [error, setError] = useState('');

    const incomeCategories = [
        'Share Purchase', 'Loan Repayment', 'Monthly Dues', 
        'Levy/Fine', 'Interest/Investment', 'Other'
    ];
    
    const expenseCategories = [
        'Loan Disbursement', 'Dividend Payout', 'Office Supplies', 
        'Salary/Wages', 'Maintenance', 'Bank Charges', 'Other'
    ];

    useEffect(() => {
        if (isOpen) {
            setFormData(prev => ({
                ...prev,
                date: new Date().toISOString().split('T')[0]
            }));
        } else {
            setFormData({
                type: 'INCOME',
                category: '',
                amount: '',
                date: '',
                description: '',
                reference_id: ''
            });
            setError('');
        }
    }, [isOpen]);

    if (!isOpen) return null;

    const handleChange = (e) => {
        const { name, value } = e.target;
        setFormData(prev => ({ ...prev, [name]: value }));
    };

    const handleSubmit = async (e) => {
        e.preventDefault();
        setError('');
        setIsSubmitting(true);

        try {
            const payload = {
                ...formData,
                amount: parseFloat(formData.amount),
                // Auto-generate reference if user left it blank
                reference_id: formData.reference_id || `MANUAL-${Math.floor(1000 + Math.random() * 9000)}`
            };

            await axiosInstance.post('/finance/ledger/', payload);
            onSuccess(`${formData.type === 'INCOME' ? 'Income' : 'Expense'} recorded successfully!`);
        } catch (err) {
            setError(err.response?.data?.detail || 'Failed to record entry. Please check your inputs.');
        } finally {
            setIsSubmitting(false);
        }
    };

    const isIncome = formData.type === 'INCOME';
    const ThemeIcon = isIncome ? TrendingUp : TrendingDown;
    const themeColor = isIncome ? 'text-emerald-600' : 'text-red-600';
    const themeBg = isIncome ? 'bg-emerald-50' : 'bg-red-50';
    const themeBorder = isIncome ? 'border-emerald-100' : 'border-red-100';
    const buttonClass = isIncome 
        ? 'bg-emerald-600 hover:bg-emerald-700' 
        : 'bg-red-600 hover:bg-red-700';

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-sm">
            <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md overflow-hidden animate-in zoom-in duration-200">
                
                {/* Header */}
                <div className={`px-6 py-4 border-b flex items-center justify-between ${themeBg}/50`}>
                    <div className="flex items-center space-x-3">
                        <div className={`p-2 rounded-xl ${themeBg} ${themeColor} border ${themeBorder}`}>
                            <ThemeIcon className="h-5 w-5" />
                        </div>
                        <h2 className="text-lg font-black text-slate-800 tracking-tight">Record Ledger Entry</h2>
                    </div>
                    <button onClick={onClose} className="p-2 hover:bg-slate-200 rounded-full transition-colors">
                        <X className="h-5 w-5 text-slate-400" />
                    </button>
                </div>

                <form onSubmit={handleSubmit} className="p-6 space-y-5">
                    {error && (
                        <div className="p-3 bg-red-50 border-l-4 border-red-500 text-red-700 text-xs rounded-r-lg flex items-center">
                            <AlertCircle className="h-4 w-4 mr-2 shrink-0" /> {error}
                        </div>
                    )}

                    {/* Type Toggle */}
                    <div className="flex p-1 bg-slate-100 rounded-xl">
                        <button
                            type="button"
                            onClick={() => setFormData({...formData, type: 'INCOME', category: ''})}
                            className={`flex-1 py-2 text-xs font-bold rounded-lg transition-all ${
                                isIncome ? 'bg-white text-emerald-600 shadow-sm' : 'text-slate-500 hover:text-slate-700'
                            }`}
                        >
                            INCOME
                        </button>
                        <button
                            type="button"
                            onClick={() => setFormData({...formData, type: 'EXPENSE', category: ''})}
                            className={`flex-1 py-2 text-xs font-bold rounded-lg transition-all ${
                                !isIncome ? 'bg-white text-red-600 shadow-sm' : 'text-slate-500 hover:text-slate-700'
                            }`}
                        >
                            EXPENSE
                        </button>
                    </div>

                    {/* Amount & Date */}
                    <div className="grid grid-cols-2 gap-4">
                        <div className="space-y-1">
                            <label className="text-[10px] font-bold text-slate-500 uppercase tracking-widest ml-1">Amount (₦)</label>
                            <div className="relative">
                                <DollarSign className="absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
                                <input
                                    required name="amount" type="number" step="0.01" value={formData.amount} onChange={handleChange}
                                    placeholder="0.00"
                                    className="pl-10 w-full px-3 py-2 border border-slate-200 rounded-xl text-sm focus:ring-2 focus:ring-blue-500 outline-none"
                                />
                            </div>
                        </div>
                        <div className="space-y-1">
                            <label className="text-[10px] font-bold text-slate-500 uppercase tracking-widest ml-1">Date</label>
                            <div className="relative">
                                <Calendar className="absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
                                <input
                                    required name="date" type="date" value={formData.date} onChange={handleChange}
                                    className="pl-10 w-full px-3 py-2 border border-slate-200 rounded-xl text-sm focus:ring-2 focus:ring-blue-500 outline-none"
                                />
                            </div>
                        </div>
                    </div>

                    {/* Category */}
                    <div className="space-y-1">
                        <label className="text-[10px] font-bold text-slate-500 uppercase tracking-widest ml-1">Category</label>
                        <div className="relative">
                            <Tag className="absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
                            <select
                                required name="category" value={formData.category} onChange={handleChange}
                                className="pl-10 w-full px-3 py-2 border border-slate-200 rounded-xl text-sm focus:ring-2 focus:ring-blue-500 outline-none appearance-none bg-white"
                            >
                                <option value="" disabled>-- Select Category --</option>
                                {(isIncome ? incomeCategories : expenseCategories).map(cat => (
                                    <option key={cat} value={cat}>{cat}</option>
                                ))}
                            </select>
                        </div>
                    </div>

                    {/* Reference ID (New field!) */}
                    <div className="space-y-1">
                        <label className="text-[10px] font-bold text-slate-500 uppercase tracking-widest ml-1">Reference / Receipt #</label>
                        <div className="relative">
                            <Hash className="absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
                            <input
                                name="reference_id" type="text" value={formData.reference_id} onChange={handleChange}
                                placeholder="Auto-generated if blank"
                                className="pl-10 w-full px-3 py-2 border border-slate-200 rounded-xl text-sm focus:ring-2 focus:ring-blue-500 outline-none font-mono"
                            />
                        </div>
                    </div>

                    {/* Description */}
                    <div className="space-y-1">
                        <label className="text-[10px] font-bold text-slate-500 uppercase tracking-widest ml-1">Description</label>
                        <div className="relative">
                            <FileText className="absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
                            <textarea
                                required name="description" rows="2" value={formData.description} onChange={handleChange}
                                placeholder="What is this for?"
                                className="pl-10 w-full px-3 py-2 border border-slate-200 rounded-xl text-sm focus:ring-2 focus:ring-blue-500 outline-none"
                            />
                        </div>
                    </div>

                    {/* Footer Actions */}
                    <div className="pt-4 flex items-center justify-end space-x-3">
                        <button type="button" onClick={onClose} className="px-4 py-2 text-sm font-bold text-slate-400 hover:text-slate-600 transition-colors">
                            Cancel
                        </button>
                        <button
                            type="submit"
                            disabled={isSubmitting}
                            className={`px-8 py-2.5 text-white text-sm font-black rounded-xl transition-all flex items-center shadow-lg active:scale-95 disabled:opacity-50 ${buttonClass}`}
                        >
                            {isSubmitting ? (
                                <><Loader2 className="animate-spin h-4 w-4 mr-2" /> Saving...</>
                            ) : (
                                <><CheckCircle className="h-4 w-4 mr-2" /> Save {isIncome ? 'Income' : 'Expense'}</>
                            )}
                        </button>
                    </div>
                </form>
            </div>
        </div>
    );
};

export default RecordEntryModal;