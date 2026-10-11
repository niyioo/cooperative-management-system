import { useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { Megaphone, Plus, Send, X } from 'lucide-react';
import { adminApi } from '../../../api/admin';
import ActionButton from '../../../components/officer/ActionButton';
import DataTable from '../../../components/officer/DataTable';
import { FilterBar, FilterSelect, SearchInput } from '../../../components/officer/Filters';
import FormModal from '../../../components/officer/FormModal';
import MemberPicker from '../../../components/officer/MemberPicker';
import Tabs from '../../../components/officer/Tabs';
import useList from '../../../components/officer/useList';
import useReference from '../../../components/officer/useReference';
import { Alert, ErrorAlert } from '../../../components/ui/Alert';
import { Badge, StatusBadge } from '../../../components/ui/Badge';
import Button from '../../../components/ui/Button';
import { CheckboxField, SelectField, TextAreaField, TextField } from '../../../components/ui/Field';
import Modal from '../../../components/ui/Modal';
import PageHeader from '../../../components/ui/PageHeader';
import { ANNOUNCEMENT_AUDIENCE, ANNOUNCEMENT_STATE, BROADCAST_AUDIENCE, options } from '../../../lib/choices';
import { apiError } from '../../../lib/errors';
import { formatDateTime } from '../../../lib/format';
import { P, useCan } from '../../../lib/permissions';

/** ISO timestamp -> value for <input type="datetime-local"> in local time. */
const toLocalInput = (iso) => {
  if (!iso) return '';
  const d = new Date(iso);
  return new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 16);
};
const fromLocalInput = (value) => (value ? new Date(value).toISOString() : null);

function ComposeMessage() {
  const queryClient = useQueryClient();
  const departments = useReference('departments', { is_active: true });
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ title: '', body: '', audience: 'ALL_ACTIVE', department: '', link: '' });
  const [members, setMembers] = useState([]);
  const [sent, setSent] = useState(null);
  const send = useMutation({
    mutationFn: () => adminApi.messages.create({
      title: form.title, body: form.body, audience: form.audience, link: form.link,
      ...(form.audience === 'DEPARTMENT' ? { department: form.department } : {}),
      ...(form.audience === 'SELECTED' ? { members: members.map((m) => m.id) } : {}),
    }),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['admin', 'messages'] });
      setSent(data);
      setOpen(false);
      setForm({ title: '', body: '', audience: 'ALL_ACTIVE', department: '', link: '' });
      setMembers([]);
    },
  });
  const fields = apiError(send.error).fields || {};
  const err = (name) => (send.error && fields[name] ? [].concat(fields[name])[0] : undefined);
  const set = (name) => (e) => setForm((f) => ({ ...f, [name]: e.target.value }));
  const blocked = !form.title.trim() || !form.body.trim() || (form.audience === 'DEPARTMENT' && !form.department) || (form.audience === 'SELECTED' && !members.length);

  return (
    <>
      <Button icon={Send} onClick={() => { send.reset(); setSent(null); setOpen(true); }}>New message</Button>
      {sent && <Alert tone="success" className="mt-3">"{sent.title}" was sent to {sent.recipient_count} member(s). It appears in their portal notifications.</Alert>}
      <Modal open={open} onClose={() => setOpen(false)} title="Message members"
        footer={<><Button variant="secondary" onClick={() => setOpen(false)}>Cancel</Button><Button icon={Send} loading={send.isPending} disabled={blocked} onClick={() => send.mutate()}>Send</Button></>}>
        <div className="space-y-4">
          <ErrorAlert error={send.error} />
          <SelectField label="Send to" value={form.audience} onChange={set('audience')}>{options(BROADCAST_AUDIENCE)}</SelectField>
          {form.audience === 'DEPARTMENT' && (
            <SelectField label="Department" required value={form.department} onChange={set('department')} error={err('department')}>
              <option value="">Choose…</option>
              {(departments.data || []).map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
            </SelectField>
          )}
          {form.audience === 'SELECTED' && (
            <div className="space-y-2">
              <MemberPicker label="Add member" value={null} status="" error={err('members')}
                onChange={(m) => m && setMembers((list) => (list.some((x) => x.id === m.id) ? list : [...list, m]))} />
              {members.length > 0 && (
                <ul className="flex flex-wrap gap-2" aria-label="Recipients">
                  {members.map((m) => (
                    <li key={m.id} className="inline-flex items-center gap-1 rounded-full bg-brand-50 py-1 pl-3 pr-1 text-xs font-medium text-brand-800">
                      {m.full_name}
                      <button type="button" onClick={() => setMembers((list) => list.filter((x) => x.id !== m.id))} className="rounded-full p-0.5 hover:bg-brand-100" aria-label={`Remove ${m.full_name}`}>
                        <X className="h-3 w-3" />
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}
          <TextField label="Title" required maxLength={200} value={form.title} onChange={set('title')} error={err('title')} />
          <TextAreaField label="Message" required rows={5} value={form.body} onChange={set('body')} error={err('body')} />
          <SelectField label="Link (optional)" value={form.link} onChange={set('link')} error={err('link')} hint="Where the member goes when they open the notification.">
            <option value="">No link</option>
            <option value="/member/savings">My Savings</option>
            <option value="/member/loans">My Loans</option>
            <option value="/member/loans/apply">Apply for Loan</option>
            <option value="/member/dividends">My Dividends</option>
            <option value="/member/transactions">Transactions</option>
            <option value="/member/profile">Profile</option>
          </SelectField>
        </div>
      </Modal>
    </>
  );
}

function Messages() {
  const list = useList(['admin', 'messages'], adminApi.messages.list, { search: '', audience: '' });
  return (
    <div className="space-y-4">
      <ComposeMessage />
      <DataTable title="Sent messages" description="Each recipient gets the message in their portal notifications." query={list.query} page={list.page} onPage={list.setPage}
        empty="No messages sent yet."
        toolbar={
          <FilterBar>
            <SearchInput value={list.filters.search} onChange={(v) => list.setFilter('search', v)} placeholder="Search messages" />
            <FilterSelect label="Audience" value={list.filters.audience} onChange={(v) => list.setFilter('audience', v)} options={BROADCAST_AUDIENCE} />
          </FilterBar>
        }
        columns={[
          { header: 'Message', cell: (m) => <><p className="font-semibold text-slate-900">{m.title}</p><p className="line-clamp-2 max-w-md text-xs text-slate-500">{m.body}</p></> },
          { header: 'Sent to', cell: (m) => <>{m.audience_label}{m.department_name && <p className="text-xs text-slate-500">{m.department_name}</p>}</> },
          { header: 'Recipients', align: 'right', cell: (m) => m.recipient_count },
          { header: 'Read', align: 'right', cell: (m) => `${m.read_count} (${m.recipient_count ? Math.round((m.read_count / m.recipient_count) * 100) : 0}%)` },
          { header: 'Sent', cell: (m) => <span className="whitespace-nowrap text-xs">{formatDateTime(m.created_at)}<br />{m.sent_by}</span> },
        ]} />
    </div>
  );
}

const ANNOUNCEMENT_DEFAULTS = { title: '', body: '', audience: 'ALL_MEMBERS', is_important: false, publish_at: '', expires_at: '' };

function AnnouncementForm({ announcement }) {
  return (
    <FormModal
      trigger={announcement ? 'Edit' : 'New announcement'} triggerIcon={announcement ? undefined : Plus}
      triggerVariant={announcement ? 'ghost' : 'primary'} triggerSize={announcement ? 'sm' : 'md'}
      title={announcement ? 'Edit announcement' : 'New announcement'}
      defaultValues={announcement
        ? { ...announcement, publish_at: toLocalInput(announcement.publish_at), expires_at: toLocalInput(announcement.expires_at) }
        : ANNOUNCEMENT_DEFAULTS}
      transform={(v) => ({
        title: v.title, body: v.body, audience: v.audience, is_important: v.is_important,
        ...(v.publish_at ? { publish_at: fromLocalInput(v.publish_at) } : {}),
        expires_at: fromLocalInput(v.expires_at),
      })}
      onSubmit={(data) => (announcement ? adminApi.announcements.update(announcement.id, data) : adminApi.announcements.create(data))}
      renderFields={({ register, errors }) => (
        <>
          <TextField label="Title" required maxLength={200} {...register('title', { required: 'Required.' })} error={errors.title?.message} />
          <TextAreaField label="Announcement" required rows={5} {...register('body', { required: 'Required.' })} error={errors.body?.message} />
          <SelectField label="Shown to" {...register('audience')} error={errors.audience?.message}>{options(ANNOUNCEMENT_AUDIENCE)}</SelectField>
          <div className="grid gap-4 sm:grid-cols-2">
            <TextField label="Publish at" type="datetime-local" {...register('publish_at')} error={errors.publish_at?.message} hint="Blank = now" />
            <TextField label="Ends at" type="datetime-local" {...register('expires_at')} error={errors.expires_at?.message} hint="Blank = until ended" />
          </div>
          <CheckboxField label="Important (pinned to the top of dashboards)" {...register('is_important')} />
        </>
      )} />
  );
}

function Announcements() {
  const list = useList(['admin', 'announcements'], adminApi.announcements.list, { search: '', state: '', audience: '' });
  return (
    <DataTable title="Announcements" description="Notices on the member and officer dashboards. Ending one takes it down and keeps it on record."
      action={<AnnouncementForm />} query={list.query} page={list.page} onPage={list.setPage} empty="No announcements."
      toolbar={
        <FilterBar>
          <SearchInput value={list.filters.search} onChange={(v) => list.setFilter('search', v)} placeholder="Search announcements" />
          <FilterSelect label="State" value={list.filters.state} onChange={(v) => list.setFilter('state', v)} options={ANNOUNCEMENT_STATE} />
          <FilterSelect label="Audience" value={list.filters.audience} onChange={(v) => list.setFilter('audience', v)} options={ANNOUNCEMENT_AUDIENCE} />
        </FilterBar>
      }
      columns={[
        {
          header: 'Announcement',
          cell: (a) => (
            <>
              <p className="font-semibold text-slate-900">{a.title} {a.is_important && <Badge tone="amber">Important</Badge>}</p>
              <p className="line-clamp-2 max-w-md text-xs text-slate-500">{a.body}</p>
            </>
          ),
        },
        { header: 'Shown to', cell: (a) => a.audience_label },
        { header: 'Runs', cell: (a) => <span className="whitespace-nowrap text-xs">{formatDateTime(a.publish_at)}<br />{a.expires_at ? `to ${formatDateTime(a.expires_at)}` : 'until ended'}</span> },
        { header: 'State', cell: (a) => <StatusBadge status={a.state} /> },
        {
          header: '', align: 'right',
          cell: (a) => a.state !== 'ENDED' && (
            <div className="flex justify-end gap-1">
              <AnnouncementForm announcement={a} />
              <ActionButton size="sm" variant="ghost" label="End" confirmVariant="danger" description={`Take "${a.title}" down now? It stays on record.`}
                action={() => adminApi.announcements.action(a.id, 'end')} />
            </div>
          ),
        },
      ]} />
  );
}

export default function OfficerNotifications() {
  const can = useCan();
  const canSend = can(P.SEND_NOTIFICATIONS);
  const canAnnounce = can(P.MANAGE_ANNOUNCEMENTS);
  const [tab, setTab] = useState(canSend ? 'messages' : 'announcements');
  return (
    <>
      <PageHeader title="Notifications" description="Message members directly or publish announcements. Members are also notified automatically about their loans, closures, dividends and Christmas Savings payouts." />
      <Tabs value={tab} onChange={setTab} tabs={[
        { key: 'messages', label: 'Messages', show: canSend },
        { key: 'announcements', label: 'Announcements', show: canAnnounce },
      ]} />
      {tab === 'messages' && canSend && <Messages />}
      {tab === 'announcements' && canAnnounce && <Announcements />}
      {!canSend && !canAnnounce && <Alert><Megaphone className="inline h-4 w-4" aria-hidden="true" /> Your role cannot send messages or announcements.</Alert>}
    </>
  );
}
