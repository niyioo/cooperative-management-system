import { useState } from 'react';
import { Link, Outlet, useParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { ArrowLeft, Plus } from 'lucide-react';
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
import { Alert } from '../../../components/ui/Alert';
import { StatusBadge } from '../../../components/ui/Badge';
import { Card, CardBody } from '../../../components/ui/Card';
import { SelectField, TextAreaField, TextField } from '../../../components/ui/Field';
import PageHeader from '../../../components/ui/PageHeader';
import QueryState from '../../../components/ui/QueryState';
import StatCard from '../../../components/ui/StatCard';
import { Money } from '../../../components/ui/Table';
import { SAVINGS_ACCOUNT_STATUS, currentPeriod, today } from '../../../lib/choices';
import { formatDate, formatNaira, formatPeriod } from '../../../lib/format';
import { P, useCan } from '../../../lib/permissions';
import { MonthlyContributionPanel } from './MonthlyDeductions';

export function SavingsLayout() {
  const can = useCan();
  return (
    <>
      <PageHeader title="Savings" description="Christmas Savings (January–October) is kept separate from other savings. Members cannot withdraw through the portal." />
      <Tabs tabs={[
        { to: '/admin/savings', label: 'Accounts', end: true },
        { to: '/admin/savings/deductions', label: 'Monthly deductions' },
        { to: '/admin/savings/cycles', label: 'Christmas Savings cycles' },
        { to: '/admin/savings/products', label: 'Products', show: can(P.MANAGE_SAVINGS_PRODUCTS) },
      ]} />
      <Outlet />
    </>
  );
}

/** Contribution dialog; used from the account list and the account page. */
export function ContributeButton({ account, size = 'sm' }) {
  return (
    <FormModal trigger="Contribute" triggerSize={size} title={`Record a contribution · ${account.account_number}`} submitLabel="Record contribution"
      defaultValues={{ amount: '', period: currentPeriod(), value_date: today(), description: '', external_reference: '' }}
      onSubmit={(v) => adminApi.contribute({ ...v, account: account.id })}
      renderFields={({ register, errors }) => (
        <>
          <p className="text-sm text-slate-600">{account.member.full_name} · {account.product_name}{account.cycle_name ? ` (${account.cycle_name})` : ''}</p>
          <TextField label="Amount (₦)" required inputMode="decimal" {...register('amount', { required: 'Enter an amount.' })} error={errors.amount?.message} />
          <div className="grid gap-4 sm:grid-cols-2">
            <TextField label="For month" type="month" {...register('period')} error={errors.period?.message} />
            <TextField label="Value date" type="date" max={today()} {...register('value_date')} error={errors.value_date?.message} />
          </div>
          <TextField label="Payment reference" {...register('external_reference')} error={errors.external_reference?.message} hint="e.g. payroll deduction or bank teller number" />
          <TextField label="Description" {...register('description')} error={errors.description?.message} />
        </>
      )} />
  );
}

function WithdrawButton({ account }) {
  return (
    <FormModal trigger="Withdraw" triggerVariant="secondary" triggerSize="sm" title={`Officer withdrawal · ${account.account_number}`} submitLabel="Record withdrawal"
      defaultValues={{ amount: '', reason: '', value_date: today() }}
      onSubmit={(v) => adminApi.withdraw({ ...v, account: account.id })}
      renderFields={({ register, errors }) => (
        <>
          <Alert tone="warning">Only products that allow officer withdrawals accept this. Depending on settings, a second officer must approve it before it is posted.</Alert>
          <TextField label="Amount (₦)" required inputMode="decimal" {...register('amount', { required: 'Enter an amount.' })} error={errors.amount?.message} />
          <TextField label="Value date" type="date" max={today()} {...register('value_date')} error={errors.value_date?.message} />
          <TextAreaField label="Reason" required rows={2} {...register('reason', { required: 'Give a reason.' })} error={errors.reason?.message} />
        </>
      )} />
  );
}

function OpenAccountButton() {
  const [member, setMember] = useState(null);
  const products = useReference('savingsProducts', { is_active: true });
  return (
    <FormModal trigger="Open account" triggerIcon={Plus} title="Open a savings account" submitLabel="Open account"
      defaultValues={{ product: '', year: new Date().getFullYear(), elected_monthly_amount: '' }}
      transform={(v) => {
        const product = products.data?.find((p) => p.id === v.product);
        return { member: member?.id, product: v.product, ...(product?.kind === 'CYCLE' ? { year: Number(v.year) } : {}), elected_monthly_amount: v.elected_monthly_amount || null };
      }}
      onSubmit={adminApi.savingsAccounts.create}
      onDone={() => setMember(null)}
      renderFields={({ register, errors, watch }) => {
        const product = products.data?.find((p) => p.id === watch('product'));
        return (
          <>
            <MemberPicker value={member} onChange={setMember} required error={errors.member?.message} />
            <SelectField label="Product" required {...register('product', { required: 'Choose a product.' })} error={errors.product?.message}>
              <option value="">Choose…</option>
              {(products.data || []).map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
            </SelectField>
            {product?.kind === 'CYCLE' && <TextField label="Cycle year" type="number" {...register('year')} error={errors.year?.message} />}
            <TextField label="Elected monthly amount (₦)" inputMode="decimal" {...register('elected_monthly_amount')} error={errors.elected_monthly_amount?.message}
              hint={product ? `Leave blank to use the product's expected ${formatNaira(product.expected_monthly_contribution)}.` : undefined} />
          </>
        );
      }} />
  );
}

export function SavingsAccounts() {
  const can = useCan();
  const products = useReference('savingsProducts');
  const list = useList(['admin', 'savings-accounts'], adminApi.savingsAccounts.list, { search: '', product: '', status: '' });
  return (
    <DataTable
      title="Savings accounts"
      action={can(P.POST_SAVINGS_CONTRIBUTION) && <OpenAccountButton />}
      query={list.query} page={list.page} onPage={list.setPage} empty="No savings accounts match."
      toolbar={
        <FilterBar>
          <SearchInput value={list.filters.search} onChange={(v) => list.setFilter('search', v)} placeholder="Account number, member name or number" />
          <FilterSelect label="Product" value={list.filters.product} onChange={(v) => list.setFilter('product', v)} options={(products.data || []).map((p) => [p.id, p.name])} />
          <FilterSelect label="Status" value={list.filters.status} onChange={(v) => list.setFilter('status', v)} options={SAVINGS_ACCOUNT_STATUS} />
        </FilterBar>
      }
      columns={[
        { header: 'Account', cell: (a) => <Link to={`/admin/savings/accounts/${a.id}`} className="font-semibold text-brand-600 hover:underline">{a.account_number}</Link> },
        { header: 'Member', cell: (a) => <><p className="font-medium text-slate-900">{a.member.full_name}</p><p className="text-xs text-slate-500">{a.member.membership_number}</p></> },
        { header: 'Product', cell: (a) => <>{a.product_name}{a.cycle_name && <p className="text-xs text-slate-500">{a.cycle_name}</p>}</> },
        { header: 'Balance', align: 'right', cell: (a) => <Money value={a.balance} className="font-semibold" /> },
        { header: 'Status', cell: (a) => <StatusBadge status={a.status} label={a.status_label} /> },
        { header: '', align: 'right', cell: (a) => can(P.POST_SAVINGS_CONTRIBUTION) && a.status === 'ACTIVE' && <ContributeButton account={a} /> },
      ]}
    />
  );
}

export function SavingsAccountDetail() {
  const { id } = useParams();
  const can = useCan();
  const account = useQuery({ queryKey: ['admin', 'savings-account', id], queryFn: () => adminApi.savingsAccounts.get(id) });
  const history = useList(['admin', 'savings-account', id, 'transactions'], (params) => adminApi.savingsAccounts.sub(id, 'transactions', params));
  return (
    <>
      <Link to="/admin/savings" className="inline-flex items-center gap-1 text-sm font-medium text-brand-600 hover:underline">
        <ArrowLeft className="h-4 w-4" aria-hidden="true" /> Savings accounts
      </Link>
      <QueryState query={account}>
        {(a) => (
          <div className="mt-3 space-y-6">
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div>
                <div className="flex items-center gap-2">
                  <h2 className="text-xl font-bold text-slate-900">{a.account_number}</h2>
                  <StatusBadge status={a.status} label={a.status_label} />
                </div>
                <p className="text-sm text-slate-500">
                  <Link to={`/admin/members/${a.member.id}`} className="font-medium text-brand-600 hover:underline">{a.member.full_name}</Link> · {a.product_name}{a.cycle_name ? ` · ${a.cycle_name}` : ''}
                </p>
              </div>
              <div className="flex flex-wrap gap-2">
                {can(P.POST_SAVINGS_CONTRIBUTION) && a.status === 'ACTIVE' && <ContributeButton account={a} size="md" />}
                {can(P.POST_SAVINGS_WITHDRAWAL) && a.status === 'ACTIVE' && <WithdrawButton account={a} />}
                {can(P.POST_SAVINGS_CONTRIBUTION) && a.status !== 'CLOSED' && (
                  <ActionButton variant="secondary" label={a.status === 'FROZEN' ? 'Unfreeze' : 'Freeze'}
                    description={a.status === 'FROZEN' ? 'Allow contributions to this account again.' : 'Stop new contributions to this account. The balance is unaffected.'}
                    action={() => adminApi.savingsAccounts.update(a.id, { status: a.status === 'FROZEN' ? 'ACTIVE' : 'FROZEN' })} />
                )}
              </div>
            </div>
            <div className="grid gap-4 sm:grid-cols-3">
              <StatCard label="Balance" value={formatNaira(a.balance)} tone="green" />
              <StatCard label="Elected monthly amount" value={formatNaira(a.elected_monthly_amount)} hint={a.elected_monthly_amount ? 'The latest amount chosen' : 'Product default applies'} tone="slate" />
              <Card><CardBody><DetailList columns={1} items={[['Opened', formatDate(a.opened_on)], ['Closed', formatDate(a.closed_on)]]} /></CardBody></Card>
            </div>
            <MonthlyContributionPanel account={a} />
            <DataTable title="Transactions" query={history.query} page={history.page} onPage={history.setPage} empty="No transactions yet."
              columns={[
                { header: 'Date', cell: (t) => <span className="whitespace-nowrap">{formatDate(t.value_date)}</span> },
                { header: 'Month', cell: (t) => <span className="whitespace-nowrap">{formatPeriod(t.period)}</span> },
                { header: 'Type', cell: (t) => <><p>{t.type_label}</p><p className="text-xs text-slate-500">{t.reference}{t.description ? ` · ${t.description}` : ''}</p></> },
                { header: 'Amount', align: 'right', cell: (t) => <Money value={t.signed_amount} className={Number(t.signed_amount) < 0 ? 'text-red-700' : ''} /> },
                { header: 'Status', cell: (t) => <StatusBadge status={t.status} label={t.status_label} /> },
              ]} />
          </div>
        )}
      </QueryState>
    </>
  );
}

