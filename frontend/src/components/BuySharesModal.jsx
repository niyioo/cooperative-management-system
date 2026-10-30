import React, { useState, useEffect } from 'react';
import { X, PieChart, AlertCircle, Loader2, User, Hash, Coins } from 'lucide-react';
import axiosInstance from '../api/axios';

const BuySharesModal = ({ isOpen, onClose, onSuccess }) => {
    const [members, setMembers] = useState([]);
    const [memberId, setMemberId] = useState('');
    const [numShares, setNumShares] = useState('');
    
    const [loadingMembers, setLoadingMembers] = useState(false);
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [error, setError] = useState('');

    // The unit price is set by management in Settings; the server applies it.
    const [unitPrice, setUnitPrice] = useState(null);
    const totalCost = numShares && unitPrice ? parseInt(numShares, 10) * unitPrice : 0;

    useEffect(() => {
        if (isOpen) {
            const fetchMembers = async () => {
                setLoadingMembers(true);
                try {
                    const [membersRes, settingsRes] = await Promise.all([
                        axiosInstance.get('/members/profiles/', { params: { page_size: 100 } }),
                        axiosInstance.get('/core/settings/'),
                    ]);
                    setMembers(membersRes.data.results || membersRes.data);
                    const settings = (settingsRes.data.results || settingsRes.data)[0];
                    setUnitPrice(settings?.share_unit_price ? Number(settings.share_unit_price) : null);
                    if (!settings?.share_unit_price) setError("The share price hasn't been set yet. Set it in Settings first.");
                } catch (err) {
                    console.error("Failed to fetch members:", err);
                    setError("Could not load members for the dropdown.");
                } finally {
                    setLoadingMembers(false);
                }
            };
            fetchMembers();
        } else {
            // Reset state when closed
            setMemberId('');
            setNumShares('');
            setError('');
        }
    }, [isOpen]);

    if (!isOpen) return null;

    const handleSubmit = async (e) => {
        e.preventDefault();
        setError('');
        setIsSubmitting(true);

        try {
            await axiosInstance.post('/shares/transactions/', {
                member: memberId,
                number_of_shares: parseInt(numShares, 10),
            });
            
            onSuccess(`Successfully purchased ${numShares} shares!`);
        } catch (err) {
            const data = err.response?.data || {};
            const first = Object.values(data)[0];
            setError(data.detail || (Array.isArray(first) ? first[0] : first) || 'Failed to process share purchase.');
        } finally {
            setIsSubmitting(false);
        }
    };

    const formatCurrency = (amount) => {
        return new Intl.NumberFormat('en-NG', { style: 'currency', currency: 'NGN' }).format(amount);
    };

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/50 backdrop-blur-sm transition-opacity">
            <div className="bg-white rounded-xl shadow-xl w-full max-w-md overflow-hidden animate-in fade-in zoom-in-95 duration-200">
                
                {/* Modal Header */}
                <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between bg-slate-50/50">
                    <div className="flex items-center space-x-2">
                        <div className="bg-indigo-100 p-2 rounded-lg text-indigo-600">
                            <PieChart className="h-5 w-5" />
                        </div>
                        <h2 className="text-lg font-semibold text-slate-800">Buy Shares</h2>
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
                            <p className="text-sm text-red-700">{error}</p>
                        </div>
                    )}

                    <div className="space-y-5">
                        {/* Member Selection */}
                        <div>
                            <label className="block text-sm font-medium text-slate-700 mb-1">Shareholder</label>
                            <div className="relative">
                                <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                                    <User className="h-4 w-4 text-slate-400" />
                                </div>
                                <select
                                    required
                                    value={memberId}
                                    onChange={(e) => setMemberId(e.target.value)}
                                    disabled={loadingMembers}
                                    className="block w-full pl-10 pr-3 py-2 border border-slate-300 bg-white rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500 sm:text-sm disabled:bg-slate-50"
                                >
                                    <option value="" disabled>
                                        {loadingMembers ? 'Loading members...' : '-- Select a member --'}
                                    </option>
                                    {members.map(member => (
                                        <option key={member.id} value={member.id}>
                                            {member.first_name} {member.last_name} ({member.membership_id})
                                        </option>
                                    ))}
                                </select>
                            </div>
                        </div>

                        {/* Number of Shares */}
                        <div>
                            <label className="block text-sm font-medium text-slate-700 mb-1">Number of Shares</label>
                            <div className="relative">
                                <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                                    <Hash className="h-4 w-4 text-slate-400" />
                                </div>
                                <input
                                    type="number"
                                    required
                                    min="1"
                                    step="1"
                                    value={numShares}
                                    onChange={(e) => setNumShares(e.target.value)}
                                    className="block w-full pl-10 pr-3 py-2 border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500 sm:text-sm"
                                    placeholder="e.g. 50"
                                />
                            </div>
                            <p className="mt-1.5 text-xs text-slate-500">Unit Price: {unitPrice ? formatCurrency(unitPrice) : '—'} per share</p>
                        </div>

                        {/* Calculated Total (Visual Only) */}
                        <div className="bg-slate-50 p-4 rounded-lg border border-slate-100 flex items-center justify-between">
                            <div className="flex items-center text-slate-600">
                                <Coins className="h-5 w-5 mr-2 text-indigo-500" />
                                <span className="text-sm font-medium">Total Cost</span>
                            </div>
                            <span className="text-lg font-bold text-slate-900">
                                {formatCurrency(totalCost)}
                            </span>
                        </div>
                    </div>

                    {/* Modal Footer */}
                    <div className="mt-8 flex items-center justify-end space-x-3">
                        <button
                            type="button"
                            onClick={onClose}
                            className="px-4 py-2 text-sm font-medium text-slate-700 bg-white border border-slate-300 rounded-lg hover:bg-slate-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-slate-500"
                        >
                            Cancel
                        </button>
                        <button
                            type="submit"
                            disabled={isSubmitting || loadingMembers || !numShares || totalCost <= 0}
                            className="inline-flex items-center px-4 py-2 text-sm font-medium text-white bg-indigo-600 border border-transparent rounded-lg hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 disabled:bg-indigo-400 transition-colors"
                        >
                            {isSubmitting ? (
                                <><Loader2 className="animate-spin h-4 w-4 mr-2" /> Processing...</>
                            ) : (
                                'Confirm Purchase'
                            )}
                        </button>
                    </div>
                </form>
            </div>
        </div>
    );
};

export default BuySharesModal;