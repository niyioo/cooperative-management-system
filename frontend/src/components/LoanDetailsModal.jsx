import React from 'react';
import { 
    X, Landmark, Calendar, User, ShieldCheck, Hash, 
    TrendingDown, ArrowUpRight, CheckCircle, Clock 
} from 'lucide-react';
import { format } from 'date-fns';

const LoanDetailsModal = ({ isOpen, onClose, loan }) => {
    if (!isOpen || !loan) return null;

    const formatCurrency = (amount) => {
        return new Intl.NumberFormat('en-NG', { style: 'currency', currency: 'NGN' }).format(amount || 0);
    };

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-sm animate-in fade-in duration-200">
            <div className="bg-white rounded-3xl shadow-2xl w-full max-w-3xl max-h-[90vh] overflow-hidden flex flex-col animate-in zoom-in-95 duration-200">
                
                {/* Header */}
                <div className="px-8 py-6 border-b border-slate-100 flex items-center justify-between bg-slate-50/50">
                    <div>
                        <div className="flex items-center space-x-2">
                            <span className="px-2 py-0.5 bg-blue-100 text-blue-700 text-[10px] font-black uppercase rounded tracking-widest">
                                {loan.loan_id}
                            </span>
                            <h2 className="text-xl font-black text-slate-900 tracking-tight">Loan Statement</h2>
                        </div>
                        <p className="text-xs text-slate-500 mt-1 font-medium">Detailed breakdown for {loan.member?.first_name} {loan.member?.last_name}</p>
                    </div>
                    <button onClick={onClose} className="p-2 hover:bg-slate-200 rounded-full transition-colors text-slate-400">
                        <X className="h-5 w-5" />
                    </button>
                </div>

                <div className="flex-1 overflow-y-auto p-8 space-y-8">
                    {/* Financial Summary Grid */}
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                        <div className="bg-slate-50 p-4 rounded-2xl border border-slate-100">
                            <p className="text-[10px] font-black text-slate-400 uppercase tracking-widest mb-1">Principal</p>
                            <p className="text-lg font-bold text-slate-900">{formatCurrency(loan.principal_amount)}</p>
                        </div>
                        <div className="bg-slate-50 p-4 rounded-2xl border border-slate-100">
                            <p className="text-[10px] font-black text-slate-400 uppercase tracking-widest mb-1">Interest</p>
                            <p className="text-lg font-bold text-emerald-600">+{formatCurrency(loan.interest_amount)}</p>
                        </div>
                        <div className="bg-blue-50 p-4 rounded-2xl border border-blue-100">
                            <p className="text-[10px] font-black text-blue-400 uppercase tracking-widest mb-1">Total Due</p>
                            <p className="text-lg font-bold text-blue-700">{formatCurrency(loan.total_payable)}</p>
                        </div>
                        <div className="bg-slate-900 p-4 rounded-2xl shadow-lg shadow-slate-200">
                            <p className="text-[10px] font-black text-slate-400 uppercase tracking-widest mb-1">Remaining</p>
                            <p className="text-lg font-bold text-white">{formatCurrency(loan.balance)}</p>
                        </div>
                    </div>

                    {/* Loan Progress / Details */}
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
                        <div className="space-y-4">
                            <h3 className="text-[10px] font-black text-slate-400 uppercase tracking-widest flex items-center">
                                <Clock className="h-3 w-3 mr-2" /> Timeline & Details
                            </h3>
                            <div className="space-y-3">
                                <div className="flex justify-between text-sm">
                                    <span className="text-slate-500 font-medium">Application Date</span>
                                    <span className="font-bold text-slate-800">{format(new Date(loan.application_date), 'MMM dd, yyyy')}</span>
                                </div>
                                <div className="flex justify-between text-sm">
                                    <span className="text-slate-500 font-medium">Tenure</span>
                                    <span className="font-bold text-slate-800">{loan.duration_months} Months</span>
                                </div>
                                <div className="flex justify-between text-sm">
                                    <span className="text-slate-500 font-medium">Purpose</span>
                                    <span className="font-bold text-slate-800 text-right max-w-[200px] truncate">{loan.purpose || 'General Support'}</span>
                                </div>
                            </div>
                        </div>

                        {/* Guarantors */}
                        <div className="space-y-4">
                            <h3 className="text-[10px] font-black text-slate-400 uppercase tracking-widest flex items-center">
                                <ShieldCheck className="h-3 w-3 mr-2" /> Guarantors
                            </h3>
                            <div className="space-y-2">
                                {loan.guarantors?.length > 0 ? loan.guarantors.map(g => (
                                    <div key={g.id} className="flex items-center justify-between p-3 bg-slate-50 rounded-xl border border-slate-100">
                                        <div className="flex items-center">
                                            <div className="h-7 w-7 bg-white rounded-full flex items-center justify-center border border-slate-200 mr-3">
                                                <User className="h-3.5 w-3.5 text-slate-400" />
                                            </div>
                                            <span className="text-xs font-bold text-slate-700">{g.guarantor_name}</span>
                                        </div>
                                        <span className="text-xs font-black text-blue-600">{formatCurrency(g.amount_guaranteed)}</span>
                                    </div>
                                )) : (
                                    <p className="text-xs text-slate-400 italic">No guarantors attached to this loan.</p>
                                )}
                            </div>
                        </div>
                    </div>

                    {/* Repayments History */}
                    <div className="space-y-4">
                        <h3 className="text-[10px] font-black text-slate-400 uppercase tracking-widest flex items-center">
                            <ArrowUpRight className="h-3 w-3 mr-2" /> Repayment History
                        </h3>
                        <div className="border border-slate-100 rounded-2xl overflow-hidden shadow-sm">
                            <table className="min-w-full divide-y divide-slate-100">
                                <thead className="bg-slate-50">
                                    <tr>
                                        <th className="px-4 py-3 text-left text-[10px] font-black text-slate-400 uppercase tracking-widest">Date</th>
                                        <th className="px-4 py-3 text-left text-[10px] font-black text-slate-400 uppercase tracking-widest">Reference</th>
                                        <th className="px-4 py-3 text-right text-[10px] font-black text-slate-400 uppercase tracking-widest">Amount Paid</th>
                                    </tr>
                                </thead>
                                <tbody className="bg-white divide-y divide-slate-50">
                                    {loan.repayments?.length > 0 ? loan.repayments.map(rep => (
                                        <tr key={rep.id}>
                                            <td className="px-4 py-3 text-xs font-bold text-slate-600">{format(new Date(rep.payment_date), 'MMM dd, yyyy')}</td>
                                            <td className="px-4 py-3 text-[10px] font-mono font-bold text-slate-400 uppercase">{rep.receipt_reference}</td>
                                            <td className="px-4 py-3 text-sm font-black text-slate-900 text-right">{formatCurrency(rep.amount_paid)}</td>
                                        </tr>
                                    )) : (
                                        <tr>
                                            <td colSpan="3" className="px-4 py-8 text-center text-xs text-slate-400 font-medium">No repayments recorded yet.</td>
                                        </tr>
                                    )}
                                </tbody>
                            </table>
                        </div>
                    </div>
                </div>

                {/* Footer Action */}
                <div className="px-8 py-6 bg-slate-50 border-t border-slate-100 flex justify-end">
                    <button 
                        onClick={onClose}
                        className="px-6 py-2.5 bg-slate-900 text-white text-xs font-black uppercase tracking-widest rounded-xl hover:bg-slate-800 transition-all shadow-lg active:scale-95"
                    >
                        Close Statement
                    </button>
                </div>
            </div>
        </div>
    );
};

export default LoanDetailsModal;