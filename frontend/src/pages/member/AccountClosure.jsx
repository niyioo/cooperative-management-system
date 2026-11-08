import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { DoorOpen } from 'lucide-react';
import { memberApi } from '../../api/member';
import { Alert, ErrorAlert } from '../../components/ui/Alert';
import { StatusBadge } from '../../components/ui/Badge';
import Button from '../../components/ui/Button';
import { Card, CardBody, CardHeader } from '../../components/ui/Card';
import { CheckboxField, SelectField, TextAreaField } from '../../components/ui/Field';
import Modal from '../../components/ui/Modal';
import PageHeader from '../../components/ui/PageHeader';
import QueryState from '../../components/ui/QueryState';
import { applyFieldErrors } from '../../lib/errors';
import { formatDate, formatDateTime } from '../../lib/format';

const OPEN = ['SUBMITTED', 'UNDER_REVIEW', 'APPROVED'];
const REASONS = [
  ['RETIREMENT', 'Retirement'],
  ['RESIGNATION', 'Resignation from service'],
  ['TRANSFER', 'Transfer'],
  ['PERSONAL', 'Personal reasons'],
  ['OTHER', 'Other'],
];

export default function AccountClosure() {
  const query = useQuery({ queryKey: ['me', 'closures'], queryFn: memberApi.closureRequests });
  return (
    <div className="space-y-6">
      <PageHeader title="Account closure" description="Apply to close your cooperative membership." />
      <QueryState query={query}>
        {(data) => {
          const open = data.results.find((r) => OPEN.includes(r.status));
          return (
            <>
              {open ? <OpenRequest request={open} /> : <ClosureForm />}
              {data.results.filter((r) => r !== open).length > 0 && <History requests={data.results.filter((r) => r !== open)} />}
            </>
          );
        }}
      </QueryState>
    </div>
  );
}

function OpenRequest({ request }) {
  const queryClient = useQueryClient();
  const [confirming, setConfirming] = useState(false);
  const withdraw = useMutation({
    mutationFn: () => memberApi.withdrawClosure(request.id),
    onSuccess: () => {
      setConfirming(false);
      queryClient.invalidateQueries({ queryKey: ['me'] });
    },
  });
  return (
    <Card>
      <CardHeader title={`Request ${request.reference}`} action={<StatusBadge status={request.status} label={request.status_label} />} />
      <CardBody className="space-y-4">
        <Alert tone="info">
          Your account stays open while the request is considered. Only the cooperative's officers can approve and complete a closure; your records are kept either way.
        </Alert>
        <dl className="grid gap-4 sm:grid-cols-2 text-sm">
          <div><dt className="text-xs text-slate-500">Submitted</dt><dd>{formatDateTime(request.created_at)}</dd></div>
          <div><dt className="text-xs text-slate-500">Reason</dt><dd>{request.reason_category_label}</dd></div>
          <div className="sm:col-span-2"><dt className="text-xs text-slate-500">Details</dt><dd className="whitespace-pre-line">{request.reason}</dd></div>
        </dl>
        {request.can_withdraw && (
          <Button variant="secondary" onClick={() => setConfirming(true)}>Withdraw request</Button>
        )}
      </CardBody>
      <Modal open={confirming} onClose={() => setConfirming(false)} title="Withdraw your closure request?"
        footer={
          <>
            <Button variant="secondary" onClick={() => setConfirming(false)}>Keep request</Button>
            <Button loading={withdraw.isPending} onClick={() => withdraw.mutate()}>Withdraw</Button>
          </>
        }>
        <p>Your membership continues as normal. You can apply again later.</p>
        <ErrorAlert error={withdraw.error} className="mt-3" />
      </Modal>
    </Card>
  );
}

function ClosureForm() {
  const queryClient = useQueryClient();
  const [error, setError] = useState(null);
  const { register, handleSubmit, formState, setError: setFieldError } = useForm({ defaultValues: { reason_category: '', confirmed: false } });

  const onSubmit = async (values) => {
    setError(null);
    try {
      await memberApi.requestClosure({ ...values, attachment: values.attachment?.[0] });
      queryClient.invalidateQueries({ queryKey: ['me'] });
    } catch (err) {
      if (!applyFieldErrors(err, setFieldError)) setError(err);
    }
  };

  return (
    <Card>
      <CardHeader title="APPLY TO CLOSE ACCOUNT" description="Submitting a request does not close your account; an officer reviews it first." />
      <CardBody>
        <form className="max-w-2xl space-y-4" onSubmit={handleSubmit(onSubmit)} noValidate>
          <Alert tone="warning" title="Before you apply">
            Closing your account ends your membership. Any outstanding loan must be settled, and your savings and investments are paid out to you in line with cooperative rules.
          </Alert>
          <ErrorAlert error={error} />
          <SelectField label="Reason for closure" required error={formState.errors.reason_category?.message}
            {...register('reason_category', { required: 'Choose a reason.' })}>
            <option value="">Choose…</option>
            {REASONS.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
          </SelectField>
          <TextAreaField label="Tell us more" required error={formState.errors.reason?.message}
            {...register('reason', { required: 'Please explain briefly.', maxLength: { value: 2000, message: 'Keep it under 2,000 characters.' } })} />
          <TextAreaField label="Additional information (optional)" rows={3} {...register('additional_information')} />
          <div>
            <label className="mb-1 block text-sm font-medium text-slate-700" htmlFor="closure-attachment">Supporting document (optional)</label>
            <input id="closure-attachment" type="file" accept=".pdf,.jpg,.jpeg,.png" className="block text-sm" {...register('attachment')} />
            {formState.errors.attachment && <p className="mt-1 text-xs font-medium text-red-600">{formState.errors.attachment.message}</p>}
          </div>
          <CheckboxField label="I understand that closing my account ends my membership, and that my request will be reviewed by the cooperative's officers."
            error={formState.errors.confirmed?.message} {...register('confirmed', { validate: (v) => v || 'Please confirm to continue.' })} />
          <Button type="submit" variant="danger" icon={DoorOpen} loading={formState.isSubmitting}>Submit closure request</Button>
        </form>
      </CardBody>
    </Card>
  );
}

function History({ requests }) {
  return (
    <Card>
      <CardHeader title="Previous requests" />
      <ul className="divide-y divide-slate-100">
        {requests.map((r) => (
          <li key={r.id} className="flex flex-wrap items-center justify-between gap-3 px-5 py-3 text-sm">
            <div>
              <p className="font-medium text-slate-800">{r.reference} · {r.reason_category_label}</p>
              <p className="text-xs text-slate-500">Submitted {formatDate(r.created_at)}{r.decision_reason ? ` · ${r.decision_reason}` : ''}</p>
            </div>
            <StatusBadge status={r.status} label={r.status_label} />
          </li>
        ))}
      </ul>
    </Card>
  );
}
