import React, { useCallback, useEffect, useState } from 'react';
import axiosInstance from '../../api/axios';
import { CheckCircle, ClipboardCheck, Loader2, XCircle } from 'lucide-react';
import { formatDistanceToNow } from 'date-fns';

const formatCurrency = (value) =>
    new Intl.NumberFormat('en-NG', { style: 'currency', currency: 'NGN', minimumFractionDigits: 2 }).format(Number(value || 0));

const errorText = (err, fallback) => {
    const data = err.response?.data;
    if (!data) return fallback;
    if (typeof data.detail === 'string') return data.detail;
    const first = Object.values(data)[0];
    return Array.isArray(first) ? first[0] : (typeof first === 'string' ? first : fallback);
};

// Pending member requests from both queues, so finance staff work through one list.
const QUEUES = [
    {
        key: 'savings', title: 'Savings requests', url: '/savings/transactions/',
        describe: (t) => `${t.transaction_type === 'WITHDRAWAL' ? 'Withdrawal' : 'Deposit'} of ${formatCurrency(t.amount)}`,
        needsReason: true,
    },
    {
        key: 'shares', title: 'Share purchases', url: '/shares/transactions/',
        describe: (t) => `${t.number_of_shares} share(s) at ${formatCurrency(t.price_per_share)} = ${formatCurrency(t.total_amount)}`,
        needsReason: false,
    },
];

const Approvals = () => {
    const [items, setItems] = useState({ savings: [], shares: [] });
    const [loading, setLoading] = useState(true);
    const [busy, setBusy] = useState(null);
    const [message, setMessage] = useState(null);

    const load = useCallback(async () => {
        try {
            const results = await Promise.all(
                QUEUES.map((q) => axiosInstance.get(q.url, { params: { status: 'PENDING', page_size: 100 } }))
            );
            setItems(Object.fromEntries(QUEUES.map((q, i) => [q.key, results[i].data?.results || results[i].data || []])));
        } catch (err) {
            setMessage({ type: 'error', text: errorText(err, 'Could not load pending requests.') });
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => { load(); }, [load]);

    const decide = async (queue, txn, verb) => {
        let body = {};
        if (verb === 'reject' && queue.needsReason) {
            const reason = window.prompt('Why is this request being declined? The member will see this reason.');
            if (reason === null) return;
            body = { reason };
        }
        setBusy(`${txn.id}:${verb}`);
        setMessage(null);
        try {
            await axiosInstance.post(`${queue.url}${txn.id}/${verb}/`, body);
            setMessage({ type: 'success', text: `${queue.describe(txn)} for ${txn.member_name} ${verb === 'approve' ? 'approved' : 'declined'}.` });
            await load();
        } catch (err) {
            setMessage({ type: 'error', text: errorText(err, `Could not ${verb} the request.`) });
        } finally {
            setBusy(null);
        }
    };

    if (loading) {
        return <div className="flex h-full items-center justify-center"><Loader2 className="animate-spin h-8 w-8 text-blue-500" /></div>;
    }

    const total = items.savings.length + items.shares.length;

    return (
        <div className="space-y-6 max-w-5xl mx-auto">
            <div>
                <h1 className="text-2xl font-bold text-slate-900 flex items-center">
                    Approvals
                    {total > 0 && (
                        <span className="ml-3 px-2.5 py-0.5 rounded-full text-xs font-medium bg-amber-100 text-amber-800">{total} pending</span>
                    )}
                </h1>
                <p className="text-sm text-slate-500 mt-1">
                    Member requests waiting for a decision. Approving moves the money; nothing changes until you do.
                </p>
            </div>

            {message && (
                <div role="status" className={`rounded-lg border px-4 py-3 text-sm ${message.type === 'success' ? 'border-emerald-200 bg-emerald-50 text-emerald-800' : 'border-red-200 bg-red-50 text-red-800'}`}>
                    {message.text}
                </div>
            )}

            {QUEUES.map((queue) => (
                <section key={queue.key} className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
                    <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between">
                        <h2 className="text-base font-semibold text-slate-900">{queue.title}</h2>
                        <span className="text-xs text-slate-500">{items[queue.key].length} pending</span>
                    </div>
                    {items[queue.key].length === 0 ? (
                        <div className="px-6 py-10 text-center text-sm text-slate-500">
                            <ClipboardCheck className="h-8 w-8 mx-auto mb-2 text-slate-300" />
                            Nothing waiting.
                        </div>
                    ) : (
                        <ul className="divide-y divide-slate-100">
                            {items[queue.key].map((txn) => (
                                <li key={txn.id} className="px-6 py-4 flex flex-col sm:flex-row sm:items-center gap-3">
                                    <div className="flex-1 min-w-0">
                                        <p className="text-sm font-medium text-slate-900">{queue.describe(txn)}</p>
                                        <p className="text-sm text-slate-500">
                                            {txn.member_name} · {txn.reference} · requested {formatDistanceToNow(new Date(txn.created_at), { addSuffix: true })}
                                        </p>
                                        {txn.description && <p className="text-xs text-slate-400 mt-1">{txn.description}</p>}
                                    </div>
                                    <div className="flex gap-2">
                                        <button
                                            onClick={() => decide(queue, txn, 'approve')}
                                            disabled={busy !== null}
                                            className="inline-flex items-center px-3 py-2 bg-emerald-600 text-white text-sm font-medium rounded-lg hover:bg-emerald-700 disabled:opacity-50"
                                        >
                                            {busy === `${txn.id}:approve` ? <Loader2 className="h-4 w-4 mr-1.5 animate-spin" /> : <CheckCircle className="h-4 w-4 mr-1.5" />}
                                            Approve
                                        </button>
                                        <button
                                            onClick={() => decide(queue, txn, 'reject')}
                                            disabled={busy !== null}
                                            className="inline-flex items-center px-3 py-2 bg-white border border-slate-300 text-slate-700 text-sm font-medium rounded-lg hover:bg-slate-50 disabled:opacity-50"
                                        >
                                            <XCircle className="h-4 w-4 mr-1.5 text-red-500" />
                                            Decline
                                        </button>
                                    </div>
                                </li>
                            ))}
                        </ul>
                    )}
                </section>
            ))}
        </div>
    );
};

export default Approvals;
