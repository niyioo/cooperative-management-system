import React, { useState, useEffect } from 'react';
import axiosInstance from '../../api/axios';
import { useAuth } from '../../hooks/useAuth';
import { 
    Search, Plus, MoreVertical, Edit, ShieldCheck, AlertCircle, Loader2, User 
} from 'lucide-react';
import RegisterNewMemberModal from '../../components/RegisterNewMemberModal';
import MemberProfileModal from '../../components/MemberProfileModal';
import { format } from 'date-fns';

const Members = () => {
    const { isManager } = useAuth();
    const [members, setMembers] = useState([]);
    const [isRegisterModalOpen, setIsRegisterModalOpen] = useState(false);
    const [isViewModalOpen, setIsViewModalOpen] = useState(false);
    const [selectedMember, setSelectedMember] = useState(null);
    const [successMessage, setSuccessMessage] = useState('');
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');
    const [searchTerm, setSearchTerm] = useState('');

    const fetchMembers = async () => {
        try {
            setError('');
            const response = await axiosInstance.get('/members/profiles/');
            const data = response.data.results || response.data;
            setMembers(Array.isArray(data) ? data : []);
        } catch (err) {
            console.error("Failed to fetch members:", err);
            setError('Failed to load members data. Please try again later.');
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchMembers();
    }, []);

    const handleApprove = async (id) => {
        try {
            await axiosInstance.post(`/members/profiles/${id}/approve/`);
            setSuccessMessage('Member approved successfully!');
            fetchMembers(); // Refresh data
            setTimeout(() => setSuccessMessage(''), 3000);
        } catch (err) {
            setError('Failed to approve member.');
        }
    };

    const filteredMembers = members.filter(member => 
        member.first_name?.toLowerCase().includes(searchTerm.toLowerCase()) ||
        member.last_name?.toLowerCase().includes(searchTerm.toLowerCase()) ||
        member.membership_id?.toLowerCase().includes(searchTerm.toLowerCase()) ||
        member.email?.toLowerCase().includes(searchTerm.toLowerCase())
    );

    const getStatusBadge = (status) => {
        switch (status) {
            case 'ACTIVE':
                return <span className="px-2.5 py-0.5 rounded-full text-xs font-medium bg-emerald-100 text-emerald-800 border border-emerald-200">Active</span>;
            case 'SUSPENDED':
                return <span className="px-2.5 py-0.5 rounded-full text-xs font-medium bg-red-100 text-red-800 border border-red-200">Suspended</span>;
            default:
                return <span className="px-2.5 py-0.5 rounded-full text-xs font-medium bg-slate-100 text-slate-800 border border-slate-200">Inactive</span>;
        }
    };

    if (loading) {
        return (
            <div className="flex h-full items-center justify-center p-12">
                <Loader2 className="animate-spin h-8 w-8 text-blue-500" />
            </div>
        );
    }

    return (
        <div className="space-y-6">
            {/* Header Section */}
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                <div>
                    <h1 className="text-2xl font-bold text-slate-900">Cooperative Members</h1>
                    <p className="text-sm text-slate-500 mt-1">Manage all registered members, their status, and profiles.</p>
                </div>
                
                {isManager && (
                    <button 
                        onClick={() => setIsRegisterModalOpen(true)}
                        className="inline-flex items-center justify-center px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700 transition-colors shadow-sm"
                    >
                        <Plus className="h-4 w-4 mr-2" />
                        Add New Member
                    </button>
                )}
            </div>

            {/* Error & Success States */}
            {error && (
                <div className="bg-red-50 border-l-4 border-red-500 p-4 rounded flex items-center">
                    <AlertCircle className="h-5 w-5 text-red-500 mr-2" />
                    <p className="text-sm text-red-700">{error}</p>
                </div>
            )}

            {/* Main Content Card */}
            <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
                <div className="p-4 border-b border-slate-200 bg-slate-50/50 flex items-center justify-between">
                    <div className="relative w-full max-w-md">
                        <Search className="absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
                        <input
                            type="text"
                            placeholder="Search by name, ID, or email..."
                            value={searchTerm}
                            onChange={(e) => setSearchTerm(e.target.value)}
                            className="block w-full pl-10 pr-3 py-2 border border-slate-300 rounded-lg bg-white focus:ring-2 focus:ring-blue-500 text-sm"
                        />
                    </div>
                </div>

                <div className="overflow-x-auto">
                    <table className="min-w-full divide-y divide-slate-200">
                        <thead className="bg-slate-50">
                            <tr>
                                <th className="px-6 py-3 text-left text-xs font-semibold text-slate-500 uppercase">Member Info</th>
                                <th className="px-6 py-3 text-left text-xs font-semibold text-slate-500 uppercase">Contact</th>
                                <th className="px-6 py-3 text-left text-xs font-semibold text-slate-500 uppercase">Status</th>
                                <th className="px-6 py-3 text-left text-xs font-semibold text-slate-500 uppercase">Joined Date</th>
                                <th className="relative px-6 py-3"><span className="sr-only">Actions</span></th>
                            </tr>
                        </thead>
                        <tbody className="bg-white divide-y divide-slate-200">
                            {filteredMembers.length > 0 ? (
                                filteredMembers.map((member) => (
                                    <tr 
                                        key={member.id} 
                                        className="hover:bg-slate-50 transition-colors group cursor-pointer"
                                        onClick={() => { setSelectedMember(member); setIsViewModalOpen(true); }}
                                    >
                                        <td className="px-6 py-4">
                                            <div className="flex items-center">
                                                <div className="h-10 w-10 bg-blue-50 text-blue-600 rounded-full flex items-center justify-center font-bold border border-blue-100">
                                                    {member.first_name?.[0]}{member.last_name?.[0]}
                                                </div>
                                                <div className="ml-4">
                                                    <div className="text-sm font-medium text-slate-900">{member.first_name} {member.last_name}</div>
                                                    <div className="text-xs font-mono text-slate-500">{member.membership_id}</div>
                                                </div>
                                            </div>
                                        </td>
                                        <td className="px-6 py-4">
                                            <div className="text-sm text-slate-900">{member.email}</div>
                                            <div className="text-sm text-slate-500">{member.phone_number}</div>
                                        </td>
                                        <td className="px-6 py-4">{getStatusBadge(member.status)}</td>
                                        <td className="px-6 py-4 text-sm text-slate-500">
                                            {member.created_at ? format(new Date(member.created_at), 'MMM dd, yyyy') : 'N/A'}
                                        </td>
                                        <td className="px-6 py-4 text-right" onClick={(e) => e.stopPropagation()}>
                                            <div className="flex items-center justify-end space-x-2 opacity-0 group-hover:opacity-100 transition-opacity">
                                                {member.status === 'INACTIVE' && isManager && (
                                                    <button 
                                                        onClick={() => handleApprove(member.id)}
                                                        className="text-emerald-600 hover:bg-emerald-50 p-1.5 rounded-lg transition-colors"
                                                        title="Approve Member"
                                                    >
                                                        <ShieldCheck className="h-5 w-5" />
                                                    </button>
                                                )}
                                                <button className="text-blue-600 hover:bg-blue-50 p-1.5 rounded-lg transition-colors" title="Edit Profile">
                                                    <Edit className="h-5 w-5" />
                                                </button>
                                                <button className="text-slate-400 hover:bg-slate-100 p-1.5 rounded-lg transition-colors">
                                                    <MoreVertical className="h-5 w-5" />
                                                </button>
                                            </div>
                                        </td>
                                    </tr>
                                ))
                            ) : (
                                <tr>
                                    <td colSpan="5" className="px-6 py-12 text-center text-slate-500 italic">No members found matching your search.</td>
                                </tr>
                            )}
                        </tbody>
                    </table>
                </div>
            </div>

            {/* Success Toast */}
            {successMessage && (
                <div className="fixed bottom-4 right-4 bg-slate-900 text-white px-6 py-3 rounded-xl shadow-2xl animate-in fade-in slide-in-from-bottom-5 z-50 flex items-center">
                    <ShieldCheck className="h-5 w-5 text-emerald-400 mr-3" />
                    {successMessage}
                </div>
            )}

            {/* Modals */}
            <RegisterNewMemberModal 
                isOpen={isRegisterModalOpen} 
                onClose={() => setIsRegisterModalOpen(false)} 
                onSuccess={() => {
                    fetchMembers();
                    setSuccessMessage('Member account created successfully!');
                    setTimeout(() => setSuccessMessage(''), 3000);
                }}
            />

            <MemberProfileModal 
                isOpen={isViewModalOpen} 
                onClose={() => setIsViewModalOpen(false)} 
                member={selectedMember}
                onStatusChange={fetchMembers} // This is key!
            />
        </div>
    );
};

export default Members;