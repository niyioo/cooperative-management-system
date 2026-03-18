import React, { useState } from 'react';
import axiosInstance from '../api/axios';
import { 
    X, User, Mail, Lock, Phone, Loader2, UserPlus, CheckCircle, AlertCircle, MapPin 
} from 'lucide-react';

const RegisterNewMemberModal = ({ isOpen, onClose, onSuccess }) => {
    const [formData, setFormData] = useState({
        email: '',
        password: '',
        first_name: '',
        last_name: '',
        phone_number: '',
        residential_address: '', // ✅ ADDED: Required by Django backend
        role: 'MEMBER'
    });
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [error, setError] = useState('');

    const handleChange = (e) => {
        setFormData({ ...formData, [e.target.name]: e.target.value });
    };

    const handleSubmit = async (e) => {
        e.preventDefault();
        setError('');
        setIsSubmitting(true);

        try {
            await axiosInstance.post('/members/profiles/', formData);
            
            if (onSuccess) onSuccess('Member registered successfully!');
            
            setFormData({
                email: '', password: '', first_name: '', 
                last_name: '', phone_number: '', residential_address: '', role: 'MEMBER'
            });
            onClose();
        } catch (err) {
            console.error("Registration failed:", err.response?.data);
            const serverError = err.response?.data;

            // Cleans up the ugly Python dictionary error string if it gets caught in 'detail'
            let errorMessage = "Registration failed. Please try again.";
            
            if (serverError?.detail && typeof serverError.detail === 'string' && serverError.detail.includes('ERRORDETAIL')) {
                 errorMessage = "Please fill in all required fields correctly.";
            } else if (serverError && typeof serverError === 'object') {
                const firstKey = Object.keys(serverError)[0];
                const detail = serverError[firstKey];
                const cleanKey = firstKey.replace('_', ' ');
                errorMessage = `${cleanKey.toUpperCase()}: ${Array.isArray(detail) ? detail[0] : detail}`;
            }

            setError(errorMessage);
        } finally {
            setIsSubmitting(false);
        }
    };

    if (!isOpen) return null;

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-sm animate-in fade-in duration-200">
            <div className="bg-white rounded-2xl shadow-2xl w-full max-w-lg overflow-hidden animate-in zoom-in-95 duration-200">
                
                {/* Header */}
                <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between bg-slate-50/50">
                    <div className="flex items-center space-x-3">
                        <div className="bg-blue-600 p-2 rounded-xl text-white shadow-sm">
                            <UserPlus className="h-5 w-5" />
                        </div>
                        <h2 className="text-xl font-black text-slate-900 tracking-tight">Register New Member</h2>
                    </div>
                    <button onClick={onClose} className="p-2 hover:bg-slate-200 rounded-full transition-colors">
                        <X className="h-5 w-5 text-slate-500" />
                    </button>
                </div>

                <form onSubmit={handleSubmit} className="p-6 space-y-5">
                    {/* Error Banner */}
                    {error && (
                        <div className="bg-red-50 border-l-4 border-red-500 p-3 rounded-r-lg flex items-start">
                            <AlertCircle className="h-5 w-5 text-red-500 mr-2 shrink-0" />
                            <p className="text-xs text-red-700 font-bold uppercase tracking-tight">{error}</p>
                        </div>
                    )}

                    <div className="grid grid-cols-2 gap-4">
                        <div className="space-y-1.5">
                            <label className="text-[10px] font-black text-slate-400 uppercase tracking-widest ml-1">First Name</label>
                            <div className="relative">
                                <User className="absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
                                <input 
                                    required name="first_name" value={formData.first_name} onChange={handleChange}
                                    className="w-full pl-10 pr-4 py-2.5 border border-slate-200 rounded-xl text-sm focus:ring-2 focus:ring-blue-500 outline-none transition-all"
                                    placeholder="John"
                                />
                            </div>
                        </div>
                        <div className="space-y-1.5">
                            <label className="text-[10px] font-black text-slate-400 uppercase tracking-widest ml-1">Last Name</label>
                            <input 
                                required name="last_name" value={formData.last_name} onChange={handleChange}
                                className="w-full px-4 py-2.5 border border-slate-200 rounded-xl text-sm focus:ring-2 focus:ring-blue-500 outline-none transition-all"
                                placeholder="Doe"
                            />
                        </div>
                    </div>

                    <div className="grid grid-cols-2 gap-4">
                        <div className="space-y-1.5">
                            <label className="text-[10px] font-black text-slate-400 uppercase tracking-widest ml-1">Phone Number</label>
                            <div className="relative">
                                <Phone className="absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
                                <input 
                                    required type="tel" name="phone_number" value={formData.phone_number} onChange={handleChange}
                                    className="w-full pl-10 pr-4 py-2.5 border border-slate-200 rounded-xl text-sm focus:ring-2 focus:ring-blue-500 outline-none transition-all"
                                    placeholder="0800 000 0000"
                                />
                            </div>
                        </div>

                        <div className="space-y-1.5">
                            <label className="text-[10px] font-black text-slate-400 uppercase tracking-widest ml-1">Email Address</label>
                            <div className="relative">
                                <Mail className="absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
                                <input 
                                    required type="email" name="email" value={formData.email} onChange={handleChange}
                                    className="w-full pl-10 pr-4 py-2.5 border border-slate-200 rounded-xl text-sm focus:ring-2 focus:ring-blue-500 outline-none transition-all"
                                    placeholder="john@example.com"
                                />
                            </div>
                        </div>
                    </div>

                    {/* ✅ ADDED: Residential Address Field */}
                    <div className="space-y-1.5">
                        <label className="text-[10px] font-black text-slate-400 uppercase tracking-widest ml-1">Residential Address</label>
                        <div className="relative">
                            <MapPin className="absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
                            <input 
                                required type="text" name="residential_address" value={formData.residential_address} onChange={handleChange}
                                className="w-full pl-10 pr-4 py-2.5 border border-slate-200 rounded-xl text-sm focus:ring-2 focus:ring-blue-500 outline-none transition-all"
                                placeholder="123 Example Street, City"
                            />
                        </div>
                    </div>

                    <div className="space-y-1.5">
                        <label className="text-[10px] font-black text-slate-400 uppercase tracking-widest ml-1">Temp Password</label>
                        <div className="relative">
                            <Lock className="absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
                            <input 
                                required type="password" name="password" value={formData.password} onChange={handleChange}
                                className="w-full pl-10 pr-4 py-2.5 border border-slate-200 rounded-xl text-sm focus:ring-2 focus:ring-blue-500 outline-none transition-all"
                                placeholder="••••••••"
                            />
                        </div>
                    </div>

                    <div className="pt-6 flex justify-end space-x-3 border-t border-slate-100">
                        <button type="button" onClick={onClose} className="px-5 py-2.5 text-sm font-bold text-slate-500 hover:text-slate-800 transition-colors">
                            Cancel
                        </button>
                        <button 
                            type="submit" disabled={isSubmitting}
                            className="px-8 py-2.5 bg-blue-600 text-white text-sm font-black rounded-xl hover:bg-blue-700 transition-all shadow-lg active:scale-95 disabled:opacity-50 flex items-center"
                        >
                            {isSubmitting ? (
                                <><Loader2 className="animate-spin h-4 w-4 mr-2" /> Processing...</>
                            ) : (
                                <><CheckCircle className="h-4 w-4 mr-2" /> Create Account</>
                            )}
                        </button>
                    </div>
                </form>
            </div>
        </div>
    );
};

export default RegisterNewMemberModal;