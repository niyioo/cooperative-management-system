import { useState } from 'react';
import { Link, Outlet, useNavigate, useParams } from 'react-router-dom';
import { useMutation, useQuery } from '@tanstack/react-query';
import { ArrowLeft, Download, Plus, Upload } from 'lucide-react';
import { adminApi, allPages } from '../../../api/admin';
import ActionButton from '../../../components/officer/ActionButton';
import DataTable from '../../../components/officer/DataTable';
import DetailList from '../../../components/officer/DetailList';
import { FilterBar, FilterDate, FilterSelect, SearchInput } from '../../../components/officer/Filters';
import FormModal from '../../../components/officer/FormModal';
import MemberPicker from '../../../components/officer/MemberPicker';
import Tabs from '../../../components/officer/Tabs';
import useList from '../../../components/officer/useList';
import useReference from '../../../components/officer/useReference';
import { useAuth } from '../../../auth/AuthProvider';
import { Alert, ErrorAlert } from '../../../components/ui/Alert';
import { StatusBadge } from '../../../components/ui/Badge';
import Button from '../../../components/ui/Button';
import { Card, CardBody, CardHeader } from '../../../components/ui/Card';
import { SelectField, TextAreaField, TextField } from '../../../components/ui/Field';
import PageHeader from '../../../components/ui/PageHeader';
import QueryState from '../../../components/ui/QueryState';
import { Money, Table, Td, Th } from '../../../components/ui/Table';
import { BATCH_STATUS, BATCH_TYPES, TXN_STATUS, TXN_TYPES, UPLOAD_BATCH_TYPES, currentPeriod, options, today } from '../../../lib/choices';
import { saveBlob } from '../../../lib/download';
import { formatDate, formatDateTime, formatPeriod } from '../../../lib/format';
import { P, useCan } from '../../../lib/permissions';

export function TransactionsLayout() {
  const can = useCan();
  const dashboard = useQuery({ queryKey: ['admin', 'dashboard'], queryFn: adminApi.dashboard });
  const approvals = dashboard.data?.approvals || {};
  return (
    <>
      <PageHeader title="Transactions" description="The ledger is append-only: mistakes are corrected by reversal or adjustment, never edited or deleted." />
      <Tabs tabs={[
        { to: '/admin/transactions', label: 'Ledger', end: true, show: can(P.VIEW_ALL_TRANSACTIONS) },
        { to: '/admin/transactions/pending', label: 'Awaiting approval', count: approvals.entries, show: can([P.APPROVE_TRANSACTION, P.VIEW_ALL_TRANSACTIONS]) },
        { to: '/admin/transactions/batches', label: 'Batches', count: approvals.batches, show: can([P.MANAGE_BATCHES, P.APPROVE_BATCH]) },
      ]} />
      <Outlet />
    </>
  );
}

const amountCell = (t) => <Money value={t.signed_amount} className={`font-semibold ${Number(t.signed_amount) < 0 ? 'text-red-700' : ''}`} />;
const memberCell = (t) => (t.member ? <><p className="font-medium text-slate-900">{t.member.full_name}</p><p className="text-xs text-slate-500">{t.member.membership_number}</p></> : '—');
const typeCell = (t) => <><p>{t.type_label}</p><p className="text-xs text-slate-500">{t.reference}{t.batch_reference ? ` · ${t.batch_reference}` : ''}</p></>;
const accountCell = (t) => <span className="text-xs">{t.account?.label}<br /><span className="text-slate-500">{t.account?.number}</span></span>;

function AdjustmentButton() {
  const [member, setMember] = useState(null);
  return (
    <FormModal trigger="Post adjustment" triggerIcon={Plus} title="Correcting adjustment" submitLabel="Post adjustment"
      defaultValues={{ account_type: 'SAVINGS', account: '', entry_side: 'CREDIT', amount: '', reason: '', value_date: today(), period: '' }}
      transform={(v) => ({ ...v, period: v.period || null })}
      onSubmit={adminApi.transactions.adjust} onDone={() => setMember(null)}
      renderFields={({ register, errors, watch }) => <AdjustmentFields register={register} errors={errors} watch={watch} member={member} setMember={setMember} />} />
  );
}

function AdjustmentFields({ register, errors, watch, member, setMember }) {
  const type = watch('account_type');
  const accounts = useQuery({
    queryKey: ['admin', 'adjust-accounts', member?.id, type],
    queryFn: () => allPages(type === 'SAVINGS' ? adminApi.savingsAccounts.list : adminApi.investmentAccounts.list, { member: member.id }),
    enabled: !!member,
  });
  return (
    <>
      <Alert tone="warning">Adjustments always need a second officer's approval. Use a reversal instead when a whole entry was wrong.</Alert>
      <MemberPicker value={member} onChange={setMember} status="" required />
      <div className="grid gap-4 sm:grid-cols-2">
        <SelectField label="Account type" {...register('account_type')}><option value="SAVINGS">Savings</option><option value="INVESTMENT">Investment</option></SelectField>
        <SelectField label="Account" required {...register('account', { required: 'Choose an account.' })} error={errors.account?.message} disabled={!member}>
          <option value="">{member ? 'Choose…' : 'Pick a member first'}</option>
          {(accounts.data || []).map((a) => <option key={a.id} value={a.id}>{a.account_number} · {a.product_name}{a.cycle_name ? ` ${a.cycle_name}` : ''}</option>)}
        </SelectField>
        <SelectField label="Direction" {...register('entry_side')}><option value="CREDIT">Credit (increase balance)</option><option value="DEBIT">Debit (decrease balance)</option></SelectField>
        <TextField label="Amount (₦)" required inputMode="decimal" {...register('amount', { required: 'Enter an amount.' })} error={errors.amount?.message} />
        <TextField label="Value date" type="date" max={today()} {...register('value_date')} error={errors.value_date?.message} />
        <TextField label="For month (optional)" type="month" {...register('period')} error={errors.period?.message} />
      </div>
      <TextAreaField label="Reason" required rows={2} {...register('reason', { required: 'Give a reason.' })} error={errors.reason?.message} />
    </>
  );
}

function ReverseButton({ entry }) {
  return (
    <ActionButton size="sm" variant="ghost" label="Reverse" confirmVariant="danger" input="required"
      description={`Post an equal and opposite entry for ${entry.reference}. The original stays on record.`}
      action={(reason) => adminApi.transactions.action(entry.id, 'reverse', { reason })} />
  );
}

export function Ledger() {
  const can = useCan();
  const list = useList(['admin', 'ledger'], adminApi.transactions.list, { search: '', txn_type: '', status: '', date_from: '', date_to: '' });
  return (
    <DataTable title="Ledger" action={can(P.POST_ADJUSTMENT) && <AdjustmentButton />}
      query={list.query} page={list.page} onPage={list.setPage} empty="No entries match."
      toolbar={
        <FilterBar>
          <SearchInput value={list.filters.search} onChange={(v) => list.setFilter('search', v)} placeholder="Reference, member number or surname, description" />
          <FilterSelect label="Type" value={list.filters.txn_type} onChange={(v) => list.setFilter('txn_type', v)} options={TXN_TYPES} />
          <FilterSelect label="Status" value={list.filters.status} onChange={(v) => list.setFilter('status', v)} options={TXN_STATUS} />
          <FilterDate label="From" value={list.filters.date_from} onChange={(v) => list.setFilter('date_from', v)} />
          <FilterDate label="To" value={list.filters.date_to} onChange={(v) => list.setFilter('date_to', v)} />
        </FilterBar>
      }
      columns={[
        { header: 'Date', cell: (t) => <span className="whitespace-nowrap">{formatDate(t.value_date)}</span> },
        { header: 'Member', cell: memberCell },
        { header: 'Type', cell: typeCell },
        { header: 'Account', cell: accountCell },
        { header: 'Amount', align: 'right', cell: amountCell },
        { header: 'Status', cell: (t) => <StatusBadge status={t.status} label={t.status_label} /> },
        { header: 'By', cell: (t) => <span className="text-xs">{t.created_by}{t.approved_by && <><br /><span className="text-slate-500">✓ {t.approved_by}</span></>}</span> },
        { header: '', align: 'right', cell: (t) => can(P.REVERSE_TRANSACTION) && t.status === 'POSTED' && t.txn_type !== 'REVERSAL' && <ReverseButton entry={t} /> },
      ]} />
  );
}

export function PendingEntries() {
  const can = useCan();
  const { user } = useAuth();
  const list = useList(['admin', 'ledger-pending'], adminApi.transactions.pending, { txn_type: '' });
  return (
    <DataTable title="Awaiting approval" description="Maker-checker: the officer who recorded an entry cannot approve it. Batch lines are approved with their batch."
      query={list.query} page={list.page} onPage={list.setPage} empty="Nothing is waiting for approval."
      toolbar={<FilterBar><FilterSelect label="Type" value={list.filters.txn_type} onChange={(v) => list.setFilter('txn_type', v)} options={TXN_TYPES} /></FilterBar>}
      columns={[
        { header: 'Recorded', cell: (t) => <span className="text-xs">{formatDateTime(t.created_at)}<br />{t.created_by}</span> },
        { header: 'Member', cell: memberCell },
        { header: 'Type', cell: (t) => <>{typeCell(t)}{t.description && <p className="text-xs text-slate-500">{t.description}</p>}</> },
        { header: 'Account', cell: accountCell },
        { header: 'Value date', cell: (t) => formatDate(t.value_date) },
        { header: 'Amount', align: 'right', cell: amountCell },
        {
          header: '', align: 'right',
          cell: (t) => {
            const mine = t.created_by === user.full_name;
            if (t.batch_reference) return <span className="text-xs text-slate-500">In batch</span>;
            return (
              <div className="flex justify-end gap-1">
                {can(P.APPROVE_TRANSACTION) && !mine && (
                  <ActionButton size="sm" label="Approve" description={`Approve and post ${t.reference}?`} action={() => adminApi.transactions.action(t.id, 'approve')} />
                )}
                {(mine || can(P.APPROVE_TRANSACTION)) && (
                  <ActionButton size="sm" variant="secondary" label={mine ? 'Cancel' : 'Reject'} confirmVariant="danger" input="required"
                    description={mine ? 'Cancel your own pending entry.' : 'Reject this entry. It will not affect any balance.'}
                    action={(reason) => adminApi.transactions.action(t.id, 'reject', { reason })} />
                )}
              </div>
            );
          },
        },
      ]} />
  );
}

function UploadBatchButton() {
  const navigate = useNavigate();
  const products = useReference('savingsProducts');
  const template = useMutation({ mutationFn: (type) => adminApi.batches.template(type).then((res) => saveBlob(res, `${type.toLowerCase()}-template.xlsx`)) });
  return (
    <FormModal trigger="Upload batch" triggerIcon={Upload} title="Upload a batch" submitLabel="Upload and check"
      defaultValues={{ batch_type: 'CONTRIBUTIONS', product: '', period: currentPeriod(), description: '', file: null }}
      transform={(v) => ({ ...v, file: v.file?.[0] })}
      onSubmit={adminApi.batches.upload}
      onDone={(batch) => navigate(`/admin/transactions/batches/${batch.id}`)}
      renderFields={({ register, errors, watch }) => {
        const type = watch('batch_type');
        return (
          <>
            <SelectField label="Batch type" {...register('batch_type')}>{options(UPLOAD_BATCH_TYPES)}</SelectField>
            <div className="flex items-center justify-between gap-2 rounded-lg bg-slate-50 px-3 py-2 text-xs text-slate-600">
              <span>Start from the template for this batch type.</span>
              <Button size="sm" variant="ghost" icon={Download} loading={template.isPending} onClick={() => template.mutate(type)}>Template</Button>
            </div>
            <ErrorAlert error={template.error} />
            {['CONTRIBUTIONS', 'OPENING_BALANCES'].includes(type) && (
              <SelectField label="Default savings product" {...register('product')} error={errors.product?.message} hint="Used for rows that leave the product column blank.">
                <option value="">None</option>
                {(products.data || []).map((p) => <option key={p.id} value={p.code}>{p.name}</option>)}
              </SelectField>
            )}
            <TextField label="Default month" type="month" {...register('period')} error={errors.period?.message} />
            <TextField label="Description" {...register('description')} error={errors.description?.message} hint="e.g. March payroll deductions" />
            <TextField label="File" type="file" accept=".xlsx,.csv" required {...register('file', { required: 'Choose a file.' })} error={errors.file?.message} />
          </>
        );
      }} />
  );
}

export function Batches() {
  const can = useCan();
  const list = useList(['admin', 'batches'], adminApi.batches.list, { search: '', batch_type: '', status: '' });
  return (
    <DataTable title="Batches" description="Bulk postings: upload, check, submit, then a second officer approves and everything posts together."
      action={can(P.MANAGE_BATCHES) && <UploadBatchButton />}
      query={list.query} page={list.page} onPage={list.setPage} empty="No batches match."
      toolbar={
        <FilterBar>
          <SearchInput value={list.filters.search} onChange={(v) => list.setFilter('search', v)} placeholder="Reference or description" />
          <FilterSelect label="Type" value={list.filters.batch_type} onChange={(v) => list.setFilter('batch_type', v)} options={BATCH_TYPES} />
          <FilterSelect label="Status" value={list.filters.status} onChange={(v) => list.setFilter('status', v)} options={BATCH_STATUS} />
        </FilterBar>
      }
      columns={[
        { header: 'Batch', cell: (b) => <Link to={`/admin/transactions/batches/${b.id}`} className="font-semibold text-brand-600 hover:underline">{b.reference}</Link> },
        { header: 'Type', cell: (b) => <>{b.batch_type_label}{b.description && <p className="text-xs text-slate-500">{b.description}</p>}</> },
        { header: 'Lines', align: 'right', cell: (b) => b.line_count },
        { header: 'Total', align: 'right', cell: (b) => <Money value={b.total_amount} className="font-semibold" /> },
        { header: 'Created', cell: (b) => <span className="text-xs">{formatDateTime(b.created_at)}<br />{b.created_by}</span> },
        { header: 'Status', cell: (b) => <StatusBadge status={b.status} label={b.status_label} /> },
      ]} />
  );
}

function ValidationReport({ report }) {
  if (!report || (!report.errors?.length && !report.file_errors?.length && !report.unknown_columns?.length)) return null;
  return (
    <Card>
      <CardHeader title="Problems found" description="Nothing was created. Fix the file and upload it again." />
      <CardBody className="space-y-3">
        {report.file_errors?.length > 0 && <Alert tone="error">{report.file_errors.join(' ')}</Alert>}
        {report.unknown_columns?.length > 0 && <Alert tone="warning" title="Ignored columns">{report.unknown_columns.join(', ')}</Alert>}
        {report.errors?.length > 0 && (
          <div className="max-h-96 overflow-y-auto">
            <Table caption="Row errors">
              <thead><tr><Th>Row</Th><Th>Problems</Th></tr></thead>
              <tbody className="divide-y divide-slate-100">
                {report.errors.map((e) => (
                  <tr key={e.row}>
                    <Td className="font-semibold">{e.row}</Td>
                    <Td>
                      <ul className="space-y-0.5 text-xs text-red-700">
                        {Array.isArray(e.errors)
                          ? e.errors.map((msg) => <li key={msg}>{msg}</li>)
                          : Object.entries(e.errors).map(([f, msgs]) => <li key={f}><strong>{f}:</strong> {[].concat(msgs).join(' ')}</li>)}
                      </ul>
                    </Td>
                  </tr>
                ))}
              </tbody>
            </Table>
          </div>
        )}
      </CardBody>
    </Card>
  );
}

export function BatchDetail() {
  const { id } = useParams();
  const can = useCan();
  const { user } = useAuth();
  const batch = useQuery({ queryKey: ['admin', 'batch', id], queryFn: () => adminApi.batches.get(id) });
  const lines = useList(['admin', 'batch', id, 'lines'], (params) => adminApi.batches.sub(id, 'lines', params));
  return (
    <>
      <Link to="/admin/transactions/batches" className="inline-flex items-center gap-1 text-sm font-medium text-brand-600 hover:underline">
        <ArrowLeft className="h-4 w-4" aria-hidden="true" /> Batches
      </Link>
      <QueryState query={batch}>
        {(b) => {
          const mine = b.created_by === user.full_name;
          return (
            <div className="mt-3 space-y-6">
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div>
                  <div className="flex items-center gap-2"><h2 className="text-xl font-bold text-slate-900">{b.reference}</h2><StatusBadge status={b.status} label={b.status_label} /></div>
                  <p className="text-sm text-slate-500">{b.batch_type_label}{b.description ? ` · ${b.description}` : ''}</p>
                </div>
                <div className="flex flex-wrap gap-2">
                  {b.status === 'VALIDATED' && can(P.MANAGE_BATCHES) && (
                    <ActionButton label="Submit for approval" description={`Submit ${b.line_count} line(s) totalling ₦${b.total_amount} for a second officer to approve.`} action={() => adminApi.batches.action(b.id, 'submit')} />
                  )}
                  {b.status === 'SUBMITTED' && can(P.APPROVE_BATCH) && !mine && (
                    <ActionButton label="Approve and post" description="Every line is re-checked and posted together; if any line fails, nothing is posted." action={() => adminApi.batches.action(b.id, 'approve')} />
                  )}
                  {['DRAFT', 'VALIDATED', 'SUBMITTED'].includes(b.status) && can([P.MANAGE_BATCHES, P.APPROVE_BATCH]) && (
                    <ActionButton label="Reject" variant="danger" input="required" description="Rejecting discards the pending lines. Nothing is posted." action={(reason) => adminApi.batches.action(b.id, 'reject', { reason })} />
                  )}
                </div>
              </div>
              {b.status === 'SUBMITTED' && mine && <Alert>You created this batch, so another officer must approve it.</Alert>}
              {b.status === 'REJECTED' && b.rejection_reason && <Alert tone="error" title="Rejected">{b.rejection_reason}</Alert>}
              <Card>
                <CardBody>
                  <DetailList columns={3} items={[
                    ['Lines', b.line_count], ['Total', <Money key="t" value={b.total_amount} className="font-semibold" />], ['Month', b.period && formatPeriod(b.period)],
                    ['Created', `${b.created_by} · ${formatDateTime(b.created_at)}`], ['Submitted', formatDateTime(b.submitted_at)],
                    ['Approved', b.approved_by && `${b.approved_by} · ${formatDateTime(b.approved_at)}`], ['Posted', formatDateTime(b.posted_at)],
                  ]} />
                </CardBody>
              </Card>
              <ValidationReport report={b.validation_report} />
              <DataTable title="Lines" query={lines.query} page={lines.page} onPage={lines.setPage} empty="No lines."
                columns={[
                  { header: 'Member', cell: memberCell },
                  { header: 'Type', cell: typeCell },
                  { header: 'Account', cell: accountCell },
                  { header: 'Month', cell: (t) => <span className="whitespace-nowrap">{formatPeriod(t.period)}</span> },
                  { header: 'Amount', align: 'right', cell: amountCell },
                  { header: 'Status', cell: (t) => <StatusBadge status={t.status} label={t.status_label} /> },
                ]} />
            </div>
          );
        }}
      </QueryState>
    </>
  );
}
