import React, { useState, useEffect } from 'react';
import { X, Receipt, AlertCircle, Loader2, User, Tag, DollarSign, Calendar, FileText, CheckCircle } from 'lucide-react';
import axiosInstance from '../api/axios';

const NewAssessmentModal = ({ isOpen, onClose, onSuccess }) => {
    const [members, setMembers] = useState([]);
    const [memberId, setMemberId] = useState('');
    const [type, setType] = useState('MONTHLY_DUES');
    const [amount, setAmount] = useState('');
    const [dueDate, setDueDate] = useState('');
    const [reference, setReference] = useState('');
    
    const [loadingMembers, setLoadingMembers] = useState(false);
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [error, setError] = useState('');

    // Fetch members and setup defaults when modal opens
    useEffect(() => {
        if (isOpen) {
            const fetchMembers = async () => {
                setLoadingMembers(true);
                try {
                    // Hits the updated members app endpoint
                    const response = await axiosInstance.get('/members/profiles/');
                    const data = response.data.results || response.data;
                    setMembers(Array.isArray(data) ? data : []);
                } catch (err) {
                    console.error("Failed to fetch members:", err);
                    setError("Could not load members for the dropdown.");
                } finally {
                    setLoadingMembers(false);
                }
            };
            fetchMembers();
            
            // Set default due date to 30 days from now
            const defaultDate = new Date();
            defaultDate.setDate(defaultDate.getDate() + 30);
            setDueDate(defaultDate.toISOString().split('T')[0]);
        } else {
            // Reset state when closed
            setMemberId('');
            setType('MONTHLY_DUES');
            setAmount('');
            setReference('');
            setError('');
        }
    }, [isOpen]);

    const handleSubmit = async (e) => {
        e.preventDefault();
        setError('');
        setIsSubmitting(true);

        try {
            // Payload constructed to match backend field names (member_id)
            const payload = {
                member_id: memberId, 
                type: type,
                amount: parseFloat(amount),
                due_date: dueDate,
                reference_id: reference || `ASSESS-${Math.floor(1000 + Math.random() * 9000)}`,
                status: 'PENDING'
            };

            await axiosInstance.post('/contributions/', payload);
            
            onSuccess('Assessment created successfully!');
            onClose();
        } catch (err) {
            console.error("Backend Error Details:", err.response?.data);
            const serverError = err.response?.data;

            // Extract specific field errors from Django
            if (serverError && typeof serverError === 'object') {
                const firstKey = Object.keys(serverError)[0];
                const detail = serverError[firstKey];
                const cleanKey = firstKey.replace('_', ' ');
                setError(`${cleanKey.toUpperCase()}: ${Array.isArray(detail) ? detail[0] : detail}`);
            } else {
                setError('Failed to create assessment. Please check your inputs.');
            }
        } finally {
            setIsSubmitting(false);
        }
    };

    if (!isOpen) return null;

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-sm animate-in fade-in duration-200">
            <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md overflow-hidden animate-in zoom-in-95 duration-200">
                
                {/* Modal Header */}
                <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between bg-slate-50/50">
                    <div className="flex items-center space-x-3">
                        <div className="bg-slate-900 p-2 rounded-xl text-white">
                            <Receipt className="h-5 w-5" />
                        </div>
                        <h2 className="text-lg font-black text-slate-800 tracking-tight">New Assessment</h2>
                    </div>
                    <button onClick={onClose} className="p-2 hover:bg-slate-200 rounded-full transition-colors text-slate-400">
                        <X className="h-5 w-5" />
                    </button>
                </div>

                {/* Modal Body */}
                <form onSubmit={handleSubmit} className="p-6">
                    {error && (
                        <div className="mb-5 bg-red-50 border-l-4 border-red-500 p-3 rounded-r-lg flex items-start animate-in slide-in-from-left-2">
                            <AlertCircle className="h-5 w-5 text-red-500 mr-2 shrink-0" />
                            <p className="text-xs text-red-700 font-bold uppercase tracking-tight">{error}</p>
                        </div>
                    )}

                    <div className="space-y-4">
                        {/* Member Selection */}
                        <div>
                            <label className="block text-[10px] font-black text-slate-400 uppercase tracking-widest mb-1.5 ml-1">Assign To Member</label>
                            <div className="relative">
                                <User className="absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
                                <select
                                    required
                                    value={memberId}
                                    onChange={(e) => setMemberId(e.target.value)}
                                    disabled={loadingMembers}
                                    className="block w-full pl-10 pr-4 py-2.5 border border-slate-200 rounded-xl bg-white focus:ring-2 focus:ring-blue-500 text-sm outline-none appearance-none disabled:bg-slate-50"
                                >
                                    <option value="" disabled>
                                        {loadingMembers ? 'Syncing members...' : '-- Select Member --'}
                                    </option>
                                    {members.map(member => (
                                        <option key={member.id} value={member.id}>
                                            {member.first_name} {member.last_name} ({member.membership_id})
                                        </option>
                                    ))}
                                </select>
                            </div>
                        </div>

                        {/* Assessment Type */}
                        <div>
                            <label className="block text-[10px] font-black text-slate-400 uppercase tracking-widest mb-1.5 ml-1">Bill Category</label>
                            <div className="relative">
                                <Tag className="absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
                                <select
                                    required
                                    value={type}
                                    onChange={(e) => setType(e.target.value)}
                                    className="block w-full pl-10 pr-4 py-2.5 border border-slate-200 rounded-xl bg-white focus:ring-2 focus:ring-blue-500 text-sm outline-none appearance-none"
                                >
                                    <option value="MONTHLY_DUES">Monthly Dues</option>
                                    <option value="LEVY">Project Levy</option>
                                    <option value="FINE">Penalty Fine</option>
                                </select>
                            </div>
                        </div>

                        {/* Amount & Due Date Row */}
                        <div className="grid grid-cols-2 gap-4">
                            <div>
                                <label className="block text-[10px] font-black text-slate-400 uppercase tracking-widest mb-1.5 ml-1">Amount (₦)</label>
                                <div className="relative">
                                    <DollarSign className="absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
                                    <input
                                        type="number"
                                        required
                                        min="1"
                                        step="0.01"
                                        value={amount}
                                        onChange={(e) => setAmount(e.target.value)}
                                        className="block w-full pl-10 pr-4 py-2.5 border border-slate-200 rounded-xl focus:ring-2 focus:ring-blue-500 text-sm outline-none"
                                        placeholder="0.00"
                                    />
                                </div>
                            </div>
                            <div>
                                <label className="block text-[10px] font-black text-slate-400 uppercase tracking-widest mb-1.5 ml-1">Due Date</label>
                                <div className="relative">
                                    <Calendar className="absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
                                    <input
                                        type="date"
                                        required
                                        value={dueDate}
                                        onChange={(e) => setDueDate(e.target.value)}
                                        className="block w-full pl-10 pr-4 py-2.5 border border-slate-200 rounded-xl focus:ring-2 focus:ring-blue-500 text-sm outline-none"
                                    />
                                </div>
                            </div>
                        </div>

                        {/* Reference / Notes */}
                        <div>
                            <label className="block text-[10px] font-black text-slate-400 uppercase tracking-widest mb-1.5 ml-1">Note / Reference</label>
                            <div className="relative">
                                <FileText className="absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
                                <input
                                    type="text"
                                    value={reference}
                                    onChange={(e) => setReference(e.target.value)}
                                    className="block w-full pl-10 pr-4 py-2.5 border border-slate-200 rounded-xl focus:ring-2 focus:ring-blue-500 text-sm outline-none"
                                    placeholder="e.g. March Meeting Fine"
                                />
                            </div>
                        </div>
                    </div>

                    {/* Modal Footer */}
                    <div className="mt-8 flex items-center justify-end space-x-3">
                        <button 
                            type="button" 
                            onClick={onClose} 
                            className="px-4 py-2 text-sm font-bold text-slate-400 hover:text-slate-600 transition-colors"
                        >
                            Cancel
                        </button>
                        <button
                            type="submit"
                            disabled={isSubmitting || loadingMembers}
                            className="px-8 py-2.5 bg-slate-900 text-white text-sm font-black rounded-xl hover:bg-black transition-all shadow-lg active:scale-95 disabled:opacity-50 flex items-center"
                        >
                            {isSubmitting ? (
                                <><Loader2 className="animate-spin h-4 w-4 mr-2" /> Processing...</>
                            ) : (
                                <><CheckCircle className="h-4 w-4 mr-2" /> Create Assessment</>
                            )}
                        </button>
                    </div>
                </form>
            </div>
        </div>
    );
};

export default NewAssessmentModal;