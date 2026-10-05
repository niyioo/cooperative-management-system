import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Link, useLocation, useParams } from 'react-router-dom';
import { ArrowLeft, Send, Trash2, X } from 'lucide-react';
import { memberApi } from '../../api/member';
import GuarantorFinder from '../../components/member/GuarantorFinder';
import { Alert, ErrorAlert } from '../../components/ui/Alert';
import { StatusBadge } from '../../components/ui/Badge';
import Button from '../../components/ui/Button';
import { Card, CardBody, CardHeader } from '../../components/ui/Card';
import { TextAreaField, TextField } from '../../components/ui/Field';
import Modal from '../../components/ui/Modal';
import QueryState from '../../components/ui/QueryState';
import { formatDate, formatDateTime, formatNaira } from '../../lib/format';

// The member-facing meaning of each status.
const EXPLANATIONS = {
  DRAFT: 'Not yet submitted. Review the details and submit when ready.',
  SUBMITTED: 'Received. A loan officer will review it shortly.',
  UNDER_REVIEW: 'The loan committee is reviewing your application.',
  RETURNED: 'The committee needs more information from you before it can continue.',
  APPROVED: 'Approved. The loan will be paid out soon.',
  REJECTED: 'Your application was not approved.',
  CANCELLED: 'You cancelled this application.',
  DISBURSED: 'The loan has been paid out.',
};

export default function ApplicationDetail() {
  const { id } = useParams();
  const location = useLocation();
  const queryClient = useQueryClient();
  const query = useQuery({ queryKey: ['me', 'application', id], queryFn: () => memberApi.application(id) });
  const refresh = () => queryClient.invalidateQueries({ queryKey: ['me'] });

  return (
    <QueryState query={query}>
      {(app) => (
        <div className="space-y-6">
          <div>
            <Link to="/member/loans" className="inline-flex items-center gap-1 text-sm font-medium text-brand-600 hover:underline">
              <ArrowLeft className="h-4 w-4" aria-hidden="true" /> My loans
            </Link>
            <div className="mt-2 flex flex-wrap items-center gap-3">
              <h1 className="text-2xl font-bold text-slate-900">{app.reference}</h1>
              <StatusBadge status={app.status} label={app.status_label} />
            </div>
            <p className="mt-1 text-sm text-slate-500">{EXPLANATIONS[app.status]}</p>
          </div>

          {location.state?.justSubmitted && app.status === 'SUBMITTED' && (
            <Alert tone="success" title="Application submitted">We will let you know when the committee decides.</Alert>
          )}
          {app.status === 'RETURNED' && app.info_request_message && (
            <Alert tone="warning" title="Information requested">{app.info_request_message}</Alert>
          )}
          {app.status === 'REJECTED' && app.decision_reason && <Alert tone="error" title="Reason">{app.decision_reason}</Alert>}
          {app.loan && (
            <Alert tone="success">
              Your loan is <Link to={`/member/loans/${app.loan.id}`} className="font-semibold underline">{app.loan.reference}</Link>.
            </Alert>
          )}

          <div className="grid gap-6 lg:grid-cols-3">
            <Card className="lg:col-span-2">
              <CardHeader title="Application" action={app.can_edit && <EditButton app={app} onSaved={refresh} />} />
              <CardBody>
                <dl className="grid gap-4 sm:grid-cols-2">
                  <Item label="Loan" value={app.product_name} />
                  <Item label="Amount requested" value={formatNaira(app.amount_requested)} />
                  <Item label="Repayment period" value={`${app.term_months} months`} />
                  <Item label="Submitted" value={formatDateTime(app.submitted_at)} />
                  {app.approved_amount && <Item label="Approved amount" value={formatNaira(app.approved_amount)} />}
                  {app.approved_term_months && <Item label="Approved period" value={`${app.approved_term_months} months`} />}
                  <div className="sm:col-span-2"><Item label="Purpose" value={app.purpose} /></div>
                  <div className="sm:col-span-2">
                    <Item label="Documents" value={app.documents.length ? app.documents.map((d) => d.title).join(', ') : 'None attached'} />
                  </div>
                </dl>
              </CardBody>
            </Card>

            <Card>
              <CardHeader title={app.approved_amount ? 'Approved terms' : 'Estimated repayments'} />
              <CardBody className="space-y-3 text-sm">
                <Row label="Monthly repayment" value={formatNaira(app.quote.monthly_payment)} strong />
                <Row label="Total interest" value={formatNaira(app.quote.total_interest)} />
                <Row label="Total to repay" value={formatNaira(app.quote.total_payable)} />
                <p className="text-xs text-slate-500">Final figures are set when the loan is paid out. Repayments are due at the end of each month, from {formatDate(app.quote.first_due_date)} if paid out today.</p>
              </CardBody>
            </Card>
          </div>

          <GuarantorsCard app={app} onChanged={refresh} />

          <div className="flex flex-wrap justify-end gap-2">
            {app.can_cancel && <CancelButton app={app} onDone={refresh} />}
            {app.can_edit && <SubmitButton app={app} onDone={refresh} />}
          </div>
        </div>
      )}
    </QueryState>
  );
}

const GUARANTOR_HINT = {
  PENDING: 'Waiting for their answer',
  ACCEPTED: 'Agreed to guarantee',
  DECLINED: 'Declined',
};

function GuarantorsCard({ app, onChanged }) {
  const remove = useMutation({ mutationFn: (id) => memberApi.removeGuarantor(app.id, id), onSuccess: onChanged });
  const standing = app.guarantors.filter((g) => g.status !== 'DECLINED').length;
  const short = app.guarantors_required - standing;
  return (
    <Card>
      <CardHeader title="Guarantors"
        description={`This loan needs ${app.guarantors_required} guarantor${app.guarantors_required > 1 ? 's' : ''}. They are asked by e-mail and in the portal when you submit.`} />
      {app.guarantors.length > 0 && (
        <ul className="divide-y divide-slate-100">
          {app.guarantors.map((g) => (
            <li key={g.id} className="flex flex-wrap items-center justify-between gap-3 px-5 py-3 text-sm">
              <div>
                <p><span className="font-semibold text-slate-900">{g.full_name}</span> <span className="text-slate-500">{g.membership_number}</span></p>
                <p className="text-xs text-slate-500">
                  {g.requested_at ? `${GUARANTOR_HINT[g.status]} · guarantees ${formatNaira(g.amount_guaranteed)}` : 'Will be asked when you submit'}
                  {g.decline_reason ? ` · “${g.decline_reason}”` : ''}
                </p>
              </div>
              <div className="flex items-center gap-2">
                {g.requested_at && <StatusBadge status={g.status} label={g.status_label} />}
                {app.can_edit && <Button variant="ghost" size="sm" icon={Trash2} loading={remove.isPending && remove.variables === g.id} onClick={() => remove.mutate(g.id)}>Remove</Button>}
              </div>
            </li>
          ))}
        </ul>
      )}
      {app.can_edit && (
        <CardBody className="space-y-3 border-t border-slate-100">
          {short > 0 && <Alert tone="warning">Add {short} more guarantor{short > 1 ? 's' : ''} before you submit.</Alert>}
          <GuarantorFinder exclude={app.guarantors.map((g) => g.membership_number)} onAdd={async (m) => { await memberApi.addGuarantor(app.id, m.membership_number); onChanged(); }} />
          <ErrorAlert error={remove.error} />
        </CardBody>
      )}
    </Card>
  );
}

function Item({ label, value }) {
  return (
    <div>
      <dt className="text-xs font-medium uppercase tracking-wide text-slate-500">{label}</dt>
      <dd className="mt-0.5 whitespace-pre-line text-sm text-slate-800">{value}</dd>
    </div>
  );
}

function Row({ label, value, strong }) {
  return (
    <div className="flex justify-between gap-3">
      <span className="text-slate-500">{label}</span>
      <span className={`tabular ${strong ? 'text-lg font-bold text-brand-800' : 'font-semibold'}`}>{value}</span>
    </div>
  );
}

function SubmitButton({ app, onDone }) {
  const mutation = useMutation({ mutationFn: () => memberApi.submitApplication(app.id), onSuccess: onDone });
  return (
    <div className="flex flex-col items-end gap-2">
      <ErrorAlert error={mutation.error} />
      <Button icon={Send} loading={mutation.isPending} onClick={() => mutation.mutate()}>
        {app.status === 'RETURNED' ? 'Resubmit application' : 'Submit application'}
      </Button>
    </div>
  );
}

function CancelButton({ app, onDone }) {
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState('');
  const mutation = useMutation({ mutationFn: () => memberApi.cancelApplication(app.id, reason), onSuccess: () => { setOpen(false); onDone(); } });
  return (
    <>
      <Button variant="secondary" icon={X} onClick={() => setOpen(true)}>Cancel application</Button>
      <Modal open={open} onClose={() => setOpen(false)} title="Cancel this application?"
        footer={
          <>
            <Button variant="secondary" onClick={() => setOpen(false)}>Keep it</Button>
            <Button variant="danger" loading={mutation.isPending} onClick={() => mutation.mutate()}>Cancel application</Button>
          </>
        }>
        <div className="space-y-3">
          <p>You can apply again later. This cannot be undone.</p>
          <TextAreaField label="Reason (optional)" rows={2} value={reason} onChange={(e) => setReason(e.target.value)} />
          <ErrorAlert error={mutation.error} />
        </div>
      </Modal>
    </>
  );
}

function EditButton({ app, onSaved }) {
  const [open, setOpen] = useState(false);
  const [values, setValues] = useState({ amount_requested: app.amount_requested, term_months: app.term_months, purpose: app.purpose });
  const mutation = useMutation({
    mutationFn: () => memberApi.updateApplication(app.id, { ...values, term_months: Number(values.term_months) }),
    onSuccess: () => { setOpen(false); onSaved(); },
  });
  return (
    <>
      <Button variant="ghost" size="sm" onClick={() => setOpen(true)}>Edit</Button>
      <Modal open={open} onClose={() => setOpen(false)} title="Edit application"
        footer={
          <>
            <Button variant="secondary" onClick={() => setOpen(false)}>Close</Button>
            <Button loading={mutation.isPending} onClick={() => mutation.mutate()}>Save changes</Button>
          </>
        }>
        <div className="space-y-3">
          <TextField label="Amount (₦)" type="number" value={values.amount_requested} onChange={(e) => setValues({ ...values, amount_requested: e.target.value })} />
          <TextField label="Repayment period (months)" type="number" value={values.term_months} onChange={(e) => setValues({ ...values, term_months: e.target.value })} />
          <TextAreaField label="Purpose" value={values.purpose} onChange={(e) => setValues({ ...values, purpose: e.target.value })} />
          <ErrorAlert error={mutation.error} />
        </div>
      </Modal>
    </>
  );
}
