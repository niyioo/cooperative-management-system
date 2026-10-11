import { useState } from 'react';
import { Link, Outlet, useParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { ArrowLeft, Plus } from 'lucide-react';
import { adminApi } from '../../../api/admin';
import DataTable from '../../../components/officer/DataTable';
import { FilterBar, FilterSelect, SearchInput } from '../../../components/officer/Filters';
import FormModal from '../../../components/officer/FormModal';
import MemberPicker from '../../../components/officer/MemberPicker';
import Tabs from '../../../components/officer/Tabs';
import useList from '../../../components/officer/useList';
import useReference from '../../../components/officer/useReference';
import { Alert } from '../../../components/ui/Alert';
import { StatusBadge } from '../../../components/ui/Badge';
import { CheckboxField, SelectField, TextAreaField, TextField } from '../../../components/ui/Field';
import PageHeader from '../../../components/ui/PageHeader';
import QueryState from '../../../components/ui/QueryState';
import StatCard from '../../../components/ui/StatCard';
import { Money } from '../../../components/ui/Table';
import { INVESTMENT_STATUS, today } from '../../../lib/choices';
import { formatDate, formatDateTime, formatNaira } from '../../../lib/format';
import { P, useCan } from '../../../lib/permissions';

export function InvestmentsLayout() {
  const can = useCan();
  return (
    <>
      <PageHeader title="Investments" description="Members' investment accounts, yearly returns that fund dividends, and investment products." />
      <Tabs tabs={[
        { to: '/admin/investments', label: 'Accounts', end: true },
        { to: '/admin/investments/returns', label: 'Returns' },
        { to: '/admin/investments/products', label: 'Products', show: can(P.MANAGE_INVESTMENT_PRODUCTS) },
      ]} />
      <Outlet />
    </>
  );
}

function OpenAccountButton() {
  const [member, setMember] = useState(null);
  const products = useReference('investmentProducts', { is_active: true });
  return (
    <FormModal trigger="Open account" triggerIcon={Plus} title="Open an investment account" submitLabel="Open account"
      defaultValues={{ product: '' }} transform={(v) => ({ ...v, member: member?.id })}
      onSubmit={adminApi.investmentAccounts.create} onDone={() => setMember(null)}
      renderFields={({ register, errors }) => (
        <>
          <MemberPicker value={member} onChange={setMember} required error={errors.member?.message} />
          <SelectField label="Product" required {...register('product', { required: 'Choose a product.' })} error={errors.product?.message}>
            <option value="">Choose…</option>
            {(products.data || []).map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
          </SelectField>
        </>
      )} />
  );
}

export function InvestmentAccounts() {
  const can = useCan();
  const products = useReference('investmentProducts');
  const list = useList(['admin', 'investment-accounts'], adminApi.investmentAccounts.list, { search: '', product: '', status: '' });
  return (
    <DataTable title="Investment accounts" action={can(P.MANAGE_INVESTMENT_ACCOUNTS) && <OpenAccountButton />}
      query={list.query} page={list.page} onPage={list.setPage} empty="No investment accounts match."
      toolbar={
        <FilterBar>
          <SearchInput value={list.filters.search} onChange={(v) => list.setFilter('search', v)} placeholder="Account number, member name or number" />
          <FilterSelect label="Product" value={list.filters.product} onChange={(v) => list.setFilter('product', v)} options={(products.data || []).map((p) => [p.id, p.name])} />
          <FilterSelect label="Status" value={list.filters.status} onChange={(v) => list.setFilter('status', v)} options={INVESTMENT_STATUS} />
        </FilterBar>
      }
      columns={[
        { header: 'Account', cell: (a) => <Link to={`/admin/investments/accounts/${a.id}`} className="font-semibold text-brand-600 hover:underline">{a.account_number}</Link> },
        { header: 'Member', cell: (a) => <><p className="font-medium text-slate-900">{a.member.full_name}</p><p className="text-xs text-slate-500">{a.member.membership_number}</p></> },
        { header: 'Product', cell: (a) => a.product_name },
        { header: 'Opened', cell: (a) => formatDate(a.opened_on) },
        { header: 'Principal', align: 'right', cell: (a) => <Money value={a.principal} className="font-semibold" /> },
        { header: 'Status', cell: (a) => <StatusBadge status={a.status} label={a.status_label} /> },
      ]} />
  );
}

export function InvestmentAccountDetail() {
  const { id } = useParams();
  const can = useCan();
  const account = useQuery({ queryKey: ['admin', 'investment-account', id], queryFn: () => adminApi.investmentAccounts.get(id) });
  const history = useList(['admin', 'investment-account', id, 'transactions'], (params) => adminApi.investmentAccounts.sub(id, 'transactions', params));
  return (
    <>
      <Link to="/admin/investments" className="inline-flex items-center gap-1 text-sm font-medium text-brand-600 hover:underline">
        <ArrowLeft className="h-4 w-4" aria-hidden="true" /> Investment accounts
      </Link>
      <QueryState query={account}>
        {(a) => (
          <div className="mt-3 space-y-6">
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div>
                <div className="flex items-center gap-2"><h2 className="text-xl font-bold text-slate-900">{a.account_number}</h2><StatusBadge status={a.status} label={a.status_label} /></div>
                <p className="text-sm text-slate-500"><Link to={`/admin/members/${a.member.id}`} className="font-medium text-brand-600 hover:underline">{a.member.full_name}</Link> · {a.product_name}</p>
              </div>
              {a.status === 'ACTIVE' && can(P.POST_INVESTMENT_TRANSACTION) && (
                <div className="flex flex-wrap gap-2">
                  <FormModal trigger="Record contribution" title={`Contribution · ${a.account_number}`} submitLabel="Record"
                    defaultValues={{ amount: '', value_date: today(), external_reference: '', description: '' }}
                    onSubmit={(v) => adminApi.investmentAccounts.action(a.id, 'contributions', v)}
                    renderFields={({ register, errors }) => (
                      <>
                        <TextField label="Amount (₦)" required inputMode="decimal" {...register('amount', { required: 'Enter an amount.' })} error={errors.amount?.message} />
                        <TextField label="Value date" type="date" max={today()} {...register('value_date')} error={errors.value_date?.message} />
                        <TextField label="Payment reference" {...register('external_reference')} error={errors.external_reference?.message} />
                        <TextField label="Description" {...register('description')} error={errors.description?.message} />
                      </>
                    )} />
                  <FormModal trigger="Liquidate" triggerVariant="secondary" title={`Liquidation · ${a.account_number}`} submitLabel="Record liquidation"
                    defaultValues={{ amount: a.principal, reason: '', value_date: today() }}
                    onSubmit={(v) => adminApi.investmentAccounts.action(a.id, 'liquidations', v)}
                    renderFields={({ register, errors }) => (
                      <>
                        <Alert tone="warning">Only products that allow officer liquidation accept this, after any lock-in. Liquidating the full principal closes the account once posted.</Alert>
                        <TextField label="Amount (₦)" required inputMode="decimal" {...register('amount', { required: 'Enter an amount.' })} error={errors.amount?.message} />
                        <TextField label="Value date" type="date" max={today()} {...register('value_date')} error={errors.value_date?.message} />
                        <TextAreaField label="Reason" required rows={2} {...register('reason', { required: 'Give a reason.' })} error={errors.reason?.message} />
                      </>
                    )} />
                </div>
              )}
            </div>
            <div className="grid gap-4 sm:grid-cols-3">
              <StatCard label="Principal" value={formatNaira(a.principal)} tone="violet" />
              <StatCard label="Opened" value={formatDate(a.opened_on)} tone="slate" />
              <StatCard label="Closed" value={formatDate(a.closed_on)} tone="slate" />
            </div>
            <DataTable title="Transactions" query={history.query} page={history.page} onPage={history.setPage} empty="No transactions yet."
              columns={[
                { header: 'Date', cell: (t) => <span className="whitespace-nowrap">{formatDate(t.value_date)}</span> },
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

export function InvestmentReturns() {
  const can = useCan();
  const products = useReference('investmentProducts');
  const list = useList(['admin', 'investment-returns'], adminApi.investmentReturns.list, { product: '' });
  return (
    <DataTable title="Investment returns" description="What each investment earned in a financial year; used to set the dividend rate."
      action={can(P.POST_INVESTMENT_TRANSACTION) && (
        <FormModal trigger="Record return" triggerIcon={Plus} title="Record an investment return" submitLabel="Record"
          defaultValues={{ product: '', financial_year: new Date().getFullYear(), amount_earned: '', description: '' }}
          transform={(v) => ({ ...v, financial_year: Number(v.financial_year) })}
          onSubmit={adminApi.investmentReturns.create}
          renderFields={({ register, errors }) => (
            <>
              <SelectField label="Product" required {...register('product', { required: 'Choose a product.' })} error={errors.product?.message}>
                <option value="">Choose…</option>
                {(products.data || []).map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
              </SelectField>
              <div className="grid gap-4 sm:grid-cols-2">
                <TextField label="Financial year" type="number" required {...register('financial_year', { required: 'Required.' })} error={errors.financial_year?.message} />
                <TextField label="Amount earned (₦)" required inputMode="decimal" {...register('amount_earned', { required: 'Required.' })} error={errors.amount_earned?.message} />
              </div>
              <TextField label="Description" {...register('description')} error={errors.description?.message} />
            </>
          )} />
      )}
      query={list.query} page={list.page} onPage={list.setPage} empty="No returns recorded."
      toolbar={<FilterBar><FilterSelect label="Product" value={list.filters.product} onChange={(v) => list.setFilter('product', v)} options={(products.data || []).map((p) => [p.id, p.name])} /></FilterBar>}
      columns={[
        { header: 'Year', cell: (r) => <span className="font-semibold">{r.financial_year}</span> },
        { header: 'Product', cell: (r) => r.product_name },
        { header: 'Amount earned', align: 'right', cell: (r) => <Money value={r.amount_earned} className="font-semibold" /> },
        { header: 'Description', cell: (r) => r.description || '—' },
        { header: 'Recorded', cell: (r) => <span className="text-xs">{formatDateTime(r.created_at)}<br />{r.recorded_by}</span> },
      ]} />
  );
}

const PRODUCT_DEFAULTS = { name: '', code: '', description: '', min_amount: '0', lock_in_months: '', dividend_eligible: true, allow_officer_liquidation: false, is_active: true };

function ProductForm({ product }) {
  return (
    <FormModal
      trigger={product ? 'Edit' : 'New product'} triggerIcon={product ? undefined : Plus} triggerVariant={product ? 'ghost' : 'primary'} triggerSize={product ? 'sm' : 'md'}
      title={product ? `Edit ${product.name}` : 'New investment product'}
      defaultValues={product ? { ...PRODUCT_DEFAULTS, ...product, lock_in_months: product.lock_in_months ?? '' } : PRODUCT_DEFAULTS}
      transform={({ id, ...v }) => ({ ...v, lock_in_months: v.lock_in_months === '' ? null : Number(v.lock_in_months) })}
      onSubmit={(data) => (product ? adminApi.investmentProducts.update(product.id, data) : adminApi.investmentProducts.create(data))}
      renderFields={({ register, errors }) => (
        <>
          <div className="grid gap-4 sm:grid-cols-2">
            <TextField label="Name" required {...register('name', { required: 'Required.' })} error={errors.name?.message} />
            <TextField label="Code" required {...register('code', { required: 'Required.' })} error={errors.code?.message} />
            <TextField label="Minimum amount (₦)" inputMode="decimal" {...register('min_amount')} error={errors.min_amount?.message} />
            <TextField label="Lock-in (months)" type="number" {...register('lock_in_months')} error={errors.lock_in_months?.message} hint="Blank for none" />
          </div>
          <TextField label="Description" {...register('description')} error={errors.description?.message} />
          <CheckboxField label="Earns dividends" {...register('dividend_eligible')} />
          <CheckboxField label="Officers may liquidate" {...register('allow_officer_liquidation')} />
          <CheckboxField label="Active" {...register('is_active')} />
        </>
      )} />
  );
}

export function InvestmentProducts() {
  const list = useList(['admin', 'investment-products'], adminApi.investmentProducts.list);
  return (
    <DataTable title="Investment products" action={<ProductForm />} query={list.query} page={list.page} onPage={list.setPage}
      columns={[
        { header: 'Product', cell: (p) => <><p className="font-semibold text-slate-900">{p.name}</p><p className="text-xs text-slate-500">{p.code}</p></> },
        { header: 'Minimum', align: 'right', cell: (p) => <Money value={p.min_amount} /> },
        { header: 'Lock-in', cell: (p) => (p.lock_in_months ? `${p.lock_in_months} months` : 'None') },
        { header: 'Dividends', cell: (p) => (p.dividend_eligible ? 'Yes' : 'No') },
        { header: 'Status', cell: (p) => <StatusBadge status={p.is_active ? 'ACTIVE' : 'INACTIVE'} /> },
        { header: '', align: 'right', cell: (p) => <ProductForm product={p} /> },
      ]} />
  );
}
