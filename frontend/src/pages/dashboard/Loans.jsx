import React, { useState, useEffect } from 'react';
import axiosInstance from '../../api/axios';
import { useAuth } from '../../hooks/useAuth';
import { 
    Search, Plus, FileText, CheckCircle, XCircle, AlertCircle, Loader2, 
    Landmark, Activity, MoreVertical, Banknote, Trash2, CreditCard 
} from 'lucide-react';
import LoanApplicationModal from '../../components/LoanApplicationModal';
import LoanDetailsModal from '../../components/LoanDetailsModal';
import RecordRepaymentModal from '../../components/RecordRepaymentModal';

const Loans = () => {
    const { isManager } = useAuth();
    const [loans, setLoans] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');
    const [searchTerm, setSearchTerm] = useState('');
    
    // Modal & Dropdown States
    const [isModalOpen, setIsModalOpen] = useState(false);
    const [isDetailsModalOpen, setIsDetailsModalOpen] = useState(false);
    const [isRepayModalOpen, setIsRepayModalOpen] = useState(false);
    const [activeMenu, setActiveMenu] = useState(null); // Tracks which dropdown is currently open
    const [selectedLoan, setSelectedLoan] = useState(null);
    const [successMessage, setSuccessMessage] = useState('');

    const fetchLoans = async () => {
        try {
            setError('');
            const response = await axiosInstance.get('/loans/applications/');
            // Handle both paginated and flat array responses
            const rawData = response.data?.results || response.data;
            
            if (Array.isArray(rawData)) {
                setLoans(rawData);
            } else {
                setLoans([]);
            }
        } catch (err) {
            console.error("Failed to fetch loans:", err);
            setError('Failed to load loan records. Please try again later.');
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchLoans();
    }, []);

    // Handles Approve, Reject, and Disbursement
    const handleLoanAction = async (id, action) => {
        try {
            await axiosInstance.post(`/loans/applications/${id}/${action}/`);
            setSuccessMessage(`Loan application successfully ${action}ed!`);
            fetchLoans(); 
            setTimeout(() => setSuccessMessage(''), 3000);
        } catch (err) {
            setError(`Failed to ${action} loan. Please try again.`);
            setTimeout(() => setError(''), 3000);
        }
    };

    // Helper to handle actions triggered from the dot-dot-dot dropdown
    const handleMenuAction = (loan, actionType) => {
        setActiveMenu(null); // Close the menu immediately
        setSelectedLoan(loan);
        if (actionType === 'details') {
            setIsDetailsModalOpen(true);
        } else if (actionType === 'repay') {
            setIsRepayModalOpen(true);
        }
    };

    // Stats Calculations
    const activeLoans = loans.filter(loan => loan?.status === 'ACTIVE');
    const totalOutstanding = activeLoans.reduce((sum, loan) => sum + parseFloat(loan?.balance || loan?.balance_remaining || 0), 0);
    const pendingApplications = loans.filter(loan => loan?.status === 'PENDING').length;

    // Search Logic
    const filteredLoans = loans.filter(loan => {
        const fullName = `${loan?.member?.first_name || ''} ${loan?.member?.last_name || ''}`.toLowerCase();
        const loanId = loan?.loan_id?.toLowerCase() || '';
        const search = searchTerm.toLowerCase();
        return fullName.includes(search) || loanId.includes(search);
    });

    const formatCurrency = (amount) => {
        const validAmount = isNaN(parseFloat(amount)) ? 0 : parseFloat(amount);
        return new Intl.NumberFormat('en-NG', { 
            style: 'currency', 
            currency: 'NGN',
            minimumFractionDigits: 0 
        }).format(validAmount);
    };

    const getStatusBadge = (status) => {
        const base = "px-2.5 py-0.5 rounded-full text-[10px] font-black uppercase tracking-widest border";
        switch (status) {
            case 'PENDING':
                return <span className={`${base} bg-amber-50 text-amber-700 border-amber-200`}>Pending</span>;
            case 'APPROVED':
                return <span className={`${base} bg-blue-50 text-blue-700 border-blue-200`}>Approved</span>;
            case 'ACTIVE':
                return <span className={`${base} bg-emerald-50 text-emerald-700 border-emerald-200`}>Active</span>;
            case 'COMPLETED':
                return <span className={`${base} bg-slate-100 text-slate-700 border-slate-200`}>Completed</span>;
            case 'REJECTED':
                return <span className={`${base} bg-red-50 text-red-700 border-red-200`}>Rejected</span>;
            default:
                return <span className={`${base} bg-slate-50 text-slate-700 border-slate-200`}>{status}</span>;
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
        <div className="space-y-6 animate-in fade-in duration-500">
            {/* Header Section */}
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                <div>
                    <h1 className="text-2xl font-black text-slate-900 tracking-tight">Loan Management</h1>
                    <p className="text-sm text-slate-500 mt-1">Track applications, disbursements, and repayments.</p>
                </div>
                
                <button 
                    onClick={() => setIsModalOpen(true)}
                    className="inline-flex items-center justify-center px-5 py-2.5 bg-blue-600 text-white text-sm font-black rounded-xl hover:bg-blue-700 transition-all shadow-lg active:scale-95"
                >
                    <Plus className="h-4 w-4 mr-2" />
                    New Application
                </button>
            </div>

            {/* Error Message */}
            {error && (
                <div className="bg-red-50 border-l-4 border-red-500 p-4 rounded flex items-center">
                    <AlertCircle className="h-5 w-5 text-red-500 mr-2" />
                    <p className="text-sm text-red-700 font-bold uppercase tracking-tight">{error}</p>
                </div>
            )}

            {/* Stats Overview */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                <div className="bg-white p-6 rounded-2xl shadow-sm border border-slate-100 transition-transform hover:scale-[1.02]">
                    <div className="flex items-center justify-between mb-4">
                        <div className="bg-blue-100 p-2 rounded-lg text-blue-600">
                            <Landmark className="h-5 w-5" />
                        </div>
                        <span className="text-[10px] font-black text-slate-400 uppercase tracking-widest">Global Balance</span>
                    </div>
                    <p className="text-xs font-bold text-slate-400 uppercase tracking-widest mb-1">Total Outstanding</p>
                    <h3 className="text-2xl font-bold text-slate-900">{formatCurrency(totalOutstanding)}</h3>
                </div>
                
                <div className="bg-white p-6 rounded-2xl shadow-sm border border-slate-100 transition-transform hover:scale-[1.02]">
                    <div className="flex items-center justify-between mb-4">
                        <div className="bg-emerald-100 p-2 rounded-lg text-emerald-600">
                            <Activity className="h-5 w-5" />
                        </div>
                        <span className="text-[10px] font-black text-slate-400 uppercase tracking-widest">Active Contracts</span>
                    </div>
                    <p className="text-xs font-bold text-slate-400 uppercase tracking-widest mb-1">Running Loans</p>
                    <h3 className="text-2xl font-bold text-slate-900">{activeLoans.length}</h3>
                </div>

                <div className="bg-white p-6 rounded-2xl shadow-sm border border-slate-100 transition-transform hover:scale-[1.02]">
                    <div className="flex items-center justify-between mb-4">
                        <div className="bg-amber-100 p-2 rounded-lg text-amber-600">
                            <FileText className="h-5 w-5" />
                        </div>
                        <span className="text-[10px] font-black text-slate-400 uppercase tracking-widest">Awaiting Review</span>
                    </div>
                    <p className="text-xs font-bold text-slate-400 uppercase tracking-widest mb-1">Pending Requests</p>
                    <h3 className="text-2xl font-bold text-slate-900">{pendingApplications}</h3>
                </div>
            </div>

            {/* Main Table Card */}
            <div className="bg-white rounded-3xl shadow-sm border border-slate-100 overflow-hidden">
                <div className="p-4 border-b border-slate-50 bg-slate-50/50">
                    <div className="relative max-w-md group">
                        <Search className="absolute left-3 top-2.5 h-4 w-4 text-slate-400 group-focus-within:text-blue-500 transition-colors" />
                        <input
                            type="text"
                            placeholder="Search applicant or loan ID..."
                            value={searchTerm}
                            onChange={(e) => setSearchTerm(e.target.value)}
                            className="block w-full pl-10 pr-4 py-2 border border-slate-200 rounded-xl bg-white focus:ring-2 focus:ring-blue-500/20 text-sm outline-none transition-all"
                        />
                    </div>
                </div>

                <div className="overflow-x-auto">
                    <table className="min-w-full divide-y divide-slate-100">
                        <thead className="bg-slate-50/50 text-slate-400 text-[10px] font-black uppercase tracking-widest">
                            <tr>
                                <th className="px-6 py-4 text-left">Applicant</th>
                                <th className="px-6 py-4 text-left">Reference</th>
                                <th className="px-6 py-4 text-right">Principal</th>
                                <th className="px-6 py-4 text-right">Remaining</th>
                                <th className="px-6 py-4 text-left">Status</th>
                                <th className="relative px-6 py-4"><span className="sr-only">Actions</span></th>
                            </tr>
                        </thead>
                        <tbody className="bg-white divide-y divide-slate-50">
                            {filteredLoans.length > 0 ? (
                                filteredLoans.map((loan) => (
                                    <tr key={loan.id} className="hover:bg-slate-50/80 transition-colors group">
                                        <td className="px-6 py-4 whitespace-nowrap">
                                            <div className="flex items-center">
                                                <div className="h-9 w-9 bg-slate-100 rounded-xl flex items-center justify-center text-slate-700 font-black text-xs border border-white shadow-sm">
                                                    {loan.member?.first_name?.[0]}{loan.member?.last_name?.[0]}
                                                </div>
                                                <div className="ml-3">
                                                    <div className="text-sm font-bold text-slate-900">
                                                        {loan.member?.first_name} {loan.member?.last_name}
                                                    </div>
                                                    <div className="text-[10px] text-blue-500 font-mono font-bold tracking-tight uppercase">
                                                        {loan.member?.membership_id}
                                                    </div>
                                                </div>
                                            </div>
                                        </td>
                                        <td className="px-6 py-4 whitespace-nowrap">
                                            <div className="text-sm font-mono font-bold text-slate-600">{loan.loan_id}</div>
                                            <div className="text-[10px] font-bold text-slate-400 uppercase tracking-tighter">{loan.duration_months} Months</div>
                                        </td>
                                        <td className="px-6 py-4 whitespace-nowrap text-right font-bold text-slate-500">
                                            {formatCurrency(loan.principal_amount)}
                                        </td>
                                        <td className="px-6 py-4 whitespace-nowrap text-right font-black text-slate-900">
                                            {formatCurrency(loan.balance || loan.balance_remaining)}
                                        </td>
                                        <td className="px-6 py-4 whitespace-nowrap">
                                            {getStatusBadge(loan.status)}
                                        </td>
                                        <td className="px-6 py-4 whitespace-nowrap text-right relative">
                                            <div className="flex items-center justify-end space-x-2">
                                                {/* Disburse for Approved */}
                                                {loan.status === 'APPROVED' && isManager && (
                                                    <button 
                                                        onClick={(e) => { e.stopPropagation(); handleLoanAction(loan.id, 'disburse'); }}
                                                        className="p-1.5 text-blue-600 bg-blue-50 rounded-lg hover:bg-blue-100 transition-colors shadow-sm"
                                                        title="Disburse Funds"
                                                    >
                                                        <Banknote className="h-4 w-4" />
                                                    </button>
                                                )}

                                                {/* Approval for Pending */}
                                                {loan.status === 'PENDING' && isManager && (
                                                    <>
                                                        <button 
                                                            onClick={(e) => { e.stopPropagation(); handleLoanAction(loan.id, 'approve'); }}
                                                            className="p-1.5 text-emerald-600 bg-emerald-50 rounded-lg hover:bg-emerald-100 transition-colors shadow-sm"
                                                            title="Approve Loan"
                                                        >
                                                            <CheckCircle className="h-4 w-4" />
                                                        </button>
                                                        <button 
                                                            onClick={(e) => { e.stopPropagation(); handleLoanAction(loan.id, 'reject'); }}
                                                            className="p-1.5 text-red-600 bg-red-50 rounded-lg hover:bg-red-100 transition-colors shadow-sm"
                                                            title="Reject Loan"
                                                        >
                                                            <XCircle className="h-4 w-4" />
                                                        </button>
                                                    </>
                                                )}

                                                {/* Statement View */}
                                                <button 
                                                    onClick={(e) => { 
                                                        e.stopPropagation(); 
                                                        setSelectedLoan(loan); 
                                                        setIsDetailsModalOpen(true); 
                                                    }}
                                                    className="p-1.5 text-blue-600 bg-blue-50 rounded-lg hover:bg-blue-100 transition-colors shadow-sm" 
                                                    title="View Statement"
                                                >
                                                    <FileText className="h-4 w-4" />
                                                </button>

                                                {/* Functional Dropdown Menu (The dot-dot-dot) */}
                                                <div className="relative">
                                                    <button 
                                                        onClick={(e) => {
                                                            e.stopPropagation();
                                                            setActiveMenu(activeMenu === loan.id ? null : loan.id);
                                                        }}
                                                        className={`p-1.5 rounded-lg transition-colors ${
                                                            activeMenu === loan.id ? 'bg-slate-200 text-slate-900' : 'text-slate-400 hover:bg-slate-100'
                                                        }`}
                                                    >
                                                        <MoreVertical className="h-4 w-4" />
                                                    </button>

                                                    {activeMenu === loan.id && (
                                                        <>
                                                            {/* Backdrop to close menu */}
                                                            <div className="fixed inset-0 z-10" onClick={() => setActiveMenu(null)}></div>
                                                            
                                                            <div className="absolute right-0 mt-2 w-48 bg-white rounded-2xl shadow-2xl border border-slate-100 py-2 z-20 animate-in fade-in zoom-in-95 duration-100">
                                                                <button 
                                                                    onClick={() => handleMenuAction(loan, 'details')}
                                                                    className="w-full px-4 py-2 text-left text-xs font-bold text-slate-700 hover:bg-slate-50 flex items-center"
                                                                >
                                                                    <FileText className="h-3.5 w-3.5 mr-2 text-blue-500" /> View Statement
                                                                </button>
                                                                
                                                                {loan.status === 'ACTIVE' && (
                                                                    <button 
                                                                        onClick={() => handleMenuAction(loan, 'repay')}
                                                                        className="w-full px-4 py-2 text-left text-xs font-bold text-slate-700 hover:bg-slate-50 flex items-center"
                                                                    >
                                                                        <CreditCard className="h-3.5 w-3.5 mr-2 text-emerald-500" /> Record Repayment
                                                                    </button>
                                                                )}

                                                                {isManager && (
                                                                    <button className="w-full px-4 py-2 text-left text-xs font-bold text-red-600 hover:bg-red-50 flex items-center border-t border-slate-50 mt-1">
                                                                        <Trash2 className="h-3.5 w-3.5 mr-2" /> Delete Record
                                                                    </button>
                                                                )}
                                                            </div>
                                                        </>
                                                    )}
                                                </div>
                                            </div>
                                        </td>
                                    </tr>
                                ))
                            ) : (
                                <tr>
                                    <td colSpan="6" className="px-6 py-16 text-center text-slate-400">
                                        <div className="flex flex-col items-center justify-center">
                                            <Landmark className="h-10 w-10 text-slate-100 mb-3" />
                                            <p className="text-sm font-bold text-slate-500 uppercase tracking-widest">No loan records found</p>
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
                <div className="fixed bottom-6 right-6 bg-slate-900 text-white px-6 py-4 rounded-2xl shadow-2xl animate-in slide-in-from-bottom-5 z-50 flex items-center font-black text-[11px] uppercase tracking-widest">
                    <div className="bg-emerald-500 p-1 rounded-full mr-3">
                        <CheckCircle className="h-4 w-4 text-white" />
                    </div>
                    {successMessage}
                </div>
            )}

            {/* Modals */}
            <LoanApplicationModal 
                isOpen={isModalOpen}
                onClose={() => setIsModalOpen(false)}
                onSuccess={(msg) => {
                    setIsModalOpen(false);
                    setSuccessMessage(msg);
                    fetchLoans(); 
                }}
            />

            <LoanDetailsModal 
                isOpen={isDetailsModalOpen}
                onClose={() => setIsDetailsModalOpen(false)}
                loan={selectedLoan}
            />

            <RecordRepaymentModal 
                isOpen={isRepayModalOpen}
                onClose={() => setIsRepayModalOpen(false)}
                loan={selectedLoan}
                onSuccess={(msg) => {
                    setSuccessMessage(msg);
                    fetchLoans(); 
                }}
            />
        </div>
    );
};

export default Loans;