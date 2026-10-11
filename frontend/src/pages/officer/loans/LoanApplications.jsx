import { useState } from 'react';
import { Link, Outlet, useNavigate, useParams } from 'react-router-dom';
import { useMutation, useQuery } from '@tanstack/react-query';
import { ArrowLeft, CheckCircle2, Download, Plus, XCircle } from 'lucide-react';
import { adminApi } from '../../../api/admin';
import ActionButton from '../../../components/officer/ActionButton';
import DataTable from '../../../components/officer/DataTable';
import DetailList from '../../../components/officer/DetailList';
import { FilterBar, FilterSelect, SearchInput } from '../../../components/officer/Filters';
import FormModal from '../../../components/officer/FormModal';
import MemberPicker from '../../../components/officer/MemberPicker';
import Tabs from '../../../components/officer/Tabs';
import useList from '../../../components/officer/useList';
import useReference from '../../../components/officer/useReference';
import { Alert, ErrorAlert } from '../../../components/ui/Alert';
import { StatusBadge } from '../../../components/ui/Badge';
import Button from '../../../components/ui/Button';
import { Card, CardBody, CardHeader } from '../../../components/ui/Card';
import EmptyState from '../../../components/ui/EmptyState';
import { SelectField, TextAreaField, TextField } from '../../../components/ui/Field';
import PageHeader from '../../../components/ui/PageHeader';
import QueryState from '../../../components/ui/QueryState';
import { Money } from '../../../components/ui/Table';
import { APPLICATION_STATUS, today } from '../../../lib/choices';
import { saveBlob } from '../../../lib/download';
import { formatDate, formatDateTime, formatNaira } from '../../../lib/format';
import { P, useCan } from '../../../lib/permissions';

export function LoansLayout() {
  const can = useCan();
  return (
    <>
      <PageHeader title="Loans" description="Every loan needs officer approval: review, decision and disbursement are separate steps." />
      <Tabs tabs={[
        { to: '/admin/loans', label: 'Applications', end: true },
        { to: '/admin/loans/active', label: 'Loans' },
        { to: '/admin/loans/overdue', label: 'Overdue' },
        { to: '/admin/loans/products', label: 'Products', show: can(P.MANAGE_LOAN_PRODUCTS) },
      ]} />
      <Outlet />
    </>
  );
}

function NewApplicationButton() {
  const navigate = useNavigate();
  const [member, setMember] = useState(null);
  const products = useReference('loanProducts', { is_active: true });
  return (
    <FormModal trigger="Apply for a member" triggerIcon={Plus} title="Loan application on a member's behalf" submitLabel="Submit application"
      defaultValues={{ product: '', amount_requested: '', term_months: '', purpose: '', guarantors: '' }}
      transform={(v) => ({
        ...v, member: member?.id, term_months: Number(v.term_months),
        guarantors: v.guarantors.split(/[\s,;]+/).map((n) => n.trim()).filter(Boolean),
      })}
      onSubmit={adminApi.loanApplications.create}
      onDone={(app) => { setMember(null); navigate(`/admin/loans/applications/${app.id}`); }}
      renderFields={({ register, errors }) => (
        <>
          <MemberPicker value={member} onChange={setMember} required error={errors.member?.message} />
          <SelectField label="Loan product" required {...register('product', { required: 'Choose a product.' })} error={errors.product?.message}>
            <option value="">Choose…</option>
            {(products.data || []).map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
          </SelectField>
          <div className="grid gap-4 sm:grid-cols-2">
            <TextField label="Amount (₦)" required inputMode="decimal" {...register('amount_requested', { required: 'Required.' })} error={errors.amount_requested?.message} />
            <TextField label="Term (months)" required type="number" {...register('term_months', { required: 'Required.' })} error={errors.term_months?.message} />
          </div>
          <TextAreaField label="Purpose" required rows={2} {...register('purpose', { required: 'Required.' })} error={errors.purpose?.message} />
          <TextField label="Guarantors' membership numbers" required {...register('guarantors', { required: 'At least one guarantor is required.' })}
            error={errors.guarantors?.message} hint="Separate several with commas. Each guarantor is asked by e-mail and in the portal to accept." />
        </>
      )} />
  );
}

export function LoanApplications() {
  const can = useCan();
  const products = useReference('loanProducts');
  const list = useList(['admin', 'loan-applications'], adminApi.loanApplications.list, { search: '', status: '', product: '' });
  return (
    <DataTable
      title="Applications"
      action={can(P.REVIEW_LOAN_APPLICATION) && <NewApplicationButton />}
      query={list.query} page={list.page} onPage={list.setPage} empty="No applications match."
      toolbar={
        <FilterBar>
          <SearchInput value={list.filters.search} onChange={(v) => list.setFilter('search', v)} placeholder="Reference, member name or number" />
          <FilterSelect label="Status" value={list.filters.status} onChange={(v) => list.setFilter('status', v)} options={APPLICATION_STATUS} />
          <FilterSelect label="Product" value={list.filters.product} onChange={(v) => list.setFilter('product', v)} options={(products.data || []).map((p) => [p.id, p.name])} />
        </FilterBar>
      }
      columns={[
        { header: 'Reference', cell: (a) => <Link to={`/admin/loans/applications/${a.id}`} className="font-semibold text-brand-600 hover:underline">{a.reference}</Link> },
        { header: 'Member', cell: (a) => <><p className="font-medium text-slate-900">{a.member.full_name}</p><p className="text-xs text-slate-500">{a.member.membership_number}</p></> },
        { header: 'Product', cell: (a) => a.product_name },
        { header: 'Amount', align: 'right', cell: (a) => <><Money value={a.approved_amount || a.amount_requested} className="font-semibold" /><p className="text-xs text-slate-500">{a.approved_term_months || a.term_months} months</p></> },
        { header: 'Submitted', cell: (a) => <span className="whitespace-nowrap text-xs">{formatDateTime(a.submitted_at)}</span> },
        { header: 'Status', cell: (a) => <StatusBadge status={a.status} label={a.status_label} /> },
      ]}
    />
  );
}

function Eligibility({ id }) {
  const result = useQuery({ queryKey: ['admin', 'loan-application', id, 'eligibility'], queryFn: () => adminApi.loanApplications.sub(id, 'eligibility') });
  return (
    <Card>
      <CardHeader title="Eligibility (live)" description="Re-checked now against current balances and loans." />
      <CardBody>
        <QueryState query={result}>
          {(e) => (
            <div className="space-y-3">
              <Alert tone={e.eligible ? 'success' : 'error'} title={e.eligible ? 'Meets the requirements' : 'Does not meet the requirements'}>
                Maximum for this member: {formatNaira(e.max_amount)} · eligible savings {formatNaira(e.savings)}
              </Alert>
              <ul className="space-y-2">
                {e.checks.map((c) => (
                  <li key={c.code} className="flex gap-2 text-sm">
                    {c.passed ? <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-emerald-600" aria-label="Passed" /> : <XCircle className={`mt-0.5 h-4 w-4 shrink-0 ${c.hard ? 'text-red-600' : 'text-amber-600'}`} aria-label={c.hard ? 'Failed' : 'Warning'} />}
                    <span><span className="font-medium text-slate-800">{c.label}</span>{c.detail && <span className="block text-xs text-slate-500">{c.detail}</span>}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </QueryState>
      </CardBody>
    </Card>
  );
}

export function LoanApplicationDetail() {
  const { id } = useParams();
  const can = useCan();
  const navigate = useNavigate();
  const application = useQuery({ queryKey: ['admin', 'loan-application', id], queryFn: () => adminApi.loanApplications.get(id) });
  const download = useMutation({ mutationFn: (doc) => adminApi.loanApplications.downloadDocument(id, doc.id).then((res) => saveBlob(res, doc.title)) });

  return (
    <>
      <Link to="/admin/loans" className="inline-flex items-center gap-1 text-sm font-medium text-brand-600 hover:underline">
        <ArrowLeft className="h-4 w-4" aria-hidden="true" /> Applications
      </Link>
      <QueryState query={application}>
        {(a) => (
          <div className="mt-3 space-y-6">
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div>
                <div className="flex items-center gap-2"><h2 className="text-xl font-bold text-slate-900">{a.reference}</h2><StatusBadge status={a.status} label={a.status_label} /></div>
                <p className="text-sm text-slate-500">
                  <Link to={`/admin/members/${a.member.id}`} className="font-medium text-brand-600 hover:underline">{a.member.full_name}</Link> · {a.member.membership_number} · {a.product_name}
                </p>
              </div>
              <div className="flex flex-wrap gap-2">
                {a.status === 'SUBMITTED' && can(P.REVIEW_LOAN_APPLICATION) && (
                  <ActionButton label="Start review" input="optional" inputLabel="Notes" description="Take this application under review." action={(notes) => adminApi.loanApplications.action(a.id, 'start-review', { notes })} />
                )}
                {['SUBMITTED', 'UNDER_REVIEW'].includes(a.status) && can(P.REVIEW_LOAN_APPLICATION) && (
                  <ActionButton label="Return to member" variant="secondary" input="required" inputLabel="What needs to change" description="The member can edit and resubmit the application."
                    action={(message) => adminApi.loanApplications.action(a.id, 'return', { message })} />
                )}
                {a.status === 'UNDER_REVIEW' && can(P.APPROVE_LOAN_APPLICATION) && (
                  <FormModal trigger="Approve" title={`Approve ${a.reference}`} submitLabel="Approve loan"
                    defaultValues={{ approved_amount: a.amount_requested, approved_term_months: a.term_months, notes: '' }}
                    transform={(v) => ({ ...v, approved_term_months: Number(v.approved_term_months) })}
                    onSubmit={(v) => adminApi.loanApplications.action(a.id, 'approve', v)}
                    renderFields={({ register, errors }) => (
                      <>
                        <p className="text-sm text-slate-600">You may approve a lower amount or a different term. Eligibility is checked again.</p>
                        <div className="grid gap-4 sm:grid-cols-2">
                          <TextField label="Approved amount (₦)" inputMode="decimal" {...register('approved_amount')} error={errors.approved_amount?.message} />
                          <TextField label="Term (months)" type="number" {...register('approved_term_months')} error={errors.approved_term_months?.message} />
                        </div>
                        <TextAreaField label="Notes (optional)" rows={2} {...register('notes')} error={errors.notes?.message} />
                      </>
                    )} />
                )}
                {['SUBMITTED', 'UNDER_REVIEW'].includes(a.status) && can(P.APPROVE_LOAN_APPLICATION) && (
                  <ActionButton label="Reject" variant="danger" input="required" description="The member will see this reason." action={(reason) => adminApi.loanApplications.action(a.id, 'reject', { reason })} />
                )}
                {a.status === 'APPROVED' && can(P.DISBURSE_LOAN) && (
                  <FormModal trigger="Disburse" title={`Disburse ${a.reference}`} submitLabel="Disburse loan"
                    defaultValues={{ disbursed_on: today(), external_reference: '' }}
                    onSubmit={(v) => adminApi.loanApplications.action(a.id, 'disburse', v)}
                    onDone={(loan) => navigate(`/admin/loans/${loan.id}`)}
                    renderFields={({ register, errors }) => (
                      <>
                        <Alert>Disbursing {formatNaira(a.approved_amount)} over {a.approved_term_months} months. Depending on settings, a second officer must approve the disbursement entry before the loan becomes active.</Alert>
                        <TextField label="Disbursement date" type="date" max={today()} {...register('disbursed_on')} error={errors.disbursed_on?.message} />
                        <TextField label="Payment reference" {...register('external_reference')} error={errors.external_reference?.message} hint="Bank transfer or cheque number" />
                      </>
                    )} />
                )}
                {a.loan && <Link to={`/admin/loans/${a.loan.id}`}><Button variant="secondary">View loan</Button></Link>}
              </div>
            </div>

            {a.status === 'RETURNED' && a.info_request_message && <Alert tone="warning" title="Returned to member">{a.info_request_message}</Alert>}

            <div className="grid gap-6 lg:grid-cols-3">
              <div className="space-y-6 lg:col-span-2">
                <Card>
                  <CardHeader title="Application" />
                  <CardBody>
                    <DetailList columns={3} items={[
                      ['Amount requested', formatNaira(a.amount_requested)], ['Term requested', `${a.term_months} months`], ['Submitted', formatDateTime(a.submitted_at)],
                      a.approved_amount && ['Approved amount', formatNaira(a.approved_amount)], a.approved_term_months && ['Approved term', `${a.approved_term_months} months`],
                      ['Purpose', a.purpose],
                    ]} />
                  </CardBody>
                </Card>
                <Card>
                  <CardHeader title="Repayment estimate" description={`For ${formatNaira(a.approved_amount || a.amount_requested)} over ${a.approved_term_months || a.term_months} months`} />
                  <CardBody>
                    <DetailList columns={3} items={[
                      ['Monthly repayment', formatNaira(a.quote.monthly_payment)], ['Total interest', formatNaira(a.quote.total_interest)], ['Total to repay', formatNaira(a.quote.total_payable)],
                      ['First due', formatDate(a.quote.first_due_date)], ['Maturity', formatDate(a.quote.maturity_date)],
                      ['Interest', a.quote.interest_deducted_upfront ? 'Deducted at disbursement' : 'With each instalment'],
                    ]} />
                  </CardBody>
                </Card>
                <Card>
                  <CardHeader title="Guarantors" description={`${a.guarantors.filter((g) => g.status === 'ACCEPTED').length} accepted; the loan can be approved once enough guarantors accept.`} />
                  {a.guarantors.length ? (
                    <ul className="divide-y divide-slate-100">
                      {a.guarantors.map((g) => (
                        <li key={g.id} className="flex flex-wrap justify-between gap-3 px-5 py-3 text-sm">
                          <span>
                            <Link to={`/admin/members/${g.guarantor.id}`} className="font-medium text-slate-900 hover:underline">{g.guarantor.full_name}</Link> <span className="text-slate-500">{g.guarantor.membership_number}</span>
                            <span className="block text-xs text-slate-500">
                              {g.requested_at ? `Asked ${formatDateTime(g.requested_at)}` : 'Not asked yet (draft)'}
                              {g.responded_at ? ` · answered ${formatDateTime(g.responded_at)}` : ''}
                              {g.decline_reason ? ` · “${g.decline_reason}”` : ''}
                            </span>
                          </span>
                          <span className="flex items-center gap-2"><Money value={g.amount_guaranteed} /><StatusBadge status={g.status} label={g.status_label} /></span>
                        </li>
                      ))}
                    </ul>
                  ) : <EmptyState title="No guarantors" />}
                </Card>
                <Card>
                  <CardHeader title="Documents" />
                  <ErrorAlert error={download.error} className="m-4" />
                  {a.documents.length ? (
                    <ul className="divide-y divide-slate-100">
                      {a.documents.map((d) => (
                        <li key={d.id} className="flex items-center justify-between gap-3 px-5 py-3 text-sm">
                          <span><span className="font-medium">{d.title}</span><span className="block text-xs text-slate-500">{d.uploaded_by} · {formatDateTime(d.created_at)}</span></span>
                          <Button size="sm" variant="ghost" icon={Download} onClick={() => download.mutate(d)}>Download</Button>
                        </li>
                      ))}
                    </ul>
                  ) : <EmptyState title="No documents" />}
                </Card>
              </div>
              <div className="space-y-6">
                {['SUBMITTED', 'UNDER_REVIEW', 'APPROVED'].includes(a.status) && <Eligibility id={a.id} />}
                <Card>
                  <CardHeader title="Decision trail" />
                  <CardBody>
                    <DetailList columns={1} items={[
                      ['Reviewed by', a.reviewed_by && `${a.reviewed_by} · ${formatDateTime(a.reviewed_at)}`],
                      ['Review notes', a.review_notes],
                      ['Decided by', a.decided_by && `${a.decided_by} · ${formatDateTime(a.decided_at)}`],
                      ['Decision notes', a.decision_reason],
                      a.cancelled_at && ['Cancelled by member', formatDateTime(a.cancelled_at)],
                    ]} />
                  </CardBody>
                </Card>
              </div>
            </div>
          </div>
        )}
      </QueryState>
    </>
  );
}
