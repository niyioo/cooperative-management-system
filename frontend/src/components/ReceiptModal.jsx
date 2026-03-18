import React, { useRef } from 'react';
import { X, Printer, Download, CheckCircle2 } from 'lucide-react';
import { format } from 'date-fns';

const ReceiptModal = ({ isOpen, onClose, transaction }) => {
    const printRef = useRef();

    if (!isOpen || !transaction) return null;

    const handlePrint = () => {
        window.print();
    };

    const formatCurrency = (amount) => {
        return new Intl.NumberFormat('en-NG', { style: 'currency', currency: 'NGN' }).format(amount);
    };

    return (
        <div className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-sm print:bg-white print:p-0">
            <div className="bg-white rounded-2xl shadow-2xl w-full max-w-lg overflow-hidden animate-in zoom-in duration-200 print:shadow-none print:w-full print:max-w-none">
                
                {/* Modal Header - Hidden on Print */}
                <div className="px-6 py-4 border-b flex items-center justify-between bg-slate-50 print:hidden">
                    <h2 className="text-lg font-bold text-slate-800">Transaction Receipt</h2>
                    <div className="flex items-center space-x-2">
                        <button onClick={handlePrint} className="p-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors">
                            <Printer className="h-4 w-4" />
                        </button>
                        <button onClick={onClose} className="p-2 hover:bg-slate-200 rounded-full transition-colors">
                            <X className="h-5 w-5 text-slate-400" />
                        </button>
                    </div>
                </div>

                {/* The Actual Receipt Content */}
                <div ref={printRef} className="p-10 space-y-8 bg-white text-slate-900">
                    {/* Brand Header */}
                    <div className="text-center space-y-2 border-b-2 border-dashed border-slate-200 pb-6">
                        <div className="inline-flex items-center justify-center w-16 h-16 bg-slate-900 rounded-2xl text-white font-black text-2xl mb-2">
                            B
                        </div>
                        <h1 className="text-xl font-black uppercase tracking-tighter">BravEdge Solutions Cooperative</h1>
                        <p className="text-[10px] text-slate-500 font-medium">123 Coop Plaza, Akure, Ondo State • +234 800 000 0000</p>
                    </div>

                    {/* Transaction Status Badge */}
                    <div className="flex flex-col items-center justify-center space-y-1">
                        <CheckCircle2 className="h-8 w-8 text-emerald-500" />
                        <span className="text-[10px] font-bold text-emerald-600 uppercase tracking-widest">Transaction Successful</span>
                    </div>

                    {/* Main Receipt Data */}
                    <div className="space-y-4">
                        <div className="flex justify-between items-end">
                            <div>
                                <p className="text-[10px] font-bold text-slate-400 uppercase">Payment Amount</p>
                                <h2 className="text-3xl font-black text-slate-900">
                                    {formatCurrency(transaction.amount)}
                                </h2>
                            </div>
                            <div className="text-right">
                                <p className="text-[10px] font-bold text-slate-400 uppercase">Date</p>
                                <p className="text-sm font-bold">{format(new Date(transaction.date), 'MMMM dd, yyyy')}</p>
                            </div>
                        </div>

                        <div className="grid grid-cols-2 gap-6 pt-4 border-t border-slate-100">
                            <div>
                                <p className="text-[10px] font-bold text-slate-400 uppercase mb-1">Transaction ID</p>
                                <p className="text-xs font-mono font-bold text-slate-700">{transaction.reference_id}</p>
                            </div>
                            <div>
                                <p className="text-[10px] font-bold text-slate-400 uppercase mb-1">Entry Type</p>
                                <p className={`text-xs font-bold ${transaction.type === 'INCOME' ? 'text-emerald-600' : 'text-red-600'}`}>
                                    {transaction.type}
                                </p>
                            </div>
                            <div>
                                <p className="text-[10px] font-bold text-slate-400 uppercase mb-1">Category</p>
                                <p className="text-xs font-bold text-slate-700">{transaction.category || 'General'}</p>
                            </div>
                            <div>
                                <p className="text-[10px] font-bold text-slate-400 uppercase mb-1">Recorded By</p>
                                <p className="text-xs font-bold text-slate-700">System Admin</p>
                            </div>
                        </div>

                        <div className="pt-4 border-t border-slate-100">
                            <p className="text-[10px] font-bold text-slate-400 uppercase mb-1">Description</p>
                            <p className="text-sm text-slate-600 italic leading-relaxed">{transaction.description}</p>
                        </div>
                    </div>

                    {/* Footer / Signature Section */}
                    <div className="pt-12 flex justify-between items-center opacity-70">
                        <div className="space-y-1">
                            <div className="w-32 border-b border-slate-400"></div>
                            <p className="text-[9px] font-bold text-slate-400 uppercase text-center">Authorized Signatory</p>
                        </div>
                        <div className="text-right">
                            <p className="text-[9px] text-slate-400">This is a computer-generated receipt.</p>
                            <p className="text-[9px] font-bold text-slate-900 italic">BravEdge Coop Management System</p>
                        </div>
                    </div>
                </div>

                {/* Print Hint - Hidden on Print */}
                <div className="bg-slate-50 px-6 py-3 text-center print:hidden border-t">
                    <p className="text-[10px] text-slate-400 italic">Press <b>Ctrl + P</b> to print or save as PDF.</p>
                </div>
            </div>

            {/* Print Logic Styles */}
            <style dangerouslySetInnerHTML={{ __html: `
                @media print {
                    body * { visibility: hidden; }
                    .print\\:block, .print\\:block * { visibility: visible; }
                    #receipt-wrapper, #receipt-wrapper * { visibility: visible; }
                    #receipt-wrapper { position: absolute; left: 0; top: 0; width: 100%; }
                }
            `}} />
        </div>
    );
};

export default ReceiptModal;