import { useEffect, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Link, useParams } from 'react-router-dom';
import { ArrowLeft, Camera, Download, KeyRound, Mail, Pencil, Plus, ShieldCheck, Trash2, UserRound } from 'lucide-react';
import { adminApi } from '../../../api/admin';
import ActionButton from '../../../components/officer/ActionButton';
import DataTable from '../../../components/officer/DataTable';
import DetailList from '../../../components/officer/DetailList';
import FormModal from '../../../components/officer/FormModal';
import Tabs from '../../../components/officer/Tabs';
import useList from '../../../components/officer/useList';
import { Alert, ErrorAlert } from '../../../components/ui/Alert';
import { StatusBadge } from '../../../components/ui/Badge';
import Button from '../../../components/ui/Button';
import { Card, CardBody, CardHeader } from '../../../components/ui/Card';
import EmptyState from '../../../components/ui/EmptyState';
import { CheckboxField, SelectField, TextField } from '../../../components/ui/Field';
import QueryState from '../../../components/ui/QueryState';
import StatCard from '../../../components/ui/StatCard';
import { Money, Table, Td, Th } from '../../../components/ui/Table';
import { DOCUMENT_TYPES, EMPLOYMENT, GENDERS, MARITAL, label, options } from '../../../lib/choices';
import { saveBlob } from '../../../lib/download';
import { formatDate, formatDateTime, formatNaira } from '../../../lib/format';
import { P, useCan } from '../../../lib/permissions';

// Status actions offered for each member status (mirrors members.services.STATUS_TRANSITIONS).
const STATUS_ACTIONS = {
  PENDING: [['activate', 'Activate', false], ['deactivate', 'Deactivate', true]],
  ACTIVE: [['suspend', 'Suspend', true], ['deactivate', 'Deactivate', true]],
  SUSPENDED: [['reinstate', 'Reinstate', false], ['deactivate', 'Deactivate', true]],
  INACTIVE: [['reactivate', 'Reactivate', false]],
  CLOSED: [],
};

function Photo({ member }) {
  const [url, setUrl] = useState(null);
  useEffect(() => {
    if (!member.has_photo) return undefined;
    let objectUrl;
    let cancelled = false;
    adminApi.members.photo(member.id).then((res) => {
      if (cancelled) return;
      objectUrl = URL.createObjectURL(res.data);
      setUrl(objectUrl);
    }).catch(() => {});
    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [member.id, member.has_photo, member.updated_at]);
  return url ? (
    <img src={url} alt={`Photo of ${member.full_name}`} className="h-16 w-16 rounded-full object-cover ring-2 ring-white" />
  ) : (
    <span className="flex h-16 w-16 items-center justify-center rounded-full bg-brand-100 text-brand-600"><UserRound className="h-8 w-8" aria-hidden="true" /></span>
  );
}

function PhotoUpload({ member }) {
  const queryClient = useQueryClient();
  const mutation = useMutation({
    mutationFn: (file) => adminApi.members.uploadPhoto(member.id, file),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['admin', 'member', member.id] }),
  });
  return (
    <>
      <label className="inline-flex cursor-pointer items-center gap-1 text-xs font-semibold text-brand-600 hover:underline">
        <Camera className="h-3.5 w-3.5" aria-hidden="true" /> {mutation.isPending ? 'Uploading…' : member.has_photo ? 'Change photo' : 'Add photo'}
        <input type="file" accept="image/jpeg,image/png" className="sr-only" onChange={(e) => e.target.files[0] && mutation.mutate(e.target.files[0])} />
      </label>
      <ErrorAlert error={mutation.error} className="mt-2" />
    </>
  );
}

function Overview({ m }) {
  return (
    <div className="grid gap-6 lg:grid-cols-3">
      <div className="space-y-6 lg:col-span-2">
        <Card>
          <CardHeader title="Personal & contact" />
          <CardBody>
            <DetailList columns={3} items={[
              ['Full name', m.full_name], ['Gender', label(GENDERS, m.gender)], ['Date of birth', formatDate(m.date_of_birth)],
              ['Marital status', label(MARITAL, m.marital_status)], ['Phone', m.phone], ['Alternative phone', m.alt_phone],
              ['Email', m.portal.has_email ? m.email : ''], ['State of origin', m.state_of_origin], ['LGA', m.lga],
              ['Residential address', m.residential_address],
            ]} />
          </CardBody>
        </Card>
        <Card>
          <CardHeader title="Employment & membership" />
          <CardBody>
            <DetailList columns={3} items={[
              ['Staff number', m.staff_number], ['IPPIS number', m.ippis_number], ['Department', m.department?.name],
              ['Unit', m.unit], ['Designation', m.designation], ['Grade level', m.grade_level],
              ['Employment date', formatDate(m.employment_date)], ['Employment status', label(EMPLOYMENT, m.employment_status)],
              ['Date joined', formatDate(m.date_joined)],
            ]} />
          </CardBody>
        </Card>
        <Card>
          <CardHeader title="Bank details" description="Used for payouts and dividend transfers." />
          <CardBody>
            <DetailList columns={3} items={[['Bank', m.bank_name], ['Account number', m.bank_account_number], ['Account name', m.bank_account_name]]} />
          </CardBody>
        </Card>
      </div>
      <div className="space-y-6">
        <Card>
          <CardHeader title="Portal access" />
          <CardBody>
            <DetailList columns={1} items={[
              ['Sign-in email', m.portal.has_email ? 'Yes' : 'No email on file'],
              ['Account set up', m.portal.activated ? 'Yes' : 'Not yet'],
              ['Login enabled', m.portal.is_active ? 'Yes' : 'No'],
              ['Last sign-in', formatDateTime(m.portal.last_login)],
            ]} />
          </CardBody>
        </Card>
        {m.status_reason && (
          <Alert tone="warning" title="Status reason">{m.status_reason}</Alert>
        )}
        <Card>
          <CardHeader title="Record" />
          <CardBody>
            <DetailList columns={1} items={[['Registered by', m.created_by], ['Registered', formatDateTime(m.created_at)], ['Last updated', formatDateTime(m.updated_at)]]} />
          </CardBody>
        </Card>
      </div>
    </div>
  );
}

function AccountTable({ title, rows, columns }) {
  return (
    <Card>
      <CardHeader title={title} />
      {rows.length ? (
        <Table caption={title}>
          <thead><tr>{columns.map(([h, , align]) => <Th key={h} align={align}>{h}</Th>)}</tr></thead>
          <tbody className="divide-y divide-slate-100">
            {rows.map((r) => <tr key={r.id || r.cycle_reference}>{columns.map(([h, cell, align]) => <Td key={h} align={align}>{cell(r)}</Td>)}</tr>)}
          </tbody>
        </Table>
      ) : <EmptyState title="None" />}
    </Card>
  );
}

function Finances({ id }) {
  const summary = useQuery({ queryKey: ['admin', 'member', id, 'finance'], queryFn: () => adminApi.members.sub(id, 'financial-summary') });
  return (
    <QueryState query={summary}>
      {(s) => (
        <div className="space-y-6">
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            {s.savings && <StatCard label={`Christmas savings ${s.savings.christmas.year}`} value={formatNaira(s.savings.christmas.balance)} tone="green" />}
            {s.savings && <StatCard label="Other savings" value={formatNaira(s.savings.other.balance)} hint={`Total ${formatNaira(s.savings.total)}`} />}
            {s.loans && <StatCard label="Loans outstanding" value={formatNaira(s.loans.outstanding)} tone="amber" hint={`${s.loans.active_count} active · ${s.loans.open_applications} open application(s)`} />}
            {s.investments && <StatCard label="Investments" value={formatNaira(s.investments.total_principal)} tone="violet" />}
          </div>
          {!s.savings && !s.loans && !s.investments && !s.dividends && (
            <Alert>Your role does not include access to members' balances.</Alert>
          )}
          {s.savings && (
            <AccountTable title="Savings accounts" rows={[...s.savings.christmas.accounts, ...s.savings.other.accounts]} columns={[
              ['Account', (a) => <><p className="font-medium">{a.product}{a.year ? ` ${a.year}` : ''}</p><p className="text-xs text-slate-500">{a.account_number}</p></>],
              ['Status', (a) => <StatusBadge status={a.status} />],
              ['Balance', (a) => <Money value={a.balance} className="font-semibold" />, 'right'],
            ]} />
          )}
          {s.loans && (
            <AccountTable title="Loans" rows={s.loans.loans} columns={[
              ['Loan', (l) => <Link to={`/admin/loans/${l.id}`} className="font-medium text-brand-600 hover:underline">{l.reference}</Link>],
              ['Product', (l) => l.product],
              ['Disbursed', (l) => formatDate(l.disbursed_on)],
              ['Principal', (l) => <Money value={l.principal} />, 'right'],
              ['Outstanding', (l) => <Money value={l.outstanding} className="font-semibold" />, 'right'],
              ['Status', (l) => <StatusBadge status={l.status} />],
            ]} />
          )}
          {s.investments && (
            <AccountTable title="Investments" rows={s.investments.accounts} columns={[
              ['Account', (a) => <><p className="font-medium">{a.product}</p><p className="text-xs text-slate-500">{a.account_number}</p></>],
              ['Opened', (a) => formatDate(a.opened_on)],
              ['Status', (a) => <StatusBadge status={a.status} />],
              ['Principal', (a) => <Money value={a.principal} className="font-semibold" />, 'right'],
            ]} />
          )}
          {s.dividends && (
            <AccountTable title="Dividends" rows={s.dividends.history} columns={[
              ['Year', (d) => d.financial_year],
              ['Basis', (d) => <Money value={d.basis_amount} />, 'right'],
              ['Rate', (d) => `${Number(d.rate)}%`, 'right'],
              ['Net', (d) => <Money value={d.net_amount} className="font-semibold" />, 'right'],
              ['Status', (d) => <StatusBadge status={d.status} />],
            ]} />
          )}
        </div>
      )}
    </QueryState>
  );
}

function Transactions({ id }) {
  const list = useList(['admin', 'member', id, 'transactions'], (params) => adminApi.members.sub(id, 'transactions', params));
  return (
    <DataTable title="Transactions" description="Every ledger entry on this member's accounts." query={list.query} page={list.page} onPage={list.setPage} empty="No transactions yet."
      columns={[
        { header: 'Date', cell: (t) => <span className="whitespace-nowrap">{formatDate(t.value_date)}</span> },
        { header: 'Type', cell: (t) => <><p>{t.type_label}</p><p className="text-xs text-slate-500">{t.reference}</p></> },
        { header: 'Account', cell: (t) => <span className="text-xs">{t.account?.label} {t.account?.number}</span> },
        { header: 'Amount', align: 'right', cell: (t) => <Money value={t.signed_amount} className={Number(t.signed_amount) < 0 ? 'text-red-700' : ''} /> },
        { header: 'Status', cell: (t) => <StatusBadge status={t.status} label={t.status_label} /> },
      ]} />
  );
}

function Documents({ id }) {
  const can = useCan();
  const queryClient = useQueryClient();
  const docs = useQuery({ queryKey: ['admin', 'member', id, 'documents'], queryFn: () => adminApi.members.sub(id, 'documents') });
  const download = useMutation({ mutationFn: (doc) => adminApi.members.downloadDocument(id, doc.id).then((res) => saveBlob(res, doc.title || 'document')) });
  const manage = can(P.MANAGE_MEMBER_DOCUMENTS);
  return (
    <Card>
      <CardHeader title="Documents" action={manage && (
        <FormModal trigger="Upload document" triggerIcon={Plus} triggerSize="sm" title="Upload a document" submitLabel="Upload"
          defaultValues={{ document_type: 'ID_CARD', title: '', file: null }}
          onSubmit={(v) => adminApi.members.uploadDocument(id, { document_type: v.document_type, title: v.title, file: v.file?.[0] })}
          renderFields={({ register, errors }) => (
            <>
              <SelectField label="Document type" {...register('document_type')}>{options(DOCUMENT_TYPES)}</SelectField>
              <TextField label="Title" {...register('title')} error={errors.title?.message} />
              <TextField label="File" type="file" accept=".pdf,.jpg,.jpeg,.png" required {...register('file', { required: 'Choose a file.' })} error={errors.file?.message} hint="PDF, JPG or PNG." />
            </>
          )} />
      )} />
      <ErrorAlert error={download.error} className="m-4" />
      <QueryState query={docs}>
        {(data) => (Array.isArray(data) ? data : data.results).length ? (
          <Table caption="Documents">
            <thead><tr><Th>Document</Th><Th>Uploaded</Th><Th>Verified</Th><Th align="right">Actions</Th></tr></thead>
            <tbody className="divide-y divide-slate-100">
              {(Array.isArray(data) ? data : data.results).map((d) => (
                <tr key={d.id}>
                  <Td><p className="font-medium">{d.title || d.document_type_label}</p><p className="text-xs text-slate-500">{d.document_type_label}</p></Td>
                  <Td className="text-xs">{formatDateTime(d.created_at)}<br />{d.uploaded_by}</Td>
                  <Td className="text-xs">{d.verified_at ? <><ShieldCheck className="inline h-3.5 w-3.5 text-emerald-600" aria-hidden="true" /> {d.verified_by}</> : 'Not verified'}</Td>
                  <Td align="right">
                    <div className="flex justify-end gap-1">
                      <Button size="sm" variant="ghost" icon={Download} onClick={() => download.mutate(d)}>Download</Button>
                      {manage && !d.verified_at && (
                        <ActionButton size="sm" variant="secondary" label="Verify" description="Confirm you have checked this document against the original."
                          action={() => adminApi.members.verifyDocument(id, d.id)} />
                      )}
                      {manage && (
                        <ActionButton size="sm" variant="ghost" icon={Trash2} label="Remove" confirmVariant="danger" description="Remove this document? This is recorded in the audit log."
                          action={() => adminApi.members.removeDocument(id, d.id)} onDone={() => queryClient.invalidateQueries({ queryKey: ['admin', 'member', id] })} />
                      )}
                    </div>
                  </Td>
                </tr>
              ))}
            </tbody>
          </Table>
        ) : <EmptyState title="No documents uploaded" />}
      </QueryState>
    </Card>
  );
}

function NextOfKin({ m }) {
  const can = useCan();
  return (
    <Card>
      <CardHeader title="Next of kin" action={can(P.CHANGE_MEMBER) && (
        <FormModal trigger="Add next of kin" triggerIcon={Plus} triggerSize="sm"
          defaultValues={{ full_name: '', relationship: '', phone: '', email: '', address: '', is_primary: false }}
          onSubmit={(v) => adminApi.members.addNextOfKin(m.id, v)}
          renderFields={({ register, errors }) => (
            <>
              <TextField label="Full name" required {...register('full_name', { required: 'Required.' })} error={errors.full_name?.message} />
              <TextField label="Relationship" required {...register('relationship', { required: 'Required.' })} error={errors.relationship?.message} />
              <TextField label="Phone" type="tel" required {...register('phone', { required: 'Required.' })} error={errors.phone?.message} />
              <TextField label="Email" type="email" {...register('email')} error={errors.email?.message} />
              <TextField label="Address" {...register('address')} error={errors.address?.message} />
              <CheckboxField label="Primary next of kin" {...register('is_primary')} />
            </>
          )} />
      )} />
      {m.next_of_kin.length ? (
        <ul className="divide-y divide-slate-100">
          {m.next_of_kin.map((k) => (
            <li key={k.id} className="flex flex-wrap items-start justify-between gap-3 px-5 py-3 text-sm">
              <div>
                <p className="font-medium text-slate-900">{k.full_name} {k.is_primary && <span className="ml-1 rounded bg-brand-50 px-1.5 py-0.5 text-xs text-brand-700">Primary</span>}</p>
                <p className="text-slate-500">{k.relationship} · {k.phone}{k.email ? ` · ${k.email}` : ''}</p>
                {k.address && <p className="text-xs text-slate-500">{k.address}</p>}
              </div>
              {can(P.CHANGE_MEMBER) && (
                <ActionButton size="sm" variant="ghost" icon={Trash2} label="Remove" confirmVariant="danger" description={`Remove ${k.full_name} as next of kin?`}
                  action={() => adminApi.members.removeNextOfKin(m.id, k.id)} />
              )}
            </li>
          ))}
        </ul>
      ) : <EmptyState title="No next of kin recorded" />}
    </Card>
  );
}

function History({ m }) {
  return (
    <Card>
      <CardHeader title="Membership status history" />
      {m.status_history.length ? (
        <Table caption="Status history">
          <thead><tr><Th>Date</Th><Th>Change</Th><Th>Reason</Th><Th>By</Th></tr></thead>
          <tbody className="divide-y divide-slate-100">
            {m.status_history.map((h) => (
              <tr key={h.created_at}>
                <Td className="whitespace-nowrap">{formatDateTime(h.created_at)}</Td>
                <Td><span className="flex items-center gap-1">{h.from_status ? <StatusBadge status={h.from_status} /> : '—'} → <StatusBadge status={h.to_status} /></span></Td>
                <Td>{h.reason || '—'}</Td>
                <Td>{h.changed_by || 'System'}</Td>
              </tr>
            ))}
          </tbody>
        </Table>
      ) : <EmptyState title="No status changes" />}
    </Card>
  );
}

export default function MemberDetail() {
  const { id } = useParams();
  const can = useCan();
  const [tab, setTab] = useState('overview');
  const [tempPassword, setTempPassword] = useState(null);
  const member = useQuery({ queryKey: ['admin', 'member', id], queryFn: () => adminApi.members.get(id) });
  const showFinance = can([P.VIEW_SAVINGS, P.VIEW_LOANS, P.VIEW_INVESTMENTS, P.VIEW_DIVIDENDS]);

  return (
    <>
      <Link to="/admin/members" className="inline-flex items-center gap-1 text-sm font-medium text-brand-600 hover:underline">
        <ArrowLeft className="h-4 w-4" aria-hidden="true" /> Members
      </Link>
      <QueryState query={member}>
        {(m) => (
          <div className="mt-3">
            <div className="mb-6 flex flex-wrap items-start justify-between gap-4">
              <div className="flex items-center gap-4">
                <Photo member={m} />
                <div>
                  <div className="flex flex-wrap items-center gap-2">
                    <h1 className="text-2xl font-bold text-slate-900">{m.full_name}</h1>
                    <StatusBadge status={m.status} label={m.status_label} />
                  </div>
                  <p className="text-sm text-slate-500">{m.membership_number}{m.department ? ` · ${m.department.name}` : ''}</p>
                  {can(P.CHANGE_MEMBER) && <PhotoUpload member={m} />}
                </div>
              </div>
              <div className="no-print flex flex-wrap gap-2">
                {can(P.CHANGE_MEMBER) && m.status !== 'CLOSED' && <Link to={`/admin/members/${m.id}/edit`}><Button variant="secondary" icon={Pencil}>Edit</Button></Link>}
                {can(P.CHANGE_MEMBER_STATUS) && STATUS_ACTIONS[m.status].map(([action, text, needsReason]) => (
                  <ActionButton key={action} label={text} variant={needsReason ? 'danger' : 'primary'} input={needsReason ? 'required' : 'optional'}
                    description={`${text} ${m.full_name}'s membership. The change is recorded in the status history and audit log.`}
                    action={(reason) => adminApi.members.action(m.id, action, { reason })} />
                ))}
                {can(P.CHANGE_MEMBER) && m.status !== 'CLOSED' && m.portal.has_email && (
                  <ActionButton label="Send activation" variant="secondary" icon={Mail}
                    description={`Email ${m.email} a link to set ${m.portal.activated ? 'a new' : 'their'} password.`}
                    action={() => adminApi.members.action(m.id, 'send-activation')} />
                )}
                {can(P.CHANGE_MEMBER) && m.status !== 'CLOSED' && (
                  <ActionButton label="Temporary password" variant="secondary" icon={KeyRound}
                    description="Generate a one-time password to give the member in person. They must change it at first sign-in. Any existing sessions are signed out."
                    action={() => adminApi.members.action(m.id, 'temporary-password')} onDone={setTempPassword} />
                )}
              </div>
            </div>

            {tempPassword && (
              <Alert tone="success" title="Temporary password created" className="mb-6">
                <p>{tempPassword.message}</p>
                <p className="mt-2 font-mono text-base font-bold tracking-wider">{tempPassword.temporary_password}</p>
                <button type="button" className="mt-2 text-xs font-semibold underline" onClick={() => setTempPassword(null)}>Hide</button>
              </Alert>
            )}

            <Tabs value={tab} onChange={setTab} tabs={[
              { key: 'overview', label: 'Profile' },
              { key: 'finance', label: 'Finances', show: showFinance },
              { key: 'transactions', label: 'Transactions', show: can(P.VIEW_ALL_TRANSACTIONS) },
              { key: 'documents', label: `Documents (${m.document_count})` },
              { key: 'kin', label: 'Next of kin' },
              { key: 'history', label: 'Status history' },
            ]} />
            {tab === 'overview' && <Overview m={m} />}
            {tab === 'finance' && <Finances id={m.id} />}
            {tab === 'transactions' && <Transactions id={m.id} />}
            {tab === 'documents' && <Documents id={m.id} />}
            {tab === 'kin' && <NextOfKin m={m} />}
            {tab === 'history' && <History m={m} />}
          </div>
        )}
      </QueryState>
    </>
  );
}
