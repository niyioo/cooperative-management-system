import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Check, Handshake, X } from 'lucide-react';
import { memberApi } from '../../api/member';
import { Alert, ErrorAlert } from '../../components/ui/Alert';
import { StatusBadge } from '../../components/ui/Badge';
import Button from '../../components/ui/Button';
import { Card, CardBody, CardHeader } from '../../components/ui/Card';
import EmptyState from '../../components/ui/EmptyState';
import { TextAreaField } from '../../components/ui/Field';
import Modal from '../../components/ui/Modal';
import PageHeader from '../../components/ui/PageHeader';
import QueryState from '../../components/ui/QueryState';
import { Money, Table, Td, Th } from '../../components/ui/Table';
import { formatDateTime, formatNaira } from '../../lib/format';

function RequestCard({ request, onDone }) {
  const [declining, setDeclining] = useState(false);
  const [reason, setReason] = useState('');
  const accept = useMutation({ mutationFn: () => memberApi.acceptGuarantee(request.id), onSuccess: onDone });
  const decline = useMutation({
    mutationFn: () => memberApi.declineGuarantee(request.id, reason.trim()),
    onSuccess: () => { setDeclining(false); onDone(); },
  });
  return (
    <Card>
      <CardBody className="space-y-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <p className="text-lg font-semibold text-slate-900">{request.applicant.full_name}</p>
            <p className="text-sm text-slate-500">{request.applicant.membership_number} · application {request.application_reference}</p>
          </div>
          <p className="text-right">
            <span className="block text-xs text-slate-500">Your guarantee</span>
            <span className="tabular text-xl font-bold text-brand-800">{formatNaira(request.amount_guaranteed)}</span>
          </p>
        </div>
        <dl className="grid gap-3 text-sm sm:grid-cols-3">
          <div><dt className="text-xs text-slate-500">Loan</dt><dd className="font-medium">{request.product_name}</dd></div>
          <div><dt className="text-xs text-slate-500">Amount requested</dt><dd className="font-medium">{formatNaira(request.amount_requested)} over {request.term_months} months</dd></div>
          <div><dt className="text-xs text-slate-500">Asked</dt><dd className="font-medium">{formatDateTime(request.requested_at)}</dd></div>
          <div className="sm:col-span-3"><dt className="text-xs text-slate-500">Purpose</dt><dd>{request.purpose}</dd></div>
        </dl>
        <Alert tone="info">
          By accepting, you agree to stand behind this loan for {formatNaira(request.amount_guaranteed)} if {request.applicant.full_name.split(' ')[0]} does not repay it.
        </Alert>
        <ErrorAlert error={accept.error} />
        <div className="flex flex-wrap justify-end gap-2">
          <Button variant="secondary" icon={X} onClick={() => { decline.reset(); setDeclining(true); }}>Decline</Button>
          <Button icon={Check} loading={accept.isPending} onClick={() => accept.mutate()}>Accept and guarantee</Button>
        </div>
      </CardBody>
      <Modal open={declining} onClose={() => setDeclining(false)} title="Decline this request?"
        footer={
          <>
            <Button variant="secondary" onClick={() => setDeclining(false)}>Back</Button>
            <Button variant="danger" loading={decline.isPending} onClick={() => decline.mutate()}>Decline</Button>
          </>
        }>
        <div className="space-y-3">
          <p>{request.applicant.full_name} will be told, so they can choose another guarantor.</p>
          <TextAreaField label="Reason (optional, shown to them)" rows={2} maxLength={500} value={reason} onChange={(e) => setReason(e.target.value)} />
          <ErrorAlert error={decline.error} />
        </div>
      </Modal>
    </Card>
  );
}

export default function Guarantees() {
  const queryClient = useQueryClient();
  const requests = useQuery({ queryKey: ['me', 'guarantee-requests'], queryFn: () => memberApi.guaranteeRequests({ page_size: 100 }) });
  const refresh = () => queryClient.invalidateQueries({ queryKey: ['me'] });

  return (
    <div className="space-y-6">
      <PageHeader title="Guarantees" description="Requests from fellow members to stand as guarantor for their loans." />
      <QueryState query={requests}>
        {(data) => {
          const waiting = data.results.filter((r) => r.can_respond);
          const history = data.results.filter((r) => !r.can_respond);
          return (
            <>
              {waiting.length ? (
                <section className="space-y-4" aria-label="Waiting for your answer">
                  <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-500">Waiting for your answer</h2>
                  {waiting.map((r) => <RequestCard key={r.id} request={r} onDone={refresh} />)}
                </section>
              ) : (
                <Card><EmptyState icon={Handshake} title="No requests waiting">When a member names you as their guarantor, you will see it here and receive an e-mail.</EmptyState></Card>
              )}
              {history.length > 0 && (
                <Card>
                  <CardHeader title="Your guarantees" />
                  <Table caption="Your guarantees">
                    <thead><tr><Th>Member</Th><Th>Application</Th><Th align="right">Guarantee</Th><Th>Your answer</Th><Th>Application status</Th></tr></thead>
                    <tbody className="divide-y divide-slate-100">
                      {history.map((r) => (
                        <tr key={r.id}>
                          <Td><p className="font-medium text-slate-900">{r.applicant.full_name}</p><p className="text-xs text-slate-500">{r.applicant.membership_number}</p></Td>
                          <Td><p>{r.application_reference}</p><p className="text-xs text-slate-500">{r.product_name}</p></Td>
                          <Td align="right"><Money value={r.amount_guaranteed} /></Td>
                          <Td><StatusBadge status={r.status} label={r.status_label} /></Td>
                          <Td><StatusBadge status={r.application_status} label={r.application_status_label} /></Td>
                        </tr>
                      ))}
                    </tbody>
                  </Table>
                </Card>
              )}
            </>
          );
        }}
      </QueryState>
    </div>
  );
}
