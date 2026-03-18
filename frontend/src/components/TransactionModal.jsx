import React, { useState, useEffect } from 'react';
import { X, ArrowDownCircle, ArrowUpCircle, AlertCircle, Loader2, DollarSign, FileText, User } from 'lucide-react';
import axiosInstance from '../api/axios';

const TransactionModal = ({ isOpen, onClose, onSuccess, type }) => {
    const [accounts, setAccounts] = useState([]); 
    const [accountId, setAccountId] = useState('');
    const [amount, setAmount] = useState('');
    const [reference, setReference] = useState('');
    const [error, setError] = useState('');
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [isLoadingAccounts, setIsLoadingAccounts] = useState(false);

    // Fetch accounts whenever the modal opens to populate the dropdown
    useEffect(() => {
        if (isOpen) {
            const fetchAccounts = async () => {
                setIsLoadingAccounts(true);
                try {
                    // hits the savings app endpoint
                    const response = await axiosInstance.get('/savings/accounts/');
                    const data = response.data.results || response.data;
                    setAccounts(Array.isArray(data) ? data : []);
                } catch (err) {
                    console.error("Failed to fetch accounts:", err);
                    setError("Could not load member accounts for selection.");
                } finally {
                    setIsLoadingAccounts(false);
                }
            };
            fetchAccounts();
        } else {
            // Reset fields on close so they are fresh for the next use
            setAccountId('');
            setAmount('');
            setReference('');
            setError('');
        }
    }, [isOpen]);

    if (!isOpen) return null;

    const isDeposit = type === 'DEPOSIT';
    const ThemeIcon = isDeposit ? ArrowDownCircle : ArrowUpCircle;
    const themeColor = isDeposit ? 'text-emerald-600' : 'text-amber-600';
    const themeBg = isDeposit ? 'bg-emerald-100' : 'bg-amber-100';
    const themeButton = isDeposit ? 'bg-emerald-600 hover:bg-emerald-700' : 'bg-amber-600 hover:bg-amber-700';

    const handleSubmit = async (e) => {
        e.preventDefault();
        setError('');
        setIsSubmitting(true);

        try {
            await axiosInstance.post('/savings/transactions/', {
                account: accountId,
                transaction_type: type,
                amount: parseFloat(amount),
                reference: reference || `${type} via Manager Dashboard`
            });
            
            onSuccess(isDeposit ? 'Deposit recorded successfully!' : 'Withdrawal processed successfully!');
            onClose();
        } catch (err) {
            console.error("Transaction Error:", err.response?.data);
            setError(err.response?.data?.detail || err.response?.data?.message || `Failed to process ${type.toLowerCase()}.`);
        } finally {
            setIsSubmitting(false);
        }
    };

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/50 backdrop-blur-sm transition-opacity">
            <div className="bg-white rounded-xl shadow-xl w-full max-w-md overflow-hidden animate-in fade-in zoom-in-95 duration-200">
                
                {/* Modal Header */}
                <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between bg-slate-50/50">
                    <div className="flex items-center space-x-2">
                        <div className={`${themeBg} p-2 rounded-lg ${themeColor}`}>
                            <ThemeIcon className="h-5 w-5" />
                        </div>
                        <h2 className="text-lg font-semibold text-slate-800">
                            {isDeposit ? 'Record Deposit' : 'Process Withdrawal'}
                        </h2>
                    </div>
                    <button onClick={onClose} className="text-slate-400 hover:text-slate-600 p-1 rounded-md transition-colors">
                        <X className="h-5 w-5" />
                    </button>
                </div>

                {/* Modal Body */}
                <form onSubmit={handleSubmit} className="p-6">
                    {error && (
                        <div className="mb-4 bg-red-50 border-l-4 border-red-500 p-3 rounded-r-md flex items-start">
                            <AlertCircle className="h-5 w-5 text-red-500 mr-2 flex-shrink-0 mt-0.5" />
                            <p className="text-sm text-red-700 font-medium">{error}</p>
                        </div>
                    )}

                    <div className="space-y-4">
                        {/* Account Selection Dropdown */}
                        <div>
                            <label className="block text-sm font-bold text-slate-700 mb-1">Select Member Account</label>
                            <div className="relative">
                                <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                                    <User className="h-4 w-4 text-slate-400" />
                                </div>
                                <select
                                    required
                                    value={accountId}
                                    onChange={(e) => setAccountId(e.target.value)}
                                    disabled={isLoadingAccounts}
                                    className="block w-full py-2 pl-10 pr-10 border border-slate-300 bg-white rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 sm:text-sm disabled:bg-slate-50 disabled:text-slate-400"
                                >
                                    <option value="" disabled>
                                        {isLoadingAccounts ? 'Fetching accounts...' : '-- Choose an account --'}
                                    </option>
                                    {accounts.map(acc => (
                                        <option key={acc.id} value={acc.id}>
                                            {acc.member?.first_name} {acc.member?.last_name} ({acc.account_number || 'No Account #'})
                                        </option>
                                    ))}
                                </select>
                            </div>
                        </div>

                        {/* Amount Input */}
                        <div>
                            <label className="block text-sm font-bold text-slate-700 mb-1">Amount (₦)</label>
                            <div className="relative">
                                <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                                    <DollarSign className="h-4 w-4 text-slate-400" />
                                </div>
                                <input
                                    type="number"
                                    required
                                    min="1"
                                    step="0.01"
                                    value={amount}
                                    onChange={(e) => setAmount(e.target.value)}
                                    className="block w-full pl-10 pr-3 py-2 border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 sm:text-sm"
                                    placeholder="0.00"
                                />
                            </div>
                        </div>

                        {/* Reference / Notes Input */}
                        <div>
                            <label className="block text-sm font-bold text-slate-700 mb-1">Reference / Notes (Optional)</label>
                            <div className="relative">
                                <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                                    <FileText className="h-4 w-4 text-slate-400" />
                                </div>
                                <input
                                    type="text"
                                    value={reference}
                                    onChange={(e) => setReference(e.target.value)}
                                    className="block w-full pl-10 pr-3 py-2 border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 sm:text-sm"
                                    placeholder="e.g. Monthly contribution"
                                />
                            </div>
                        </div>
                    </div>

                    {/* Modal Footer */}
                    <div className="mt-8 flex items-center justify-end space-x-3">
                        <button
                            type="button"
                            onClick={onClose}
                            className="px-4 py-2 text-sm font-bold text-slate-400 bg-white border border-slate-200 rounded-lg hover:bg-slate-50 transition-colors"
                        >
                            Cancel
                        </button>
                        <button
                            type="submit"
                            disabled={isSubmitting || isLoadingAccounts}
                            className={`inline-flex items-center px-4 py-2 text-sm font-bold text-white border border-transparent rounded-lg focus:outline-none focus:ring-2 focus:ring-offset-2 disabled:opacity-70 transition-colors shadow-lg active:scale-95 ${themeButton}`}
                        >
                            {isSubmitting ? (
                                <><Loader2 className="animate-spin h-4 w-4 mr-2" /> Processing...</>
                            ) : (
                                isDeposit ? 'Confirm Deposit' : 'Confirm Withdrawal'
                            )}
                        </button>
                    </div>
                </form>
            </div>
        </div>
    );
};

export default TransactionModal;