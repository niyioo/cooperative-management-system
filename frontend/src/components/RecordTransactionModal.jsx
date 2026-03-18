import React, { useState, useEffect } from 'react';
import axiosInstance from '../api/axios';
import { 
    X, Plus, Loader2, AlertCircle, CheckCircle, User, Hash, FileText, Calendar, Tag
} from 'lucide-react';

const RecordTransactionModal = ({ isOpen, onClose, onSuccess }) => {
    const [formData, setFormData] = useState({
        type: 'INCOME',
        category: '',
        amount: '',
        date: new Date().toISOString().split('T')[0],
        description: '',
        member: ''
    });
    
    const [members, setMembers] = useState([]); // Initialized as array
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [error, setError] = useState('');

    useEffect(() => {
        if (isOpen) {
            const fetchMembers = async () => {
                try {
                    const response = await axiosInstance.get('/members/profiles/');
                    
                    // ✅ FIX: Extract the array correctly from paginated or non-paginated responses
                    const data = Array.isArray(response.data) ? response.data : 
                                 (response.data.results && Array.isArray(response.data.results)) ? response.data.results : [];
                    
                    setMembers(data);
                } catch (err) {
                    console.error("Failed to fetch members for dropdown", err);
                    setMembers([]); // Safety fallback to prevent .map crash
                }
            };
            fetchMembers();
        }
    }, [isOpen]);

    const handleChange = (e) => {
        setFormData({ ...formData, [e.target.name]: e.target.value });
    };

    const handleSubmit = async (e) => {
        e.preventDefault();
        setError('');
        setIsSubmitting(true);

        try {
            const payload = {
                ...formData,
                member: formData.member === "" ? null : formData.member,
                amount: parseFloat(formData.amount)
            };

            await axiosInstance.post('/finance/ledger/', payload);
            
            if (onSuccess) onSuccess('Transaction recorded successfully!');
            setFormData({
                type: 'INCOME', category: '', amount: '',
                date: new Date().toISOString().split('T')[0],
                description: '', member: ''
            });
            onClose();
        } catch (err) {
            console.error("Submission failed:", err.response?.data);
            setError(err.response?.data?.detail || "Failed to record transaction. Please check all fields.");
        } finally {
            setIsSubmitting(false);
        }
    };

    if (!isOpen) return null;

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-sm animate-in fade-in duration-200">
            <div className="bg-white rounded-3xl shadow-2xl w-full max-w-lg overflow-hidden animate-in zoom-in-95 duration-200">
                
                {/* Header */}
                <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between bg-slate-50/50">
                    <div className="flex items-center space-x-3">
                        <div className="bg-blue-600 p-2 rounded-xl text-white shadow-sm">
                            <Plus className="h-5 w-5" />
                        </div>
                        <h2 className="text-xl font-black text-slate-900 tracking-tight">Record Transaction</h2>
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

                    {/* Type Toggle */}
                    <div className="flex bg-slate-100 p-1 rounded-2xl">
                        <button
                            type="button"
                            onClick={() => setFormData({...formData, type: 'INCOME'})}
                            className={`flex-1 py-2 text-xs font-black uppercase tracking-widest rounded-xl transition-all ${
                                formData.type === 'INCOME' ? 'bg-white text-emerald-600 shadow-sm' : 'text-slate-500'
                            }`}
                        >
                            Income
                        </button>
                        <button
                            type="button"
                            onClick={() => setFormData({...formData, type: 'EXPENSE'})}
                            className={`flex-1 py-2 text-xs font-black uppercase tracking-widest rounded-xl transition-all ${
                                formData.type === 'EXPENSE' ? 'bg-white text-red-600 shadow-sm' : 'text-slate-500'
                            }`}
                        >
                            Expense
                        </button>
                    </div>

                    <div className="grid grid-cols-2 gap-4">
                        <div className="space-y-1.5">
                            <label className="text-[10px] font-black text-slate-400 uppercase tracking-widest ml-1">Category</label>
                            <div className="relative">
                                <Tag className="absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
                                <input 
                                    required name="category" value={formData.category} onChange={handleChange}
                                    placeholder="e.g. Registration Fee"
                                    className="w-full pl-10 pr-4 py-2.5 border border-slate-200 rounded-xl text-sm focus:ring-2 focus:ring-blue-500 outline-none transition-all"
                                />
                            </div>
                        </div>
                        <div className="space-y-1.5">
                            <label className="text-[10px] font-black text-slate-400 uppercase tracking-widest ml-1">Amount (₦)</label>
                            <div className="relative">
                                <Hash className="absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
                                <input 
                                    required type="number" name="amount" value={formData.amount} onChange={handleChange}
                                    placeholder="0.00"
                                    className="w-full pl-10 pr-4 py-2.5 border border-slate-200 rounded-xl text-sm focus:ring-2 focus:ring-blue-500 outline-none transition-all"
                                />
                            </div>
                        </div>
                    </div>

                    <div className="space-y-1.5">
                        <label className="text-[10px] font-black text-slate-400 uppercase tracking-widest ml-1">Related Member (Optional)</label>
                        <div className="relative">
                            <User className="absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
                            <select 
                                name="member" value={formData.member} onChange={handleChange}
                                className="w-full pl-10 pr-4 py-2.5 border border-slate-200 rounded-xl text-sm focus:ring-2 focus:ring-blue-500 outline-none appearance-none bg-white"
                            >
                                <option value="">Global / No Specific Member</option>
                                {/* ✅ FIXED: Map only if members is an array */}
                                {Array.isArray(members) && members.map(m => (
                                    <option key={m.id} value={m.id}>
                                        {/* Use names from the nested user object or direct fields */}
                                        {m.user?.first_name || m.first_name} {m.user?.last_name || m.last_name} ({m.membership_id})
                                    </option>
                                ))}
                            </select>
                        </div>
                    </div>

                    <div className="space-y-1.5">
                        <label className="text-[10px] font-black text-slate-400 uppercase tracking-widest ml-1">Transaction Date</label>
                        <div className="relative">
                            <Calendar className="absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
                            <input 
                                required type="date" name="date" value={formData.date} onChange={handleChange}
                                className="w-full pl-10 pr-4 py-2.5 border border-slate-200 rounded-xl text-sm focus:ring-2 focus:ring-blue-500 outline-none transition-all"
                            />
                        </div>
                    </div>

                    <div className="space-y-1.5">
                        <label className="text-[10px] font-black text-slate-400 uppercase tracking-widest ml-1">Description</label>
                        <div className="relative">
                            <FileText className="absolute left-3 top-3 h-4 w-4 text-slate-400" />
                            <textarea 
                                name="description" value={formData.description} onChange={handleChange}
                                rows="2"
                                placeholder="Additional details..."
                                className="w-full pl-10 pr-4 py-2.5 border border-slate-200 rounded-xl text-sm focus:ring-2 focus:ring-blue-500 outline-none transition-all"
                            ></textarea>
                        </div>
                    </div>

                    <div className="pt-4 flex justify-end space-x-3 border-t border-slate-100">
                        <button type="button" onClick={onClose} className="px-5 py-2.5 text-sm font-bold text-slate-500 hover:text-slate-800">
                            Cancel
                        </button>
                        <button 
                            type="submit" disabled={isSubmitting}
                            className="px-8 py-2.5 bg-blue-600 text-white text-sm font-black rounded-xl hover:bg-blue-700 transition-all shadow-lg active:scale-95 disabled:opacity-50 flex items-center"
                        >
                            {isSubmitting ? <Loader2 className="animate-spin h-4 w-4 mr-2" /> : <CheckCircle className="h-4 w-4 mr-2" />}
                            Save Entry
                        </button>
                    </div>
                </form>
            </div>
        </div>
    );
};

export default RecordTransactionModal;