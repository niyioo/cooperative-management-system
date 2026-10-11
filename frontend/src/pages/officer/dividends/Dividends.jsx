import { Link, useNavigate, useParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { ArrowLeft, Plus } from 'lucide-react';
import { adminApi } from '../../../api/admin';
import ActionButton from '../../../components/officer/ActionButton';
import DataTable from '../../../components/officer/DataTable';
import DetailList from '../../../components/officer/DetailList';
import { FilterBar, FilterSelect, SearchInput } from '../../../components/officer/Filters';
import FormModal from '../../../components/officer/FormModal';
import useList from '../../../components/officer/useList';
import useReference from '../../../components/officer/useReference';
import { Alert } from '../../../components/ui/Alert';
import { StatusBadge } from '../../../components/ui/Badge';
import { Card, CardBody, CardHeader } from '../../../components/ui/Card';
import { SelectField, TextAreaField, TextField } from '../../../components/ui/Field';
import PageHeader from '../../../components/ui/PageHeader';
import QueryState from '../../../components/ui/QueryState';
import StatCard from '../../../components/ui/StatCard';
import { Money } from '../../../components/ui/Table';
import { DIVIDEND_BASIS, DIVIDEND_PAYMENT, DIVIDEND_STATUS, label, options, today } from '../../../lib/choices';
import { formatDate, formatDateTime, formatNaira } from '../../../lib/format';
import { P, useCan } from '../../../lib/permissions';

const STEPS = ['DRAFT', 'CALCULATED', 'APPROVED', 'PUBLISHED', 'PAID'];

function CycleForm({ cycle }) {
  const savings = useReference('savingsProducts');
  const investments = useReference('investmentProducts', { dividend_eligible: true });
  const year = new Date().getFullYear();
  const defaults = cycle
    ? { ...cycle, eligible_investment_products: cycle.eligible_investment_products.map(String), eligible_savings_products: cycle.eligible_savings_products.map(String), distributable_surplus: cycle.distributable_surplus || '', credit_savings_product: cycle.credit_savings_product || '' }
    : { financial_year: year, rate: '', basis: 'CLOSING_BALANCE', cutoff_date: `${year}-12-31`, eligible_investment_products: [], eligible_savings_products: [], distributable_surplus: '', withholding_rate: '0', payment_method: 'CREDIT_TO_SAVINGS', credit_savings_product: '', notes: '' };
  const checkboxes = (register, name, items) => (
    <div className="grid gap-1 rounded-lg border border-slate-200 p-3 sm:grid-cols-2">
      {items.map((p) => (
        <label key={p.id} className="flex items-center gap-2 text-sm text-slate-700">
          <input type="checkbox" value={p.id} {...register(name)} className="h-4 w-4 rounded border-slate-300 text-brand-600" /> {p.name}
        </label>
      ))}
      {!items.length && <p className="text-xs text-slate-500">No products.</p>}
    </div>
  );
  return (
    <FormModal
      trigger={cycle ? 'Edit' : 'New dividend cycle'} triggerIcon={cycle ? undefined : Plus} triggerVariant={cycle ? 'secondary' : 'primary'}
      title={cycle ? `Edit ${cycle.financial_year} dividend` : 'New dividend cycle'} defaultValues={defaults}
      transform={(v) => ({
        financial_year: Number(v.financial_year), rate: v.rate, basis: v.basis, cutoff_date: v.cutoff_date,
        eligible_investment_products: [].concat(v.eligible_investment_products || []), eligible_savings_products: [].concat(v.eligible_savings_products || []),
        distributable_surplus: v.distributable_surplus || null, withholding_rate: v.withholding_rate || '0', payment_method: v.payment_method,
        credit_savings_product: v.payment_method === 'CREDIT_TO_SAVINGS' ? v.credit_savings_product || null : null, notes: v.notes,
      })}
      onSubmit={(data) => (cycle ? adminApi.dividendCycles.update(cycle.id, data) : adminApi.dividendCycles.create(data))}
      renderFields={({ register, errors, watch }) => (
        <div className="max-h-[60vh] space-y-4 overflow-y-auto pr-1">
          <div className="grid gap-4 sm:grid-cols-2">
            <TextField label="Financial year" type="number" required {...register('financial_year', { required: 'Required.' })} error={errors.financial_year?.message} />
            <TextField label="Dividend rate (%)" required inputMode="decimal" {...register('rate', { required: 'Required.' })} error={errors.rate?.message} />
            <SelectField label="Calculated on" {...register('basis')} error={errors.basis?.message}>{options(DIVIDEND_BASIS)}</SelectField>
            <TextField label="Cut-off date" type="date" {...register('cutoff_date')} error={errors.cutoff_date?.message} />
            <TextField label="Distributable surplus (₦)" inputMode="decimal" {...register('distributable_surplus')} error={errors.distributable_surplus?.message} hint="Optional cap; calculation fails if the total exceeds it" />
            <TextField label="Withholding tax (%)" inputMode="decimal" {...register('withholding_rate')} error={errors.withholding_rate?.message} />
          </div>
          <div>
            <p className="mb-1 text-sm font-medium text-slate-700">Investment products that earn dividends</p>
            {checkboxes(register, 'eligible_investment_products', investments.data || [])}
            {errors.eligible_investment_products && <p className="mt-1 text-xs text-red-600">{errors.eligible_investment_products.message}</p>}
          </div>
          <div>
            <p className="mb-1 text-sm font-medium text-slate-700">Savings products that earn dividends</p>
            {checkboxes(register, 'eligible_savings_products', savings.data || [])}
          </div>
          <SelectField label="Payment" {...register('payment_method')} error={errors.payment_method?.message}>{options(DIVIDEND_PAYMENT)}</SelectField>
          {watch('payment_method') === 'CREDIT_TO_SAVINGS' && (
            <SelectField label="Credit to savings product" {...register('credit_savings_product')} error={errors.credit_savings_product?.message}>
              <option value="">Choose…</option>
              {(savings.data || []).filter((p) => p.kind === 'REGULAR').map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
            </SelectField>
          )}
          <TextAreaField label="Notes" rows={2} {...register('notes')} error={errors.notes?.message} />
        </div>
      )} />
  );
}

export function DividendCycles() {
  const can = useCan();
  const list = useList(['admin', 'dividend-cycles'], adminApi.dividendCycles.list, { status: '' });
  return (
    <>
      <PageHeader title="Dividends" description="Dividends are processed in December: calculate, approve, publish to members, then pay." actions={can(P.MANAGE_DIVIDEND_CYCLES) && <CycleForm />} />
      <DataTable query={list.query} page={list.page} onPage={list.setPage} empty="No dividend cycles yet."
        toolbar={
          <FilterBar>
            <FilterSelect label="Status" value={list.filters.status} onChange={(v) => list.setFilter('status', v)} options={DIVIDEND_STATUS} />
          </FilterBar>
        }
        columns={[
          { header: 'Year', cell: (c) => <Link to={`/admin/dividends/${c.id}`} className="font-semibold text-brand-600 hover:underline">{c.financial_year} dividend</Link> },
          { header: 'Reference', cell: (c) => c.reference },
          { header: 'Rate', align: 'right', cell: (c) => `${Number(c.rate)}%` },
          { header: 'Basis', cell: (c) => c.basis_label },
          { header: 'Net total', align: 'right', cell: (c) => (c.latest_run ? <Money value={c.latest_run.total_net} className="font-semibold" /> : '—') },
          { header: 'Status', cell: (c) => <StatusBadge status={c.status} label={c.status_label} /> },
        ]} />
    </>
  );
}

export function DividendCycleDetail() {
  const { id } = useParams();
  const can = useCan();
  const navigate = useNavigate();
  const cycle = useQuery({ queryKey: ['admin', 'dividend-cycle', id], queryFn: () => adminApi.dividendCycles.get(id) });
  const runs = useQuery({ queryKey: ['admin', 'dividend-cycle', id, 'runs'], queryFn: () => adminApi.dividendCycles.sub(id, 'runs') });
  const members = useList(['admin', 'dividend-cycle', id, 'members'], (params) => adminApi.dividendCycles.sub(id, 'member-dividends', params), { search: '' });

  return (
    <>
      <Link to="/admin/dividends" className="inline-flex items-center gap-1 text-sm font-medium text-brand-600 hover:underline">
        <ArrowLeft className="h-4 w-4" aria-hidden="true" /> Dividends
      </Link>
      <QueryState query={cycle}>
        {(c) => {
          const run = c.latest_run;
          return (
            <div className="mt-3 space-y-6">
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div>
                  <div className="flex items-center gap-2"><h1 className="text-2xl font-bold text-slate-900">{c.financial_year} dividend</h1><StatusBadge status={c.status} label={c.status_label} /></div>
                  <p className="text-sm text-slate-500">{c.reference} · {Number(c.rate)}% on {c.basis_label.toLowerCase()} at {formatDate(c.cutoff_date)}</p>
                </div>
                <div className="flex flex-wrap gap-2">
                  {['DRAFT', 'CALCULATED'].includes(c.status) && can(P.MANAGE_DIVIDEND_CYCLES) && <CycleForm cycle={c} />}
                  {['DRAFT', 'CALCULATED'].includes(c.status) && can(P.CALCULATE_DIVIDENDS) && (
                    <ActionButton label={c.status === 'DRAFT' ? 'Calculate' : 'Recalculate'} description="Works out every member's dividend from posted balances. A recalculation replaces the previous run, which is kept for the record."
                      action={() => adminApi.dividendCycles.action(c.id, 'calculate')} />
                  )}
                  {c.status === 'CALCULATED' && can(P.APPROVE_DIVIDENDS) && (
                    <ActionButton label="Approve" description={`Approve ${run ? formatNaira(run.total_net) : 'the calculated'} net dividends for ${run?.member_count ?? ''} members. The officer who calculated cannot approve.`}
                      action={() => adminApi.dividendCycles.action(c.id, 'approve')} />
                  )}
                  {c.status === 'APPROVED' && can(P.APPROVE_DIVIDENDS) && (
                    <ActionButton label="Publish to members" description="Members will see their dividend in the portal." action={() => adminApi.dividendCycles.action(c.id, 'publish')} />
                  )}
                  {['APPROVED', 'PUBLISHED'].includes(c.status) && can(P.PAY_DIVIDENDS) && can(P.MANAGE_BATCHES) && (
                    <ActionButton label="Prepare payment" description={c.payment_method === 'CREDIT_TO_SAVINGS' ? 'Creates a batch crediting each member’s savings. A second officer approves it before posting.' : 'Creates a payment batch to record the external transfers. A second officer approves it before posting.'}
                      action={() => adminApi.dividendCycles.action(c.id, 'pay', { value_date: today() })} onDone={(batch) => navigate(`/admin/transactions/batches/${batch.id}`)} />
                  )}
                  {!['PAID', 'CANCELLED'].includes(c.status) && can(P.MANAGE_DIVIDEND_CYCLES) && (
                    <ActionButton label="Cancel cycle" variant="danger" input="required" description="Cancel this dividend cycle. It stays on record." action={(reason) => adminApi.dividendCycles.action(c.id, 'cancel', { reason })} />
                  )}
                </div>
              </div>

              {c.status !== 'CANCELLED' && (
                <ol className="flex flex-wrap gap-2 text-xs font-semibold" aria-label="Progress">
                  {STEPS.map((s, i) => {
                    const done = STEPS.indexOf(c.status) >= i;
                    return <li key={s} className={`rounded-full px-3 py-1 ${done ? 'bg-brand-600 text-white' : 'bg-slate-100 text-slate-500'}`} aria-current={c.status === s ? 'step' : undefined}>{i + 1}. {label(DIVIDEND_STATUS, s)}</li>;
                  })}
                </ol>
              )}

              {run && (
                <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
                  <StatCard label="Members" value={run.member_count} />
                  <StatCard label="Total basis" value={formatNaira(run.total_basis)} tone="slate" />
                  <StatCard label="Gross dividend" value={formatNaira(run.total_gross)} tone="green" hint={`Withholding ${formatNaira(run.total_withholding)}`} />
                  <StatCard label="Net payable" value={formatNaira(run.total_net)} tone="violet" />
                </div>
              )}
              {!run && c.status === 'DRAFT' && <Alert>Not calculated yet. Check the settings, then calculate.</Alert>}

              <div className="grid gap-6 lg:grid-cols-3">
                <div className="lg:col-span-2">
                  <DataTable title="Member dividends" description={run ? `Run ${run.run_number}` : undefined} query={members.query} page={members.page} onPage={members.setPage} empty="No dividends calculated."
                    toolbar={<SearchInput value={members.filters.search} onChange={(v) => members.setFilter('search', v)} placeholder="Member name or number" />}
                    columns={[
                      { header: 'Member', cell: (d) => <><p className="font-medium text-slate-900">{d.member.full_name}</p><p className="text-xs text-slate-500">{d.member.membership_number}</p></> },
                      { header: 'Basis', align: 'right', cell: (d) => <Money value={d.basis_amount} /> },
                      { header: 'Gross', align: 'right', cell: (d) => <Money value={d.gross_amount} /> },
                      { header: 'Tax', align: 'right', cell: (d) => <Money value={d.withholding_amount} /> },
                      { header: 'Net', align: 'right', cell: (d) => <Money value={d.net_amount} className="font-semibold" /> },
                      { header: 'Status', cell: (d) => <StatusBadge status={d.status} label={d.status_label} /> },
                    ]} />
                </div>
                <div className="space-y-6">
                  <Card>
                    <CardHeader title="Settings" />
                    <CardBody>
                      <DetailList columns={1} items={[
                        ['Payment', label(DIVIDEND_PAYMENT, c.payment_method)],
                        ['Withholding tax', `${Number(c.withholding_rate)}%`],
                        ['Distributable surplus', c.distributable_surplus && formatNaira(c.distributable_surplus)],
                        ['Approved', c.approved_by && `${c.approved_by} · ${formatDateTime(c.approved_at)}`],
                        ['Published', formatDateTime(c.published_at)],
                        ['Paid', formatDateTime(c.paid_at)],
                        ['Notes', c.notes],
                      ]} />
                    </CardBody>
                  </Card>
                  <Card>
                    <CardHeader title="Calculation runs" />
                    <QueryState query={runs}>
                      {(data) => (
                        <ul className="divide-y divide-slate-100">
                          {(data.results || data).map((r) => (
                            <li key={r.id} className="px-5 py-3 text-sm">
                              <div className="flex justify-between gap-2"><span className="font-medium">Run {r.run_number}</span><StatusBadge status={r.status} label={r.status_label} /></div>
                              <p className="text-xs text-slate-500">{r.run_by} · {formatDateTime(r.created_at)} · {r.member_count} members · net {formatNaira(r.total_net)}</p>
                            </li>
                          ))}
                          {!(data.results || data).length && <li className="px-5 py-3 text-sm text-slate-500">No runs yet.</li>}
                        </ul>
                      )}
                    </QueryState>
                  </Card>
                </div>
              </div>
            </div>
          );
        }}
      </QueryState>
    </>
  );
}
