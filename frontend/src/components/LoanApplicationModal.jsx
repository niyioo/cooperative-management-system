import React, { useState, useEffect } from 'react';
import { X, Landmark, AlertCircle, Loader2, DollarSign, Calendar, User, FileText, CheckCircle } from 'lucide-react';
import axiosInstance from '../api/axios';
import { useAuth } from '../hooks/useAuth';

const LoanApplicationModal = ({ isOpen, onClose, onSuccess }) => {
    const { user } = useAuth();
    const [members, setMembers] = useState([]);
    const [products, setProducts] = useState([]); 
    const [memberId, setMemberId] = useState('');
    const [productId, setProductId] = useState(''); 
    const [amount, setAmount] = useState('');
    const [duration, setDuration] = useState('12');
    const [purpose, setPurpose] = useState('');
    
    const [loadingData, setLoadingData] = useState(false);
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [error, setError] = useState('');

    useEffect(() => {
        if (isOpen) {
            const fetchData = async () => {
                setLoadingData(true);
                setError('');
                try {
                    // Fetch products (Everyone needs this) and members (Only if Admin)
                    const [prodRes, memRes] = await Promise.all([
                        axiosInstance.get('/loans/products/'),
                        user?.role !== 'MEMBER' ? axiosInstance.get('/members/profiles/') : Promise.resolve({ data: { results: [] } })
                    ]);
                    
                    setProducts(prodRes.data.results || prodRes.data);
                    
                    if (user?.role !== 'MEMBER') {
                        setMembers(memRes.data.results || memRes.data);
                    } else {
                        // Automatically set memberId for regular members applying for themselves
                        setMemberId(user?.member_profile?.id || '');
                    }
                } catch (err) {
                    console.error("Fetch error:", err);
                    setError("Could not load required data. Please check your connection.");
                } finally {
                    setLoadingData(false);
                }
            };
            fetchData();
        }
    }, [isOpen, user]);

    const handleSubmit = async (e) => {
        e.preventDefault();
        setError('');
        setIsSubmitting(true);

        try {
            const payload = {
                member_id: memberId,
                loan_product_id: productId,
                principal_amount: parseFloat(amount),
                duration_months: parseInt(duration, 10),
                purpose: purpose,
                status: 'PENDING'
            };

            await axiosInstance.post('/loans/applications/', payload);
            onSuccess('Loan application submitted successfully!');
            onClose();
        } catch (err) {
            console.error("Submission Error:", err.response?.data);
            const serverError = err.response?.data;
            if (serverError && typeof serverError === 'object') {
                const firstKey = Object.keys(serverError)[0];
                setError(`${firstKey.replace('_', ' ').toUpperCase()}: ${serverError[firstKey]}`);
            } else {
                setError('Failed to submit application. Please check your inputs.');
            }
        } finally {
            setIsSubmitting(false);
        }
    };

    if (!isOpen) return null;

    return (
        <div className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-sm animate-in fade-in duration-200">
            {/* Modal Container with Max Height and Internal Scroll */}
            <div className="bg-white rounded-3xl shadow-2xl w-full max-w-md max-h-[90vh] flex flex-col overflow-hidden animate-in zoom-in-95 duration-200 border border-slate-100">
                
                {/* Fixed Header */}
                <div className="px-6 py-5 border-b border-slate-100 flex items-center justify-between bg-slate-50/50 shrink-0">
                    <div className="flex items-center space-x-3">
                        <div className="bg-slate-900 p-2.5 rounded-xl text-white shadow-lg">
                            <Landmark className="h-5 w-5" />
                        </div>
                        <div>
                            <h2 className="text-lg font-black text-slate-900 tracking-tight uppercase">Loan Portal</h2>
                            <p className="text-[10px] font-bold text-blue-600 uppercase tracking-widest mt-1">
                                {user?.role === 'MEMBER' ? 'Personal Request' : 'New Application'}
                            </p>
                        </div>
                    </div>
                    <button onClick={onClose} className="p-2 hover:bg-slate-200 rounded-full transition-all text-slate-400">
                        <X className="h-5 w-5" />
                    </button>
                </div>

                {/* Scrollable Form Body */}
                <form onSubmit={handleSubmit} className="flex flex-col overflow-hidden">
                    <div className="flex-1 overflow-y-auto p-6 space-y-5 scrollbar-thin scrollbar-thumb-slate-200">
                        {error && (
                            <div className="mb-2 bg-red-50 border-l-4 border-red-500 p-3 rounded-r-lg flex items-start animate-in slide-in-from-top-2">
                                <AlertCircle className="h-5 w-5 text-red-500 mr-2 shrink-0" />
                                <p className="text-[10px] text-red-700 font-black uppercase leading-tight">{error}</p>
                            </div>
                        )}

                        {/* Loan Product Selection */}
                        <div className="space-y-1.5">
                            <label className="block text-[10px] font-black text-slate-400 uppercase tracking-widest ml-1">Loan Product Type</label>
                            <div className="relative">
                                <FileText className="absolute left-3.5 top-3.5 h-4 w-4 text-slate-400" />
                                <select
                                    required value={productId}
                                    onChange={(e) => setProductId(e.target.value)}
                                    className="block w-full pl-11 pr-4 py-3.5 border border-slate-200 rounded-2xl bg-white focus:ring-4 focus:ring-blue-500/5 focus:border-blue-500 text-sm font-bold outline-none appearance-none transition-all"
                                >
                                    <option value="" disabled>{loadingData ? 'Syncing...' : '-- Select Product --'}</option>
                                    {products.map(prod => (
                                        <option key={prod.id} value={prod.id}>{prod.name} ({prod.interest_rate}%)</option>
                                    ))}
                                </select>
                            </div>
                        </div>

                        {/* Applicant Selection - Only show for Admin */}
                        {user?.role !== 'MEMBER' ? (
                            <div className="space-y-1.5">
                                <label className="block text-[10px] font-black text-slate-400 uppercase tracking-widest ml-1">Applicant</label>
                                <div className="relative">
                                    <User className="absolute left-3.5 top-3.5 h-4 w-4 text-slate-400" />
                                    <select
                                        required value={memberId}
                                        onChange={(e) => setMemberId(e.target.value)}
                                        className="block w-full pl-11 pr-4 py-3.5 border border-slate-200 rounded-2xl bg-white focus:ring-4 focus:ring-blue-500/5 focus:border-blue-500 text-sm font-bold outline-none appearance-none transition-all"
                                    >
                                        <option value="" disabled>-- Select Member --</option>
                                        {members.map(member => (
                                            <option key={member.id} value={member.id}>{member.first_name} {member.last_name} ({member.membership_id})</option>
                                        ))}
                                    </select>
                                </div>
                            </div>
                        ) : (
                            <div className="p-4 bg-blue-50 rounded-2xl border border-blue-100 flex items-center space-x-3">
                                <div className="p-2 bg-white rounded-lg shadow-sm">
                                    <User className="h-4 w-4 text-blue-600" />
                                </div>
                                <div>
                                    <p className="text-[10px] font-black text-blue-400 uppercase tracking-widest leading-none mb-1">Applying as</p>
                                    <p className="text-sm font-bold text-blue-900 leading-none">{user?.first_name} {user?.last_name}</p>
                                </div>
                            </div>
                        )}

                        <div className="grid grid-cols-2 gap-4">
                            <div className="space-y-1.5">
                                <label className="block text-[10px] font-black text-slate-400 uppercase tracking-widest ml-1">Principal (₦)</label>
                                <div className="relative">
                                    <DollarSign className="absolute left-3.5 top-3.5 h-4 w-4 text-slate-400" />
                                    <input
                                        type="number" required value={amount} 
                                        onChange={(e) => setAmount(e.target.value)}
                                        className="block w-full pl-11 pr-4 py-3.5 border border-slate-200 rounded-2xl text-sm font-bold focus:ring-4 focus:ring-emerald-500/5 focus:border-emerald-500 outline-none transition-all" 
                                        placeholder="0.00"
                                    />
                                </div>
                            </div>
                            <div className="space-y-1.5">
                                <label className="block text-[10px] font-black text-slate-400 uppercase tracking-widest ml-1">Duration (Months)</label>
                                <div className="relative">
                                    <Calendar className="absolute left-3.5 top-3.5 h-4 w-4 text-slate-400" />
                                    <input
                                        type="number" required value={duration} 
                                        onChange={(e) => setDuration(e.target.value)}
                                        className="block w-full pl-11 pr-4 py-3.5 border border-slate-200 rounded-2xl text-sm font-bold focus:ring-4 focus:ring-blue-500/5 focus:border-blue-500 outline-none transition-all" 
                                    />
                                </div>
                            </div>
                        </div>

                        <div className="space-y-1.5">
                            <label className="block text-[10px] font-black text-slate-400 uppercase tracking-widest mb-1.5 ml-1">Loan Purpose</label>
                            <textarea
                                value={purpose}
                                required
                                onChange={(e) => setPurpose(e.target.value)}
                                className="block w-full px-5 py-3.5 border border-slate-200 rounded-2xl text-sm font-medium outline-none focus:ring-4 focus:ring-blue-500/5 focus:border-blue-500 h-24 resize-none transition-all"
                                placeholder="Briefly describe why you need this loan..."
                            />
                        </div>
                    </div>

                    {/* Fixed Footer */}
                    <div className="px-6 py-5 bg-slate-50 border-t border-slate-100 flex items-center justify-end space-x-3 shrink-0">
                        <button type="button" onClick={onClose} className="px-6 py-2.5 text-[11px] font-black uppercase tracking-widest text-slate-400 hover:text-slate-600 transition-colors">
                            Cancel
                        </button>
                        <button
                            type="submit"
                            disabled={isSubmitting || loadingData}
                            className="px-8 py-2.5 bg-blue-600 text-white text-[11px] font-black uppercase tracking-widest rounded-xl hover:bg-blue-700 transition-all shadow-xl shadow-blue-500/20 active:scale-95 disabled:opacity-50 flex items-center"
                        >
                            {isSubmitting ? (
                                <><Loader2 className="animate-spin h-4 w-4 mr-2" /> Processing</>
                            ) : (
                                <><CheckCircle className="h-4 w-4 mr-2" /> Submit Application</>
                            )}
                        </button>
                    </div>
                </form>
            </div>
        </div>
    );
};

export default LoanApplicationModal;