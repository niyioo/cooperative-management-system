import React, { useState } from 'react';
import axiosInstance from '../api/axios';
import { 
    X, CreditCard, Hash, Calendar, Loader2, CheckCircle, AlertCircle 
} from 'lucide-react';

const RecordRepaymentModal = ({ isOpen, onClose, loan, onSuccess }) => {
    const [amount, setAmount] = useState('');
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [error, setError] = useState('');

    if (!isOpen || !loan) return null;

    const handleSubmit = async (e) => {
        e.preventDefault();
        setError('');
        setIsSubmitting(true);

        try {
            const payload = {
                loan: loan.id,
                amount_paid: parseFloat(amount),
            };

            // 1. Record the repayment
            await axiosInstance.post('/loans/repayments/', payload);

            // 2. Add an entry to the Finance Ledger so the Treasury Snapshot updates
            await axiosInstance.post('/finance/ledger/', {
                type: 'INCOME',
                category: 'Loan Repayment',
                amount: parseFloat(amount),
                member: loan.member.id,
                description: `Repayment for Loan ${loan.loan_id}`,
                date: new Date().toISOString().split('T')[0]
            });

            if (onSuccess) onSuccess('Repayment recorded successfully!');
            setAmount('');
            onClose();
        } catch (err) {
            console.error("Repayment failed:", err.response?.data);
            setError(err.response?.data?.detail || "Failed to record payment. Please check the amount.");
        } finally {
            setIsSubmitting(false);
        }
    };

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-sm animate-in fade-in duration-200">
            <div className="bg-white rounded-3xl shadow-2xl w-full max-w-md overflow-hidden animate-in zoom-in-95 duration-200">
                
                {/* Header */}
                <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between bg-slate-50/50">
                    <div className="flex items-center space-x-3">
                        <div className="bg-emerald-600 p-2 rounded-xl text-white shadow-sm">
                            <CreditCard className="h-5 w-5" />
                        </div>
                        <div>
                            <h2 className="text-lg font-black text-slate-900 tracking-tight">Record Repayment</h2>
                            <p className="text-[10px] font-bold text-slate-400 uppercase tracking-widest">{loan.loan_id}</p>
                        </div>
                    </div>
                    <button onClick={onClose} className="p-2 hover:bg-slate-200 rounded-full transition-colors">
                        <X className="h-5 w-5 text-slate-500" />
                    </button>
                </div>

                <form onSubmit={handleSubmit} className="p-6 space-y-4">
                    {error && (
                        <div className="bg-red-50 border-l-4 border-red-500 p-3 rounded-r-lg flex items-start">
                            <AlertCircle className="h-5 w-5 text-red-500 mr-2 shrink-0" />
                            <p className="text-xs text-red-700 font-bold uppercase tracking-tight">{error}</p>
                        </div>
                    )}

                    <div className="p-4 bg-blue-50 rounded-2xl border border-blue-100">
                        <p className="text-[10px] font-black text-blue-400 uppercase tracking-widest mb-1">Current Balance</p>
                        <p className="text-xl font-black text-blue-700">
                            {new Intl.NumberFormat('en-NG', { style: 'currency', currency: 'NGN' }).format(loan.balance)}
                        </p>
                    </div>

                    <div className="space-y-1.5">
                        <label className="text-[10px] font-black text-slate-400 uppercase tracking-widest ml-1">Amount to Pay (₦)</label>
                        <div className="relative">
                            <Hash className="absolute left-3 top-3 h-4 w-4 text-slate-400" />
                            <input 
                                required 
                                type="number" 
                                value={amount} 
                                onChange={(e) => setAmount(e.target.value)}
                                placeholder="0.00"
                                className="w-full pl-10 pr-4 py-3 border border-slate-200 rounded-xl text-sm font-bold focus:ring-2 focus:ring-emerald-500 outline-none transition-all"
                            />
                        </div>
                    </div>

                    <div className="pt-4 flex justify-end space-x-3 border-t border-slate-100">
                        <button type="button" onClick={onClose} className="px-5 py-2.5 text-xs font-bold text-slate-500 hover:text-slate-800 uppercase tracking-widest">
                            Cancel
                        </button>
                        <button 
                            type="submit" 
                            disabled={isSubmitting || !amount}
                            className="px-8 py-2.5 bg-emerald-600 text-white text-xs font-black uppercase tracking-widest rounded-xl hover:bg-emerald-700 transition-all shadow-lg shadow-emerald-500/20 active:scale-95 disabled:opacity-50 flex items-center"
                        >
                            {isSubmitting ? <Loader2 className="animate-spin h-4 w-4 mr-2" /> : <CheckCircle className="h-4 w-4 mr-2" />}
                            Confirm Payment
                        </button>
                    </div>
                </form>
            </div>
        </div>
    );
};

export default RecordRepaymentModal;