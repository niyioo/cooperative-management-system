import { Link, useNavigate, useParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { ArrowLeft, Plus } from 'lucide-react';
import { adminApi } from '../../../api/admin';
import ActionButton from '../../../components/officer/ActionButton';
import DataTable from '../../../components/officer/DataTable';
import { FilterBar, FilterSelect, SearchInput } from '../../../components/officer/Filters';
import FormModal from '../../../components/officer/FormModal';
import useList from '../../../components/officer/useList';
import useReference from '../../../components/officer/useReference';
import { StatusBadge } from '../../../components/ui/Badge';
import { Card, CardHeader } from '../../../components/ui/Card';
import EmptyState from '../../../components/ui/EmptyState';
import Pagination from '../../../components/ui/Pagination';
import { CheckboxField, SelectField, TextField } from '../../../components/ui/Field';
import QueryState from '../../../components/ui/QueryState';
import StatCard from '../../../components/ui/StatCard';
import { Money, Table, Td, Th } from '../../../components/ui/Table';
import { CYCLE_STATUS, MONTHS, SAVINGS_KIND, label, options, today } from '../../../lib/choices';
import { formatAmount, formatDate, formatNaira, monthLabel, monthsInclusive } from '../../../lib/format';
import { P, useCan } from '../../../lib/permissions';

export function SavingsCycles() {
  const can = useCan();
  const cycleProducts = useReference('savingsProducts', { kind: 'CYCLE' });
  const list = useList(['admin', 'savings-cycles'], adminApi.savingsCycles.list, { status: '', year: '' });
  return (
    <DataTable
      title="Cycles"
      description="Each year's Christmas Savings runs January–October and pays out after it closes."
      action={can(P.MANAGE_SAVINGS_CYCLES) && (
        <FormModal trigger="New cycle" triggerIcon={Plus} title="Create a savings cycle" submitLabel="Create cycle"
          defaultValues={{ product: '', year: new Date().getFullYear() + 1, expected_monthly_contribution: '' }}
          transform={(v) => ({ ...v, year: Number(v.year), ...(v.expected_monthly_contribution ? {} : { expected_monthly_contribution: undefined }) })}
          onSubmit={adminApi.savingsCycles.create}
          renderFields={({ register, errors }) => (
            <>
              <SelectField label="Product" required {...register('product', { required: 'Choose a product.' })} error={errors.product?.message}>
                <option value="">Choose…</option>
                {(cycleProducts.data || []).map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
              </SelectField>
              <TextField label="Year" type="number" required {...register('year', { required: 'Required.' })} error={errors.year?.message} />
              <TextField label="Expected monthly contribution (₦)" inputMode="decimal" {...register('expected_monthly_contribution')} error={errors.expected_monthly_contribution?.message} hint="Leave blank to use the product's amount." />
            </>
          )} />
      )}
      query={list.query} page={list.page} onPage={list.setPage} empty="No cycles yet."
      toolbar={
        <FilterBar>
          <FilterSelect label="Status" value={list.filters.status} onChange={(v) => list.setFilter('status', v)} options={CYCLE_STATUS} />
          <SearchInput value={list.filters.year} onChange={(v) => list.setFilter('year', v)} placeholder="Year" label="Year" />
        </FilterBar>
      }
      columns={[
        { header: 'Cycle', cell: (c) => <Link to={`/admin/savings/cycles/${c.id}`} className="font-semibold text-brand-600 hover:underline">{c.name}</Link> },
        { header: 'Window', cell: (c) => <span className="whitespace-nowrap">{formatDate(c.start_date)} – {formatDate(c.end_date)}</span> },
        { header: 'Accounts', align: 'right', cell: (c) => c.account_count },
        { header: 'Saved', align: 'right', cell: (c) => <Money value={c.total_saved} className="font-semibold" /> },
        { header: 'Status', cell: (c) => <StatusBadge status={c.status} label={c.status_label} /> },
      ]}
    />
  );
}

export function SavingsCycleDetail() {
  const { id } = useParams();
  const can = useCan();
  const navigate = useNavigate();
  const cycle = useQuery({ queryKey: ['admin', 'savings-cycle', id], queryFn: () => adminApi.savingsCycles.get(id) });
  const grid = useList(['admin', 'savings-cycle', id, 'grid'], (params) => adminApi.savingsCycles.sub(id, 'grid', params), { search: '' });

  return (
    <>
      <Link to="/admin/savings/cycles" className="inline-flex items-center gap-1 text-sm font-medium text-brand-600 hover:underline">
        <ArrowLeft className="h-4 w-4" aria-hidden="true" /> Cycles
      </Link>
      <QueryState query={cycle}>
        {(c) => (
          <div className="mt-3 space-y-6">
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div>
                <div className="flex items-center gap-2"><h2 className="text-xl font-bold text-slate-900">{c.name}</h2><StatusBadge status={c.status} label={c.status_label} /></div>
                <p className="text-sm text-slate-500">{formatDate(c.start_date)} – {formatDate(c.end_date)} · expected {formatNaira(c.expected_monthly_contribution)} a month</p>
              </div>
              <div className="flex flex-wrap gap-2">
                {c.status === 'UPCOMING' && can(P.MANAGE_SAVINGS_CYCLES) && (
                  <ActionButton label="Open cycle" description="Members' contributions can be recorded against this cycle once it is open." action={() => adminApi.savingsCycles.action(c.id, 'open')} />
                )}
                {c.status === 'OPEN' && can(P.CLOSE_SAVINGS_CYCLE) && (
                  <ActionButton label="Close cycle" variant="danger" description="No further contributions will be accepted. You can then pay the savings out." action={() => adminApi.savingsCycles.action(c.id, 'close')} />
                )}
                {c.status === 'CLOSED' && can([P.MANAGE_BATCHES]) && can(P.POST_SAVINGS_WITHDRAWAL) && (
                  <ActionButton label="Prepare payout" description="Creates a payout batch for every account with a balance. A second officer must approve it before money is paid out."
                    action={() => adminApi.savingsCycles.action(c.id, 'payout', { value_date: today() })}
                    onDone={(batch) => navigate(`/admin/transactions/batches/${batch.id}`)} />
                )}
              </div>
            </div>
            <div className="grid gap-4 sm:grid-cols-3">
              <StatCard label="Accounts" value={c.account_count} />
              <StatCard label="Total saved" value={formatNaira(c.total_saved)} tone="green" />
              <StatCard label="Expected per account" value={formatNaira(Number(c.expected_monthly_contribution) * monthsInclusive(c.start_date, c.end_date))} hint={`${monthsInclusive(c.start_date, c.end_date)} months × expected monthly`} tone="slate" />
            </div>
            <Card>
              <CardHeader title="Contribution grid" description="Posted contributions per member per month. Reversals net out in the month they belong to."
                action={<div className="w-64"><SearchInput value={grid.filters.search} onChange={(v) => grid.setFilter('search', v)} placeholder="Filter members" /></div>} />
              <QueryState query={grid.query}>
                {({ results: g, count }) => g.rows.length ? (
                  <>
                  <Table caption="Christmas savings contribution grid">
                    <thead>
                      <tr>
                        <Th className="sticky left-0 z-10">Member</Th>
                        {g.months.map((m) => <Th key={m} align="right">{monthLabel(m)}</Th>)}
                        <Th align="right">Other</Th><Th align="right">Total</Th><Th align="right">Expected</Th><Th align="right">Paid out</Th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100">
                      {g.rows.map((r) => (
                        <tr key={r.account_id} className="hover:bg-slate-50">
                          <Td className="sticky left-0 z-10 whitespace-nowrap bg-white">
                            <Link to={`/admin/savings/accounts/${r.account_id}`} className="font-medium text-slate-900 hover:text-brand-600 hover:underline">{r.member_name}</Link>
                            <p className="text-xs text-slate-500">{r.membership_number}</p>
                          </Td>
                          {g.months.map((m) => (
                            <Td key={m} align="right" className={`tabular ${Number(r.months[m]) ? '' : 'text-slate-300'}`}>{Number(r.months[m]) ? formatAmount(r.months[m]) : '—'}</Td>
                          ))}
                          <Td align="right" className="tabular">{Number(r.other) ? formatAmount(r.other) : '—'}</Td>
                          <Td align="right" className={`tabular font-semibold ${Number(r.total) < Number(r.expected_total) ? 'text-amber-700' : 'text-emerald-700'}`}>{formatAmount(r.total)}</Td>
                          <Td align="right" className="tabular text-slate-500">{formatAmount(r.expected_total)}</Td>
                          <Td align="right" className="tabular">{Number(r.paid_out) ? formatAmount(r.paid_out) : '—'}</Td>
                        </tr>
                      ))}
                    </tbody>
                    <tfoot className="border-t-2 border-slate-200 bg-slate-50 font-semibold">
                      <tr>
                        <Td className="sticky left-0 bg-slate-50">{count > g.rows.length ? 'Page total' : 'Total'}</Td>
                        {g.months.map((m) => <Td key={m} align="right" className="tabular">{formatAmount(g.totals[m])}</Td>)}
                        <Td align="right" className="tabular">{formatAmount(g.totals.other)}</Td>
                        <Td align="right" className="tabular">{formatAmount(g.totals.total)}</Td>
                        <Td />
                        <Td align="right" className="tabular">{formatAmount(g.totals.paid_out)}</Td>
                      </tr>
                    </tfoot>
                  </Table>
                  <Pagination page={grid.page} count={count} onChange={grid.setPage} />
                  </>
                ) : <EmptyState title="No accounts in this cycle yet" />}
              </QueryState>
            </Card>
          </div>
        )}
      </QueryState>
    </>
  );
}

const PRODUCT_DEFAULTS = {
  name: '', code: '', description: '', kind: 'REGULAR', cycle_start_month: 1, cycle_end_month: 10, payout_month: 12,
  expected_monthly_contribution: '0', min_contribution: '0', max_monthly_contribution: '', allow_contribution_outside_window: false, allow_multiple_contributions_per_period: true,
  min_membership_months: 0, is_mandatory: false, allow_officer_withdrawal: false, allow_member_withdrawal_request: false,
  counts_toward_loan_eligibility: true, is_active: true, display_order: 0,
};

function ProductForm({ product }) {
  return (
    <FormModal
      trigger={product ? 'Edit' : 'New product'} triggerIcon={product ? undefined : Plus} triggerVariant={product ? 'ghost' : 'primary'} triggerSize={product ? 'sm' : 'md'}
      title={product ? `Edit ${product.name}` : 'New savings product'}
      defaultValues={product ? { ...PRODUCT_DEFAULTS, ...product } : PRODUCT_DEFAULTS}
      transform={(v) => {
        const data = { ...v };
        ['cycle_start_month', 'cycle_end_month', 'payout_month'].forEach((k) => { data[k] = data.kind === 'CYCLE' ? Number(data[k]) : null; });
        ['min_membership_months', 'display_order'].forEach((k) => { data[k] = Number(data[k]); });
        data.max_monthly_contribution = data.max_monthly_contribution === '' || data.max_monthly_contribution === null ? null : data.max_monthly_contribution;
        delete data.id; delete data.kind_label;
        return data;
      }}
      onSubmit={(data) => (product ? adminApi.savingsProducts.update(product.id, data) : adminApi.savingsProducts.create(data))}
      renderFields={({ register, errors, watch }) => (
        <div className="max-h-[60vh] space-y-4 overflow-y-auto pr-1">
          <div className="grid gap-4 sm:grid-cols-2">
            <TextField label="Name" required {...register('name', { required: 'Required.' })} error={errors.name?.message} />
            <TextField label="Code" required {...register('code', { required: 'Required.' })} error={errors.code?.message} />
          </div>
          <TextField label="Description" {...register('description')} error={errors.description?.message} />
          <SelectField label="Kind" {...register('kind')} error={errors.kind?.message} disabled={!!product}>{options(SAVINGS_KIND)}</SelectField>
          {watch('kind') === 'CYCLE' && (
            <div className="grid gap-4 sm:grid-cols-3">
              <SelectField label="Starts" {...register('cycle_start_month')}>{options(MONTHS)}</SelectField>
              <SelectField label="Ends" {...register('cycle_end_month')}>{options(MONTHS)}</SelectField>
              <SelectField label="Pays out" {...register('payout_month')}>{options(MONTHS)}</SelectField>
            </div>
          )}
          <div className="grid gap-4 sm:grid-cols-2">
            <TextField label="Expected monthly (₦)" inputMode="decimal" {...register('expected_monthly_contribution')} error={errors.expected_monthly_contribution?.message} />
            <TextField label="Minimum contribution (₦)" inputMode="decimal" {...register('min_contribution')} error={errors.min_contribution?.message} />
            <TextField label="Maximum monthly contribution (₦)" inputMode="decimal" {...register('max_monthly_contribution')} error={errors.max_monthly_contribution?.message}
              hint="The most a member may choose to contribute each month. Blank means no limit." />
            <TextField label="Minimum membership (months)" type="number" {...register('min_membership_months')} error={errors.min_membership_months?.message} />
            <TextField label="Display order" type="number" {...register('display_order')} error={errors.display_order?.message} />
          </div>
          <div className="grid gap-2">
            <CheckboxField label="Mandatory for every member" {...register('is_mandatory')} />
            <CheckboxField label="Counts toward loan eligibility" {...register('counts_toward_loan_eligibility')} />
            <CheckboxField label="Allow more than one contribution per month" {...register('allow_multiple_contributions_per_period')} />
            {watch('kind') === 'CYCLE' && <CheckboxField label="Accept contributions outside the cycle window" {...register('allow_contribution_outside_window')} />}
            <CheckboxField label="Officers may record withdrawals" {...register('allow_officer_withdrawal')} />
            <CheckboxField label="Members may request withdrawals (needs the cooperative setting too)" {...register('allow_member_withdrawal_request')} />
            <CheckboxField label="Active" {...register('is_active')} />
          </div>
        </div>
      )} />
  );
}

export function SavingsProducts() {
  const list = useList(['admin', 'savings-products'], adminApi.savingsProducts.list);
  return (
    <DataTable title="Savings products" action={<ProductForm />} query={list.query} page={list.page} onPage={list.setPage}
      columns={[
        { header: 'Product', cell: (p) => <><p className="font-semibold text-slate-900">{p.name}</p><p className="text-xs text-slate-500">{p.code}</p></> },
        { header: 'Kind', cell: (p) => <>{p.kind_label}{p.kind === 'CYCLE' && <p className="text-xs text-slate-500">{label(MONTHS, p.cycle_start_month)} – {label(MONTHS, p.cycle_end_month)}</p>}</> },
        { header: 'Expected monthly', align: 'right', cell: (p) => <Money value={p.expected_monthly_contribution} /> },
        { header: 'Loan collateral', cell: (p) => (p.counts_toward_loan_eligibility ? 'Yes' : 'No') },
        { header: 'Status', cell: (p) => <StatusBadge status={p.is_active ? 'ACTIVE' : 'INACTIVE'} /> },
        { header: '', align: 'right', cell: (p) => <ProductForm product={p} /> },
      ]} />
  );
}
