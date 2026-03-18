import React, { useState, useEffect } from 'react';
import axiosInstance from '../../api/axios';
import { useAuth } from '../../hooks/useAuth';
import { 
    Search, Plus, Receipt, AlertCircle, Loader2, CheckCircle, Clock, AlertOctagon, FileText
} from 'lucide-react';
import { format, isPast } from 'date-fns';
import NewAssessmentModal from '../../components/NewAssessmentModal';

const Contributions = () => {
    const { isManager } = useAuth();
    const [contributions, setContributions] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');
    const [searchTerm, setSearchTerm] = useState('');

    // Modal & Toast State
    const [isModalOpen, setIsModalOpen] = useState(false);
    const [successMessage, setSuccessMessage] = useState('');

    const fetchContributions = async () => {
        try {
            const response = await axiosInstance.get('/contributions/');
            // Safely extract the data, checking for paginated results
            const rawData = response.data?.results || response.data;
            
            // BULLETPROOF CHECK: Ensure we only ever set an Array into state
            if (Array.isArray(rawData)) {
                setContributions(rawData);
            } else {
                console.warn("API did not return an array for contributions:", rawData);
                setContributions([]); // Default to empty array to prevent crashes
            }
        } catch (err) {
            console.error("Failed to fetch contributions:", err);
            setError('Failed to load contribution records. Please try again later.');
            setContributions([]); // Failsafe
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchContributions();
    }, []);

    // Quick Stats Calculations (Safely fallback to 0 if amount is missing)
    const totalCollected = contributions
        .filter(c => c?.status === 'PAID')
        .reduce((sum, c) => sum + parseFloat(c?.amount || 0), 0);
        
    const pendingAmount = contributions
        .filter(c => c?.status === 'PENDING')
        .reduce((sum, c) => sum + parseFloat(c?.amount || 0), 0);
        
    const activeFines = contributions.filter(c => c?.type === 'FINE' && c?.status === 'PENDING').length;

    // Filter based on search input (Safely handle missing member data)
    const filteredContributions = contributions.filter(c => {
        const firstName = c?.member?.first_name || '';
        const lastName = c?.member?.last_name || '';
        const memberName = `${firstName} ${lastName}`.toLowerCase();
        
        const refId = c?.reference_id?.toLowerCase() || '';
        const search = searchTerm.toLowerCase();
        
        return memberName.includes(search) || refId.includes(search);
    });

    const formatCurrency = (amount) => {
        // Prevent NaN errors if amount is invalid
        const validAmount = isNaN(amount) ? 0 : amount;
        return new Intl.NumberFormat('en-NG', { style: 'currency', currency: 'NGN' }).format(validAmount);
    };

    const getTypeBadge = (type) => {
        switch (type) {
            case 'MONTHLY_DUES':
                return <span className="text-xs font-medium text-blue-600 bg-blue-50 px-2 py-0.5 rounded border border-blue-100">Monthly Dues</span>;
            case 'LEVY':
                return <span className="text-xs font-medium text-purple-600 bg-purple-50 px-2 py-0.5 rounded border border-purple-100">Project Levy</span>;
            case 'FINE':
                return <span className="text-xs font-medium text-red-600 bg-red-50 px-2 py-0.5 rounded border border-red-100">Penalty Fine</span>;
            default:
                return <span className="text-xs font-medium text-slate-600 bg-slate-50 px-2 py-0.5 rounded border border-slate-100">General</span>;
        }
    };

    const getStatusBadge = (status, dueDate) => {
        if (status === 'PAID') {
            return <span className="px-2.5 py-0.5 rounded-full text-xs font-medium bg-emerald-100 text-emerald-800 border border-emerald-200 flex items-center w-max"><CheckCircle className="h-3 w-3 mr-1" /> Paid</span>;
        }
        
        // Safely check if pending and past due date
        if (status === 'PENDING' && dueDate) {
            try {
                if (isPast(new Date(dueDate))) {
                    return <span className="px-2.5 py-0.5 rounded-full text-xs font-medium bg-red-100 text-red-800 border border-red-200 flex items-center w-max"><AlertOctagon className="h-3 w-3 mr-1" /> Overdue</span>;
                }
            } catch (e) {
                // If the date string is broken, just show pending
            }
        }

        return <span className="px-2.5 py-0.5 rounded-full text-xs font-medium bg-amber-100 text-amber-800 border border-amber-200 flex items-center w-max"><Clock className="h-3 w-3 mr-1" /> Pending</span>;
    };

    if (loading) {
        return (
            <div className="flex h-full items-center justify-center">
                <Loader2 className="animate-spin h-8 w-8 text-blue-500" />
            </div>
        );
    }

    return (
        <div className="space-y-6">
            {/* Header Section */}
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                <div>
                    <h1 className="text-2xl font-bold text-slate-900">Contributions & Levies</h1>
                    <p className="text-sm text-slate-500 mt-1">Manage mandatory dues, special levies, and penalty fines.</p>
                </div>
                
                {isManager && (
                    <div className="flex space-x-3">
                        <button 
                            onClick={() => setIsModalOpen(true)}
                            className="inline-flex items-center justify-center px-4 py-2 bg-slate-800 text-white text-sm font-medium rounded-lg hover:bg-slate-900 transition-colors shadow-sm"
                        >
                            <Plus className="h-4 w-4 mr-2" />
                            New Assessment
                        </button>
                    </div>
                )}
            </div>

            {/* Error State */}
            {error && (
                <div className="bg-red-50 border-l-4 border-red-500 p-4 rounded-r-lg">
                    <div className="flex items-center">
                        <AlertCircle className="h-5 w-5 text-red-500 mr-2" />
                        <p className="text-sm text-red-700">{error}</p>
                    </div>
                </div>
            )}

            {/* Top Stats Cards */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                <div className="bg-white p-6 rounded-xl shadow-sm border border-slate-200 flex items-center space-x-4">
                    <div className="bg-emerald-100 p-3 rounded-lg">
                        <CheckCircle className="h-6 w-6 text-emerald-600" />
                    </div>
                    <div>
                        <p className="text-sm font-medium text-slate-500">Total Collected</p>
                        <h3 className="text-2xl font-bold text-slate-900">{formatCurrency(totalCollected)}</h3>
                    </div>
                </div>
                
                <div className="bg-white p-6 rounded-xl shadow-sm border border-slate-200 flex items-center space-x-4">
                    <div className="bg-amber-100 p-3 rounded-lg">
                        <Clock className="h-6 w-6 text-amber-600" />
                    </div>
                    <div>
                        <p className="text-sm font-medium text-slate-500">Pending Receivables</p>
                        <h3 className="text-2xl font-bold text-slate-900">{formatCurrency(pendingAmount)}</h3>
                    </div>
                </div>

                <div className="bg-white p-6 rounded-xl shadow-sm border border-slate-200 flex items-center space-x-4">
                    <div className="bg-red-100 p-3 rounded-lg">
                        <AlertOctagon className="h-6 w-6 text-red-600" />
                    </div>
                    <div>
                        <p className="text-sm font-medium text-slate-500">Unpaid Fines</p>
                        <h3 className="text-2xl font-bold text-slate-900">{activeFines} Active</h3>
                    </div>
                </div>
            </div>

            {/* Main Content Card */}
            <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
                {/* Search & Filter Bar */}
                <div className="p-4 border-b border-slate-200 bg-slate-50/50 flex items-center justify-between">
                    <div className="relative w-full max-w-md">
                        <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                            <Search className="h-4 w-4 text-slate-400" />
                        </div>
                        <input
                            type="text"
                            placeholder="Search by member name or reference..."
                            value={searchTerm}
                            onChange={(e) => setSearchTerm(e.target.value)}
                            className="block w-full pl-10 pr-3 py-2 border border-slate-300 rounded-lg leading-5 bg-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-slate-500 sm:text-sm transition-colors"
                        />
                    </div>
                </div>

                {/* Data Table */}
                <div className="overflow-x-auto">
                    <table className="min-w-full divide-y divide-slate-200">
                        <thead className="bg-slate-50">
                            <tr>
                                <th scope="col" className="px-6 py-3 text-left text-xs font-semibold text-slate-500 uppercase tracking-wider">Member</th>
                                <th scope="col" className="px-6 py-3 text-left text-xs font-semibold text-slate-500 uppercase tracking-wider">Type & Ref</th>
                                <th scope="col" className="px-6 py-3 text-right text-xs font-semibold text-slate-500 uppercase tracking-wider">Amount</th>
                                <th scope="col" className="px-6 py-3 text-left text-xs font-semibold text-slate-500 uppercase tracking-wider">Due Date</th>
                                <th scope="col" className="px-6 py-3 text-left text-xs font-semibold text-slate-500 uppercase tracking-wider">Status</th>
                                <th scope="col" className="relative px-6 py-3"><span className="sr-only">Actions</span></th>
                            </tr>
                        </thead>
                        <tbody className="bg-white divide-y divide-slate-200">
                            {filteredContributions.length > 0 ? (
                                filteredContributions.map((contrib) => (
                                    <tr key={contrib.id} className="hover:bg-slate-50 transition-colors group">
                                        <td className="px-6 py-4 whitespace-nowrap">
                                            <div className="flex items-center">
                                                <div className="flex-shrink-0 h-8 w-8 bg-slate-100 text-slate-600 rounded-full flex items-center justify-center font-bold text-xs">
                                                    {contrib?.member?.first_name?.charAt(0) || '-'}
                                                </div>
                                                <div className="ml-3">
                                                    <div className="text-sm font-medium text-slate-900">
                                                        {contrib?.member?.first_name || 'Unknown'} {contrib?.member?.last_name || ''}
                                                    </div>
                                                    <div className="text-xs text-slate-500">ID: {contrib?.member?.membership_id || 'N/A'}</div>
                                                </div>
                                            </div>
                                        </td>
                                        <td className="px-6 py-4 whitespace-nowrap">
                                            <div className="mb-1">{getTypeBadge(contrib?.type)}</div>
                                            <div className="text-xs text-slate-500 font-mono">{contrib?.reference_id || 'N/A'}</div>
                                        </td>
                                        <td className="px-6 py-4 whitespace-nowrap text-right">
                                            <span className="text-sm font-bold text-slate-900">{formatCurrency(contrib?.amount)}</span>
                                        </td>
                                        <td className="px-6 py-4 whitespace-nowrap text-sm text-slate-500">
                                            {contrib?.due_date ? format(new Date(contrib.due_date), 'MMM dd, yyyy') : 'N/A'}
                                        </td>
                                        <td className="px-6 py-4 whitespace-nowrap">
                                            {getStatusBadge(contrib?.status, contrib?.due_date)}
                                        </td>
                                        <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                                            <div className="flex items-center justify-end space-x-2 opacity-0 group-hover:opacity-100 transition-opacity">
                                                {contrib?.status === 'PENDING' && isManager && (
                                                    <button title="Record Payment" className="text-emerald-600 hover:text-emerald-900 p-1 bg-emerald-50 rounded border border-emerald-100 transition-colors">
                                                        <CheckCircle className="h-4 w-4" />
                                                    </button>
                                                )}
                                                <button title="View Details" className="text-blue-600 hover:text-blue-900 p-1 bg-blue-50 rounded border border-blue-100 transition-colors">
                                                    <FileText className="h-4 w-4" />
                                                </button>
                                            </div>
                                        </td>
                                    </tr>
                                ))
                            ) : (
                                <tr>
                                    <td colSpan="6" className="px-6 py-12 text-center text-slate-500">
                                        <div className="flex flex-col items-center justify-center">
                                            <Receipt className="h-10 w-10 text-slate-300 mb-3" />
                                            <p className="text-base font-medium text-slate-900">No records found</p>
                                            <p className="text-sm mt-1">Assessments, dues, and fines will appear here.</p>
                                        </div>
                                    </td>
                                </tr>
                            )}
                        </tbody>
                    </table>
                </div>
            </div>

            {/* Success Toast */}
            {successMessage && (
                <div className="fixed bottom-4 right-4 bg-emerald-50 border-l-4 border-emerald-500 p-4 rounded shadow-lg animate-in fade-in slide-in-from-bottom-5 z-50">
                    <p className="text-sm text-emerald-700 font-medium">{successMessage}</p>
                </div>
            )}

            {/* New Assessment Modal */}
            <NewAssessmentModal 
                isOpen={isModalOpen}
                onClose={() => setIsModalOpen(false)}
                onSuccess={(msg) => {
                    setIsModalOpen(false);
                    setSuccessMessage(msg);
                    fetchContributions(); // Auto-refresh the table
                    setTimeout(() => setSuccessMessage(''), 5000);
                }}
            />
        </div>
    );
};

export default Contributions;