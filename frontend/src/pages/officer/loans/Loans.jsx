import { Link, useParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { ArrowLeft, Plus } from 'lucide-react';
import { adminApi } from '../../../api/admin';
import ActionButton from '../../../components/officer/ActionButton';
import DataTable from '../../../components/officer/DataTable';
import { FilterBar, FilterDate, FilterSelect, SearchInput } from '../../../components/officer/Filters';
import FormModal from '../../../components/officer/FormModal';
import useList from '../../../components/officer/useList';
import useReference from '../../../components/officer/useReference';
import { Alert } from '../../../components/ui/Alert';
import { StatusBadge } from '../../../components/ui/Badge';
import { Card, CardHeader } from '../../../components/ui/Card';
import { CheckboxField, SelectField, TextField } from '../../../components/ui/Field';
import QueryState from '../../../components/ui/QueryState';
import StatCard from '../../../components/ui/StatCard';
import { Money, Table, Td, Th } from '../../../components/ui/Table';
import { INTEREST_COLLECTION, INTEREST_METHOD, LOAN_STATUS, RATE_BASIS, currentPeriod, label, options, today } from '../../../lib/choices';
import { formatDate, formatNaira } from '../../../lib/format';
import { P, useCan } from '../../../lib/permissions';

const memberCell = (m) => (
  <Link to={`/admin/members/${m.id}`} className="group block">
    <span className="font-medium text-slate-900 group-hover:underline">{m.full_name}</span>
    <span className="block text-xs text-slate-500">{m.membership_number}</span>
  </Link>
);

export function LoanList() {
  const products = useReference('loanProducts');
  const list = useList(['admin', 'loans'], adminApi.loans.list, { search: '', status: '', product: '', disbursed_from: '', disbursed_to: '' });
  return (
    <DataTable title="Loans" query={list.query} page={list.page} onPage={list.setPage} empty="No loans match."
      toolbar={
        <FilterBar>
          <SearchInput value={list.filters.search} onChange={(v) => list.setFilter('search', v)} placeholder="Reference, member name or number" />
          <FilterSelect label="Status" value={list.filters.status} onChange={(v) => list.setFilter('status', v)} options={LOAN_STATUS} />
          <FilterSelect label="Product" value={list.filters.product} onChange={(v) => list.setFilter('product', v)} options={(products.data || []).map((p) => [p.id, p.name])} />
          <FilterDate label="Disbursed from" value={list.filters.disbursed_from} onChange={(v) => list.setFilter('disbursed_from', v)} />
          <FilterDate label="Disbursed to" value={list.filters.disbursed_to} onChange={(v) => list.setFilter('disbursed_to', v)} />
        </FilterBar>
      }
      columns={[
        { header: 'Loan', cell: (l) => <Link to={`/admin/loans/${l.id}`} className="font-semibold text-brand-600 hover:underline">{l.reference}</Link> },
        { header: 'Member', cell: (l) => memberCell(l.member) },
        { header: 'Product', cell: (l) => <>{l.product_name}<p className="text-xs text-slate-500">{l.term_months} months</p></> },
        { header: 'Disbursed', cell: (l) => <span className="whitespace-nowrap">{formatDate(l.disbursed_on)}</span> },
        { header: 'Principal', align: 'right', cell: (l) => <Money value={l.principal} /> },
        { header: 'Outstanding', align: 'right', cell: (l) => <Money value={l.outstanding} className="font-semibold" /> },
        { header: 'Status', cell: (l) => <StatusBadge status={l.status} label={l.status_label} /> },
      ]} />
  );
}

export function OverdueLoans() {
  const list = useList(['admin', 'loans-overdue'], adminApi.loans.overdue);
  return (
    <DataTable title="Overdue loans" description="Running loans with at least one instalment past due (after the grace period), worst first." query={list.query} page={list.page} onPage={list.setPage} empty="No overdue loans."
      columns={[
        { header: 'Loan', cell: (l) => <Link to={`/admin/loans/${l.id}`} className="font-semibold text-brand-600 hover:underline">{l.reference}</Link> },
        { header: 'Member', cell: (l) => <>{memberCell(l.member)}<span className="text-xs text-slate-500">{l.member.phone}</span></> },
        { header: 'Product', cell: (l) => l.product_name },
        { header: 'Instalments', align: 'right', cell: (l) => l.arrears.instalments },
        { header: 'Days overdue', align: 'right', cell: (l) => <span className="font-semibold text-red-700">{l.arrears.days_overdue}</span> },
        { header: 'Arrears', align: 'right', cell: (l) => <Money value={l.arrears.amount} className="font-semibold text-red-700" /> },
        { header: 'Outstanding', align: 'right', cell: (l) => <Money value={l.outstanding} /> },
      ]} />
  );
}

export function LoanDetail() {
  const { id } = useParams();
  const can = useCan();
  const loan = useQuery({ queryKey: ['admin', 'loan', id], queryFn: () => adminApi.loans.get(id) });
  const repayments = useList(['admin', 'loan', id, 'repayments'], (params) => adminApi.loans.sub(id, 'repayments', params));
  return (
    <>
      <Link to="/admin/loans/active" className="inline-flex items-center gap-1 text-sm font-medium text-brand-600 hover:underline">
        <ArrowLeft className="h-4 w-4" aria-hidden="true" /> Loans
      </Link>
      <QueryState query={loan}>
        {(l) => {
          const running = ['ACTIVE', 'DEFAULTED'].includes(l.status);
          return (
            <div className="mt-3 space-y-6">
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div>
                  <div className="flex items-center gap-2"><h2 className="text-xl font-bold text-slate-900">{l.reference}</h2><StatusBadge status={l.status} label={l.status_label} /></div>
                  <p className="text-sm text-slate-500">
                    <Link to={`/admin/members/${l.member.id}`} className="font-medium text-brand-600 hover:underline">{l.member.full_name}</Link> · {l.product_name} ·
                    {' '}{Number(l.interest_rate)}% {label(RATE_BASIS, l.interest_rate_basis).toLowerCase()} ({label(INTEREST_METHOD, l.interest_method).toLowerCase()}) · {l.term_months} months
                    {l.application_reference && <> · application {l.application_reference}</>}
                  </p>
                </div>
                <div className="flex flex-wrap gap-2">
                  {running && can(P.RECORD_LOAN_REPAYMENT) && (
                    <FormModal trigger="Record repayment" title={`Repayment · ${l.reference}`} submitLabel="Record repayment"
                      defaultValues={{ amount: l.next_instalment?.remaining || '', value_date: today(), period: currentPeriod(), external_reference: '', description: '' }}
                      onSubmit={(v) => adminApi.loans.action(l.id, 'repayments', v)}
                      renderFields={({ register, errors }) => (
                        <>
                          <p className="text-sm text-slate-600">Outstanding {formatNaira(l.outstanding)}. Repayments settle penalties, then interest, then principal, oldest instalment first.</p>
                          <TextField label="Amount (₦)" required inputMode="decimal" {...register('amount', { required: 'Enter an amount.' })} error={errors.amount?.message} />
                          <div className="grid gap-4 sm:grid-cols-2">
                            <TextField label="Value date" type="date" max={today()} {...register('value_date')} error={errors.value_date?.message} />
                            <TextField label="For month" type="month" {...register('period')} error={errors.period?.message} />
                          </div>
                          <TextField label="Payment reference" {...register('external_reference')} error={errors.external_reference?.message} />
                          <TextField label="Description" {...register('description')} error={errors.description?.message} />
                        </>
                      )} />
                  )}
                  {l.status === 'ACTIVE' && can(P.MARK_LOAN_DEFAULT) && (
                    <ActionButton label="Mark as defaulted" variant="danger" input="required" description="Record that this loan is in default. Repayments can still be recorded."
                      action={(reason) => adminApi.loans.action(l.id, 'mark-default', { reason })} />
                  )}
                </div>
              </div>

              {l.status === 'PENDING_DISBURSEMENT' && (
                <Alert title="Disbursement awaiting approval">
                  The loan becomes active once a second officer approves the disbursement entry in{' '}
                  <Link to="/admin/transactions/pending" className="font-semibold underline">Transactions › Awaiting approval</Link>.
                </Alert>
              )}

              {Number(l.arrears.amount) > 0 && (
                <Alert tone="warning" title="Repayments overdue">
                  {formatNaira(l.arrears.amount)} across {l.arrears.instalments} instalment(s); oldest due {formatDate(l.arrears.oldest_due_date)} ({l.arrears.days_overdue} days).
                </Alert>
              )}

              <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
                <StatCard label="Principal" value={formatNaira(l.principal)} hint={`Disbursed ${formatDate(l.disbursed_on)}`} />
                <StatCard label="Interest" value={formatNaira(l.total_interest)} hint={label(INTEREST_COLLECTION, l.interest_collection)} />
                <StatCard label="Outstanding" value={formatNaira(l.outstanding)} tone="amber" hint={`Matures ${formatDate(l.maturity_date)}`} />
                <StatCard label="Next instalment" value={l.next_instalment ? formatNaira(l.next_instalment.remaining) : '—'} tone="slate"
                  hint={l.next_instalment ? `Due ${formatDate(l.next_instalment.due_date)}` : 'Nothing due'} />
              </div>

              <Card>
                <CardHeader title="Repayment schedule" />
                <Table caption="Repayment schedule">
                  <thead><tr><Th>#</Th><Th>Due</Th><Th align="right">Principal</Th><Th align="right">Interest</Th><Th align="right">Total</Th><Th align="right">Paid</Th><Th align="right">Remaining</Th><Th>Status</Th></tr></thead>
                  <tbody className="divide-y divide-slate-100">
                    {l.schedule.map((r) => (
                      <tr key={r.number}>
                        <Td>{r.number}</Td>
                        <Td className="whitespace-nowrap">{formatDate(r.due_date)}</Td>
                        <Td align="right"><Money value={r.principal_due} /></Td>
                        <Td align="right"><Money value={r.interest_due} /></Td>
                        <Td align="right"><Money value={r.total_due} className="font-semibold" /></Td>
                        <Td align="right"><Money value={r.paid} /></Td>
                        <Td align="right"><Money value={r.remaining} /></Td>
                        <Td><StatusBadge status={r.status} /></Td>
                      </tr>
                    ))}
                  </tbody>
                </Table>
              </Card>

              <DataTable title="Repayments" query={repayments.query} page={repayments.page} onPage={repayments.setPage} empty="No repayments yet."
                columns={[
                  { header: 'Date', cell: (r) => <span className="whitespace-nowrap">{formatDate(r.value_date)}</span> },
                  { header: 'Reference', cell: (r) => <>{r.reference}<p className="text-xs text-slate-500">{r.description}</p></> },
                  { header: 'Amount', align: 'right', cell: (r) => <Money value={r.amount} className="font-semibold" /> },
                  { header: 'Principal', align: 'right', cell: (r) => <Money value={r.principal_component} /> },
                  { header: 'Interest', align: 'right', cell: (r) => <Money value={r.interest_component} /> },
                  { header: 'Penalty', align: 'right', cell: (r) => <Money value={r.penalty_component} /> },
                  { header: 'Status', cell: (r) => <StatusBadge status={r.status} /> },
                ]} />
            </div>
          );
        }}
      </QueryState>
    </>
  );
}

const PRODUCT_DEFAULTS = {
  name: '', code: '', description: '', interest_rate: '', interest_rate_basis: 'PER_ANNUM', interest_method: 'FLAT', interest_collection: 'AMORTISED',
  min_amount: '0', max_amount: '', max_savings_multiple: '', min_term_months: 1, max_term_months: 12, allowed_terms: '',
  min_membership_months: 0, max_active_loans: 1, guarantors_required: 1, required_documents: '', allow_topup: false, is_active: true,
};

function ProductForm({ product }) {
  const initial = product
    ? { ...PRODUCT_DEFAULTS, ...product, max_savings_multiple: product.max_savings_multiple || '', allowed_terms: product.allowed_terms.join(', '), required_documents: product.required_documents.join('\n') }
    : PRODUCT_DEFAULTS;
  return (
    <FormModal
      trigger={product ? 'Edit' : 'New product'} triggerIcon={product ? undefined : Plus} triggerVariant={product ? 'ghost' : 'primary'} triggerSize={product ? 'sm' : 'md'}
      title={product ? `Edit ${product.name}` : 'New loan product'} defaultValues={initial}
      transform={(v) => {
        const { id, ...data } = v;
        ['min_term_months', 'max_term_months', 'min_membership_months', 'max_active_loans', 'guarantors_required'].forEach((k) => { data[k] = Number(data[k]); });
        data.max_savings_multiple = data.max_savings_multiple || null;
        data.allowed_terms = String(data.allowed_terms).split(',').map((t) => t.trim()).filter(Boolean).map(Number);
        data.required_documents = String(data.required_documents).split('\n').map((t) => t.trim()).filter(Boolean);
        return data;
      }}
      onSubmit={(data) => (product ? adminApi.loanProducts.update(product.id, data) : adminApi.loanProducts.create(data))}
      renderFields={({ register, errors }) => (
        <div className="max-h-[60vh] space-y-4 overflow-y-auto pr-1">
          <div className="grid gap-4 sm:grid-cols-2">
            <TextField label="Name" required {...register('name', { required: 'Required.' })} error={errors.name?.message} />
            <TextField label="Code" required {...register('code', { required: 'Required.' })} error={errors.code?.message} />
          </div>
          <TextField label="Description" {...register('description')} error={errors.description?.message} />
          <div className="grid gap-4 sm:grid-cols-2">
            <TextField label="Interest rate (%)" required inputMode="decimal" {...register('interest_rate', { required: 'Required.' })} error={errors.interest_rate?.message} />
            <SelectField label="Rate applies" {...register('interest_rate_basis')}>{options(RATE_BASIS)}</SelectField>
            <SelectField label="Interest method" {...register('interest_method')}>{options(INTEREST_METHOD)}</SelectField>
            <SelectField label="Interest collected" {...register('interest_collection')}>{options(INTEREST_COLLECTION)}</SelectField>
            <TextField label="Minimum amount (₦)" inputMode="decimal" {...register('min_amount')} error={errors.min_amount?.message} />
            <TextField label="Maximum amount (₦)" required inputMode="decimal" {...register('max_amount', { required: 'Required.' })} error={errors.max_amount?.message} />
            <TextField label="Max multiple of savings" inputMode="decimal" {...register('max_savings_multiple')} error={errors.max_savings_multiple?.message} hint="e.g. 2 = twice eligible savings; blank for no limit" />
            <TextField label="Allowed terms (months)" {...register('allowed_terms')} error={errors.allowed_terms?.message} hint="Comma-separated, e.g. 6, 12, 18; blank for any" />
            <TextField label="Minimum term (months)" type="number" {...register('min_term_months')} error={errors.min_term_months?.message} />
            <TextField label="Maximum term (months)" type="number" {...register('max_term_months')} error={errors.max_term_months?.message} />
            <TextField label="Minimum membership (months)" type="number" {...register('min_membership_months')} error={errors.min_membership_months?.message} />
            <TextField label="Max running loans of this product" type="number" {...register('max_active_loans')} error={errors.max_active_loans?.message} />
            <TextField label="Guarantors required" type="number" min={1} hint="At least one" {...register('guarantors_required', { min: { value: 1, message: 'Every loan needs at least one guarantor.' } })} error={errors.guarantors_required?.message} />
          </div>
          <label className="block text-sm font-medium text-slate-700">
            Required documents <span className="font-normal text-slate-500">(one per line)</span>
            <textarea rows={3} {...register('required_documents')} className="mt-1 block w-full rounded-lg border border-slate-300 px-3 py-2 text-sm" />
          </label>
          <CheckboxField label="Allow top-up of a running loan" {...register('allow_topup')} />
          <CheckboxField label="Active (open to applications)" {...register('is_active')} />
        </div>
      )} />
  );
}

export function LoanProducts() {
  const list = useList(['admin', 'loan-products'], adminApi.loanProducts.list);
  return (
    <DataTable title="Loan products" action={<ProductForm />} query={list.query} page={list.page} onPage={list.setPage}
      columns={[
        { header: 'Product', cell: (p) => <><p className="font-semibold text-slate-900">{p.name}</p><p className="text-xs text-slate-500">{p.code}</p></> },
        { header: 'Interest', cell: (p) => <>{Number(p.interest_rate)}% {label(RATE_BASIS, p.interest_rate_basis).toLowerCase()}<p className="text-xs text-slate-500">{label(INTEREST_METHOD, p.interest_method)}</p></> },
        { header: 'Amount', align: 'right', cell: (p) => <span className="whitespace-nowrap"><Money value={p.min_amount} /> – <Money value={p.max_amount} /></span> },
        { header: 'Term', cell: (p) => `${p.min_term_months}–${p.max_term_months} months` },
        { header: 'Guarantors', align: 'right', cell: (p) => p.guarantors_required },
        { header: 'Status', cell: (p) => <StatusBadge status={p.is_active ? 'ACTIVE' : 'INACTIVE'} /> },
        { header: '', align: 'right', cell: (p) => <ProductForm product={p} /> },
      ]} />
  );
}
