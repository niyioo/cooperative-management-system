import React, { useState } from 'react';
import axiosInstance from '../api/axios';
import { useAuth } from '../hooks/useAuth';
import { 
    X, User, Phone, MapPin, Calendar, ShieldCheck, 
    FileText, Heart, Ban, CheckCircle, Loader2, AlertTriangle 
} from 'lucide-react';

const MemberProfileModal = ({ isOpen, onClose, member, onStatusChange }) => {
    const { isManager } = useAuth();
    const [isUpdating, setIsUpdating] = useState(false);

    if (!isOpen || !member) return null;

    const handleStatusUpdate = async (newStatus) => {
        setIsUpdating(true);
        try {
            await axiosInstance.post(`/members/profiles/${member.id}/update_status/`, {
                status: newStatus
            });
            if (onStatusChange) onStatusChange(); // Refresh the table in Members.jsx
            onClose(); // Close modal after success
        } catch (err) {
            console.error("Status update failed", err);
            alert("Failed to update status. Please try again.");
        } finally {
            setIsUpdating(false);
        }
    };

    const StatusBadge = ({ status }) => {
        const styles = {
            ACTIVE: 'bg-emerald-100 text-emerald-700',
            INACTIVE: 'bg-amber-100 text-amber-700',
            SUSPENDED: 'bg-red-100 text-red-700',
        };
        return (
            <span className={`px-2 py-1 rounded-full text-xs font-bold ${styles[status] || 'bg-slate-100'}`}>
                {status}
            </span>
        );
    };

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-sm">
            <div className="bg-white rounded-2xl shadow-xl w-full max-w-2xl max-h-[90vh] overflow-y-auto animate-in zoom-in duration-200">
                {/* Header with Photo Overlay */}
                <div className="relative h-32 bg-slate-800">
                    <button onClick={onClose} className="absolute top-4 right-4 p-2 bg-white/10 hover:bg-white/20 rounded-full transition-colors text-white">
                        <X className="h-5 w-5" />
                    </button>
                    <div className="absolute -bottom-12 left-8">
                        {member.passport_photo ? (
                            <img src={member.passport_photo} alt="Profile" className="h-24 w-24 rounded-2xl border-4 border-white object-cover shadow-md" />
                        ) : (
                            <div className="h-24 w-24 rounded-2xl border-4 border-white bg-blue-600 flex items-center justify-center text-white text-3xl font-bold shadow-md">
                                {member.first_name[0]}{member.last_name[0]}
                            </div>
                        )}
                    </div>
                </div>

                <div className="pt-16 px-8 pb-8 space-y-8">
                    {/* Basic Info */}
                    <div className="flex justify-between items-start">
                        <div>
                            <h2 className="text-2xl font-bold text-slate-900">{member.first_name} {member.last_name}</h2>
                            <p className="text-slate-500 font-mono text-sm">{member.membership_id}</p>
                        </div>
                        <StatusBadge status={member.status} />
                    </div>

                    {/* Contact & Next of Kin Grid (Same as before) */}
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                        <div className="space-y-4">
                            <h3 className="text-sm font-bold text-slate-400 uppercase flex items-center"><Phone className="h-4 w-4 mr-2" /> Contact</h3>
                            <div className="text-sm text-slate-600 space-y-2">
                                <p>{member.phone_number}</p>
                                <p>{member.email}</p>
                                <p className="italic">{member.residential_address || 'No address'}</p>
                            </div>
                        </div>
                        <div className="space-y-4">
                            <h3 className="text-sm font-bold text-slate-400 uppercase flex items-center"><Heart className="h-4 w-4 mr-2" /> Next of Kin</h3>
                            <div className="p-3 bg-slate-50 rounded-lg text-sm">
                                {member.next_of_kin ? (
                                    <>
                                        <p className="font-bold">{member.next_of_kin.full_name}</p>
                                        <p className="text-blue-600 text-xs uppercase">{member.next_of_kin.relationship}</p>
                                    </>
                                ) : <p className="text-slate-400">Not provided</p>}
                            </div>
                        </div>
                    </div>

                    {/* Admin Action Section */}
                    {isManager && (
                        <div className="pt-6 border-t border-slate-100">
                            <h3 className="text-sm font-bold text-slate-900 mb-4 flex items-center">
                                <ShieldCheck className="h-4 w-4 mr-2 text-blue-600" /> Administrative Actions
                            </h3>
                            <div className="flex flex-wrap gap-3">
                                {member.status !== 'ACTIVE' && (
                                    <button 
                                        onClick={() => handleStatusUpdate('ACTIVE')}
                                        disabled={isUpdating}
                                        className="inline-flex items-center px-4 py-2 bg-emerald-600 text-white text-sm font-bold rounded-lg hover:bg-emerald-700 transition-all disabled:opacity-50"
                                    >
                                        {isUpdating ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <CheckCircle className="h-4 w-4 mr-2" />}
                                        Activate Member
                                    </button>
                                )}

                                {member.status !== 'SUSPENDED' && (
                                    <button 
                                        onClick={() => handleStatusUpdate('SUSPENDED')}
                                        disabled={isUpdating}
                                        className="inline-flex items-center px-4 py-2 bg-red-50 text-red-600 border border-red-100 text-sm font-bold rounded-lg hover:bg-red-100 transition-all disabled:opacity-50"
                                    >
                                        {isUpdating ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <Ban className="h-4 w-4 mr-2" />}
                                        Suspend Member
                                    </button>
                                )}

                                {member.status === 'SUSPENDED' && (
                                    <button 
                                        onClick={() => handleStatusUpdate('INACTIVE')}
                                        disabled={isUpdating}
                                        className="inline-flex items-center px-4 py-2 bg-amber-50 text-amber-600 border border-amber-100 text-sm font-bold rounded-lg hover:bg-amber-100 transition-all disabled:opacity-50"
                                    >
                                        <AlertTriangle className="h-4 w-4 mr-2" />
                                        Set to Inactive
                                    </button>
                                )}
                            </div>
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
};

export default MemberProfileModal;