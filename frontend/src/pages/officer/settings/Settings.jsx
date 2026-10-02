import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { Navigate, Outlet } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { KeyRound, Mail, Plus, Trash2 } from 'lucide-react';
import { adminApi } from '../../../api/admin';
import ActionButton from '../../../components/officer/ActionButton';
import DataTable from '../../../components/officer/DataTable';
import { SearchInput } from '../../../components/officer/Filters';
import FormModal from '../../../components/officer/FormModal';
import Tabs from '../../../components/officer/Tabs';
import useList from '../../../components/officer/useList';
import useReference from '../../../components/officer/useReference';
import { Alert, ErrorAlert } from '../../../components/ui/Alert';
import { Badge, StatusBadge } from '../../../components/ui/Badge';
import Button from '../../../components/ui/Button';
import { Card, CardBody, CardHeader } from '../../../components/ui/Card';
import { CheckboxField, SelectField, TextAreaField, TextField } from '../../../components/ui/Field';
import Modal from '../../../components/ui/Modal';
import PageHeader from '../../../components/ui/PageHeader';
import QueryState from '../../../components/ui/QueryState';
import { MONTHS, TXN_TYPES, options } from '../../../lib/choices';
import { applyFieldErrors } from '../../../lib/errors';
import { formatDateTime } from '../../../lib/format';
import { P, useCan } from '../../../lib/permissions';

export function SettingsLayout() {
  const can = useCan();
  return (
    <>
      <PageHeader title="Settings" description="Cooperative details, business rules, departments, officers and their roles." />
      <Tabs tabs={[
        { to: '/admin/settings/cooperative', label: 'Cooperative', show: can(P.MANAGE_SETTINGS) },
        { to: '/admin/settings/departments', label: 'Departments', show: can(P.MANAGE_SETTINGS) },
        { to: '/admin/settings/officers', label: 'Officers', show: can(P.MANAGE_OFFICERS) },
        { to: '/admin/settings/roles', label: 'Roles & permissions', show: can([P.MANAGE_ROLES, P.MANAGE_OFFICERS]) },
      ]} />
      <Outlet />
    </>
  );
}

export function SettingsIndex() {
  const can = useCan();
  if (can(P.MANAGE_SETTINGS)) return <Navigate to="cooperative" replace />;
  if (can(P.MANAGE_OFFICERS)) return <Navigate to="officers" replace />;
  return <Navigate to="roles" replace />;
}

function CooperativeForm({ settings }) {
  const queryClient = useQueryClient();
  const [saved, setSaved] = useState(false);
  const { register, handleSubmit, setError, formState: { errors, isDirty }, reset } = useForm({ defaultValues: settings });
  const mutation = useMutation({
    mutationFn: ({ updated_at, ...data }) => adminApi.settings.update({
      ...data,
      financial_year_start_month: Number(data.financial_year_start_month),
      dividend_processing_month: Number(data.dividend_processing_month),
      loan_overdue_grace_days: Number(data.loan_overdue_grace_days),
      session_idle_timeout_minutes: Number(data.session_idle_timeout_minutes),
      maker_checker_types: [].concat(data.maker_checker_types || []),
    }),
    onSuccess: (data) => {
      reset(data);
      setSaved(true);
      queryClient.invalidateQueries({ queryKey: ['admin', 'settings'] });
    },
    onError: (error) => applyFieldErrors(error, setError),
  });
  const err = (n) => errors[n]?.message;
  return (
    <form onSubmit={handleSubmit((v) => { setSaved(false); mutation.mutate(v); })} noValidate className="space-y-6">
      <ErrorAlert error={mutation.error} />
      {saved && !isDirty && <Alert tone="success">Settings saved.</Alert>}
      <Card>
        <CardHeader title="Cooperative details" description="Shown on statements and reports." />
        <CardBody className="grid gap-4 sm:grid-cols-2">
          <TextField label="Name" {...register('name')} error={err('name')} />
          <TextField label="Short name" {...register('short_name')} error={err('short_name')} />
          <TextField label="Parent institution" {...register('parent_institution')} error={err('parent_institution')} />
          <TextField label="Registration number" {...register('registration_number')} error={err('registration_number')} />
          <TextField label="Email" type="email" {...register('email')} error={err('email')} />
          <TextField label="Phone" {...register('phone')} error={err('phone')} />
          <div className="sm:col-span-2"><TextAreaField label="Address" rows={2} {...register('address')} error={err('address')} /></div>
        </CardBody>
      </Card>
      <Card>
        <CardHeader title="Business rules" />
        <CardBody className="grid gap-4 sm:grid-cols-2">
          <TextField label="Membership number format" {...register('membership_number_format')} error={err('membership_number_format')} hint="e.g. EMDI/{year}/{seq:04d}" />
          <TextField label="Currency" {...register('currency_code')} error={err('currency_code')} />
          <SelectField label="Financial year starts" {...register('financial_year_start_month')} error={err('financial_year_start_month')}>{options(MONTHS)}</SelectField>
          <SelectField label="Dividends processed in" {...register('dividend_processing_month')} error={err('dividend_processing_month')}>{options(MONTHS)}</SelectField>
          <TextField label="Loan overdue grace (days)" type="number" {...register('loan_overdue_grace_days')} error={err('loan_overdue_grace_days')} />
          <TextField label="Sign out after inactivity (minutes)" type="number" {...register('session_idle_timeout_minutes')} error={err('session_idle_timeout_minutes')} />
          <div className="space-y-2 sm:col-span-2">
            <CheckboxField label="Members may request savings withdrawals (only on products that allow it)" {...register('member_withdrawal_requests_enabled')} />
            <CheckboxField label="Closing an account disables the member's portal login" {...register('closure_disables_portal_login')} />
          </div>
        </CardBody>
      </Card>
      <Card>
        <CardHeader title="Maker-checker" description="Entries of these types need a second officer's approval before they are posted. Adjustments and reversals always do." />
        <CardBody className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
          {TXN_TYPES.filter(([v]) => !['ADJUSTMENT', 'REVERSAL'].includes(v)).map(([value, text]) => (
            <label key={value} className="flex items-center gap-2 text-sm text-slate-700">
              <input type="checkbox" value={value} {...register('maker_checker_types')} className="h-4 w-4 rounded border-slate-300 text-brand-600" /> {text}
            </label>
          ))}
          {err('maker_checker_types') && <p className="text-xs text-red-600">{err('maker_checker_types')}</p>}
        </CardBody>
      </Card>
      <div className="flex items-center justify-end gap-3">
        <span className="text-xs text-slate-500">Last updated {formatDateTime(settings.updated_at)}</span>
        <Button type="submit" loading={mutation.isPending} disabled={!isDirty}>Save settings</Button>
      </div>
    </form>
  );
}

export function CooperativeSettings() {
  const settings = useQuery({ queryKey: ['admin', 'settings'], queryFn: adminApi.settings.get });
  return <QueryState query={settings}>{(s) => <CooperativeForm settings={s} />}</QueryState>;
}

function DepartmentForm({ department }) {
  return (
    <FormModal trigger={department ? 'Edit' : 'New department'} triggerIcon={department ? undefined : Plus} triggerVariant={department ? 'ghost' : 'primary'} triggerSize={department ? 'sm' : 'md'}
      title={department ? `Edit ${department.name}` : 'New department'}
      defaultValues={department ? { name: department.name, code: department.code || '', is_active: department.is_active } : { name: '', code: '', is_active: true }}
      transform={(v) => ({ ...v, code: v.code || null })}
      onSubmit={(data) => (department ? adminApi.departments.update(department.id, data) : adminApi.departments.create(data))}
      renderFields={({ register, errors }) => (
        <>
          <TextField label="Name" required {...register('name', { required: 'Required.' })} error={errors.name?.message} />
          <TextField label="Code" {...register('code')} error={errors.code?.message} />
          <CheckboxField label="Active" {...register('is_active')} />
        </>
      )} />
  );
}

export function Departments() {
  const list = useList(['admin', 'departments'], adminApi.departments.list, { search: '' });
  return (
    <DataTable title="Departments" description="Used on member records and reports. Deactivate rather than delete, so history is kept." action={<DepartmentForm />}
      query={list.query} page={list.page} onPage={list.setPage}
      toolbar={<SearchInput value={list.filters.search} onChange={(v) => list.setFilter('search', v)} placeholder="Search departments" />}
      columns={[
        { header: 'Department', cell: (d) => <span className="font-medium text-slate-900">{d.name}</span> },
        { header: 'Code', cell: (d) => d.code || '—' },
        { header: 'Status', cell: (d) => <StatusBadge status={d.is_active ? 'ACTIVE' : 'INACTIVE'} /> },
        { header: '', align: 'right', cell: (d) => <DepartmentForm department={d} /> },
      ]} />
  );
}

function RoleChecklist({ register, roles }) {
  return (
    <div className="space-y-1 rounded-lg border border-slate-200 p-3">
      {roles.map((r) => (
        <label key={r.id} className="flex items-start gap-2 text-sm text-slate-700">
          <input type="checkbox" value={r.id} {...register('roles')} className="mt-0.5 h-4 w-4 rounded border-slate-300 text-brand-600" />
          <span><span className="font-medium">{r.name}</span>{r.description && <span className="block text-xs text-slate-500">{r.description}</span>}</span>
        </label>
      ))}
    </div>
  );
}

const toIds = (roles) => [].concat(roles || []).map(Number);

export function Officers() {
  const roles = useReference('roles');
  const [tempPassword, setTempPassword] = useState(null);
  const list = useList(['admin', 'officers'], adminApi.officers.list, { search: '', role: '' });
  return (
    <div className="space-y-4">
      {tempPassword && (
        <Alert tone="success" title="Temporary password created">
          <p>{tempPassword.message}</p>
          <p className="mt-2 font-mono text-base font-bold tracking-wider">{tempPassword.temporary_password}</p>
          <button type="button" className="mt-2 text-xs font-semibold underline" onClick={() => setTempPassword(null)}>Hide</button>
        </Alert>
      )}
      <DataTable title="Officers" description="Executives and staff with access to the officer portal. Access comes only from their roles."
        action={
          <FormModal trigger="Add officer" triggerIcon={Plus} title="Add an officer" submitLabel="Add and send invitation"
            defaultValues={{ email: '', first_name: '', last_name: '', phone: '', roles: [] }}
            transform={(v) => ({ ...v, roles: toIds(v.roles) })}
            onSubmit={adminApi.officers.create}
            renderFields={({ register, errors }) => (
              <>
                <div className="grid gap-4 sm:grid-cols-2">
                  <TextField label="First name" required {...register('first_name', { required: 'Required.' })} error={errors.first_name?.message} />
                  <TextField label="Last name" required {...register('last_name', { required: 'Required.' })} error={errors.last_name?.message} />
                  <TextField label="Email" type="email" required {...register('email', { required: 'Required.' })} error={errors.email?.message} hint="They receive a link to set their password." />
                  <TextField label="Phone" {...register('phone')} error={errors.phone?.message} />
                </div>
                <p className="text-sm font-medium text-slate-700">Roles</p>
                <RoleChecklist register={register} roles={roles.data || []} />
                {errors.roles && <p className="text-xs text-red-600">{errors.roles.message}</p>}
              </>
            )} />
        }
        query={list.query} page={list.page} onPage={list.setPage} empty="No officers match."
        toolbar={<SearchInput value={list.filters.search} onChange={(v) => list.setFilter('search', v)} placeholder="Name or email" />}
        columns={[
          { header: 'Officer', cell: (o) => <><p className="font-medium text-slate-900">{o.full_name}</p><p className="text-xs text-slate-500">{o.email}</p></> },
          { header: 'Roles', cell: (o) => <div className="flex flex-wrap gap-1">{o.is_superuser && <Badge tone="blue">Superuser</Badge>}{o.roles.map((r) => <Badge key={r.id}>{r.name}</Badge>)}{!o.roles.length && !o.is_superuser && <span className="text-xs text-slate-500">No roles</span>}</div> },
          { header: 'Access', cell: (o) => (o.is_active ? (o.is_activated ? <StatusBadge status="ACTIVE" /> : <Badge tone="amber">Invited</Badge>) : <StatusBadge status="INACTIVE" label="Revoked" />) },
          { header: 'Last sign-in', cell: (o) => <span className="whitespace-nowrap text-xs">{formatDateTime(o.last_login)}</span> },
          {
            header: '', align: 'right',
            cell: (o) => (
              <div className="flex justify-end gap-1">
                <FormModal trigger="Roles" triggerVariant="ghost" triggerSize="sm" title={`Roles for ${o.full_name}`} submitLabel="Save roles"
                  defaultValues={{ roles: o.roles.map((r) => String(r.id)) }}
                  onSubmit={(v) => adminApi.officers.setRoles(o.id, toIds(v.roles))}
                  renderFields={({ register, errors }) => (
                    <>
                      <RoleChecklist register={register} roles={roles.data || []} />
                      {errors.roles && <p className="text-xs text-red-600">{errors.roles.message}</p>}
                      <p className="text-xs text-slate-500">You cannot remove your own administration access, and at least one officer must keep it.</p>
                    </>
                  )} />
                {o.is_active && !o.is_activated && (
                  <ActionButton size="sm" variant="ghost" icon={Mail} label="Resend invite" description={`Email ${o.email} a new link to set their password.`} action={() => adminApi.officers.action(o.id, 'send-activation')} />
                )}
                {o.is_active && (
                  <ActionButton size="sm" variant="ghost" icon={KeyRound} label="Temp password" description="Generate a one-time password to give the officer in person. Existing sessions are signed out."
                    action={() => adminApi.officers.action(o.id, 'temporary-password')} onDone={setTempPassword} />
                )}
                {o.is_active && (
                  <ActionButton size="sm" variant="ghost" label="Revoke" confirmVariant="danger" input="optional" description={`Remove ${o.full_name}'s officer access and sign them out everywhere. Their membership (if any) is unaffected.`}
                    action={(reason) => adminApi.officers.action(o.id, 'revoke', { reason })} />
                )}
              </div>
            ),
          },
        ]} />
    </div>
  );
}

function RoleEditor({ role, catalogue, onClose }) {
  const queryClient = useQueryClient();
  const { register, handleSubmit, setError, formState: { errors } } = useForm({
    defaultValues: { name: role?.name || '', description: role?.description || '', permissions: role?.permissions || [] },
  });
  const mutation = useMutation({
    mutationFn: (v) => {
      const data = { ...v, permissions: [].concat(v.permissions || []) };
      return role ? adminApi.roles.update(role.id, data) : adminApi.roles.create(data);
    },
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['admin'] }); onClose(); },
    onError: (error) => applyFieldErrors(error, setError),
  });
  return (
    <Modal open onClose={onClose} title={role ? `Edit role · ${role.name}` : 'New role'}
      footer={<><Button variant="secondary" onClick={onClose}>Cancel</Button><Button loading={mutation.isPending} onClick={handleSubmit((v) => mutation.mutate(v))}>Save role</Button></>}>
      <form className="space-y-4" onSubmit={handleSubmit((v) => mutation.mutate(v))} noValidate>
        <ErrorAlert error={mutation.error} />
        <TextField label="Name" required {...register('name', { required: 'Required.' })} error={errors.name?.message} disabled={role?.is_system} />
        <TextField label="Description" {...register('description')} error={errors.description?.message} />
        {errors.permissions && <p className="text-xs text-red-600">{errors.permissions.message}</p>}
        <div className="max-h-[50vh] space-y-4 overflow-y-auto pr-1">
          {catalogue.map((group) => (
            <fieldset key={group.module}>
              <legend className="mb-1 text-xs font-semibold uppercase tracking-wide text-slate-500">{group.label}</legend>
              <div className="space-y-1">
                {group.permissions.map((p) => (
                  <label key={p.code} className="flex items-center gap-2 text-sm text-slate-700">
                    <input type="checkbox" value={p.code} {...register('permissions')} className="h-4 w-4 rounded border-slate-300 text-brand-600" /> {p.name}
                  </label>
                ))}
              </div>
            </fieldset>
          ))}
        </div>
      </form>
    </Modal>
  );
}

export function Roles() {
  const can = useCan();
  const [editing, setEditing] = useState(null);
  const roles = useQuery({ queryKey: ['admin', 'roles-page'], queryFn: () => adminApi.roles.list({ page_size: 100 }) });
  const catalogue = useQuery({ queryKey: ['admin', 'permission-catalogue'], queryFn: adminApi.permissions, staleTime: Infinity });
  const manage = can(P.MANAGE_ROLES);
  const names = Object.fromEntries((catalogue.data || []).flatMap((g) => g.permissions.map((p) => [p.code, p.name])));
  return (
    <>
      <Card>
        <CardHeader title="Roles" description="Default roles mirror EMDI's executive offices. Officers get permissions only through roles."
          action={manage && <Button icon={Plus} onClick={() => setEditing('new')} disabled={!catalogue.data}>New role</Button>} />
        <QueryState query={roles}>
          {(data) => (
            <ul className="divide-y divide-slate-100">
              {data.results.map((r) => (
                <li key={r.id} className="px-5 py-4">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <p className="font-semibold text-slate-900">{r.name} {r.is_system && <Badge tone="blue">Default</Badge>}</p>
                      {r.description && <p className="text-sm text-slate-500">{r.description}</p>}
                      <p className="mt-1 text-xs text-slate-500">{r.officer_count} officer(s) · {r.permissions.length} permission(s)</p>
                    </div>
                    {manage && (
                      <div className="flex gap-1">
                        <Button size="sm" variant="ghost" onClick={() => setEditing(r)} disabled={!catalogue.data}>Edit</Button>
                        {!r.is_system && (
                          <ActionButton size="sm" variant="ghost" icon={Trash2} label="Delete" confirmVariant="danger"
                            description={r.officer_count ? `${r.officer_count} officer(s) have this role. Reassign them first.` : `Delete the ${r.name} role?`}
                            action={() => adminApi.roles.remove(r.id)} />
                        )}
                      </div>
                    )}
                  </div>
                  <details className="mt-2 text-xs">
                    <summary className="cursor-pointer text-brand-600">Permissions</summary>
                    <ul className="mt-2 grid gap-1 text-slate-600 sm:grid-cols-2 lg:grid-cols-3">
                      {r.permissions.map((p) => <li key={p}>• {names[p] || p}</li>)}
                    </ul>
                  </details>
                </li>
              ))}
            </ul>
          )}
        </QueryState>
      </Card>
      {editing && catalogue.data && <RoleEditor role={editing === 'new' ? null : editing} catalogue={catalogue.data} onClose={() => setEditing(null)} />}
    </>
  );
}
