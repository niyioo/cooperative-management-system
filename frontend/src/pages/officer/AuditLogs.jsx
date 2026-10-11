import { Fragment, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { ChevronDown, ChevronRight } from 'lucide-react';
import { adminApi } from '../../api/admin';
import { FilterBar, FilterDate, FilterSelect, SearchInput } from '../../components/officer/Filters';
import useList from '../../components/officer/useList';
import { Card } from '../../components/ui/Card';
import EmptyState from '../../components/ui/EmptyState';
import PageHeader from '../../components/ui/PageHeader';
import Pagination from '../../components/ui/Pagination';
import QueryState from '../../components/ui/QueryState';
import { Table, Td, Th } from '../../components/ui/Table';
import { formatDateTime } from '../../lib/format';

function Json({ title, value }) {
  if (!value || (typeof value === 'object' && !Object.keys(value).length)) return null;
  return (
    <div>
      <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-slate-500">{title}</p>
      <pre className="max-h-64 overflow-auto rounded-lg bg-slate-900 p-3 text-xs text-slate-100">{JSON.stringify(value, null, 2)}</pre>
    </div>
  );
}

export default function AuditLogs() {
  const [open, setOpen] = useState(null);
  const actions = useQuery({ queryKey: ['admin', 'audit-actions'], queryFn: adminApi.auditLogs.actions, staleTime: 5 * 60_000 });
  const list = useList(['admin', 'audit-logs'], adminApi.auditLogs.list, { search: '', action: '', date_from: '', date_to: '' });

  return (
    <>
      <PageHeader title="Audit logs" description="Every sign-in, approval, financial operation and settings change, with who did it, when and from where. Read-only." />
      <Card>
        <div className="border-b border-slate-100 px-5 py-3">
          <FilterBar>
            <SearchInput value={list.filters.search} onChange={(v) => list.setFilter('search', v)} placeholder="Officer, action, record or reference" />
            <FilterSelect label="Action" value={list.filters.action} onChange={(v) => list.setFilter('action', v)} options={(actions.data || []).map((a) => [a, a])} />
            <FilterDate label="From" value={list.filters.date_from} onChange={(v) => list.setFilter('date_from', v)} />
            <FilterDate label="To" value={list.filters.date_to} onChange={(v) => list.setFilter('date_to', v)} />
          </FilterBar>
        </div>
        <QueryState query={list.query}>
          {(data) => data.results.length ? (
            <>
              <Table caption="Audit log">
                <thead><tr><Th /><Th>When</Th><Th>Who</Th><Th>Action</Th><Th>Record</Th><Th>IP address</Th></tr></thead>
                <tbody className="divide-y divide-slate-100">
                  {data.results.map((log) => {
                    const expanded = open === log.id;
                    return (
                      <Fragment key={log.id}>
                        <tr className="cursor-pointer hover:bg-slate-50" onClick={() => setOpen(expanded ? null : log.id)}>
                          <Td>
                            <button type="button" aria-expanded={expanded} aria-label={expanded ? 'Hide details' : 'Show details'} className="text-slate-400">
                              {expanded ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
                            </button>
                          </Td>
                          <Td className="whitespace-nowrap text-xs">{formatDateTime(log.timestamp)}</Td>
                          <Td>{log.actor_repr || 'System'}</Td>
                          <Td><code className="rounded bg-slate-100 px-1.5 py-0.5 text-xs text-slate-800">{log.action}</code></Td>
                          <Td className="text-xs">{log.object_repr}{log.object_type && <span className="block text-slate-500">{log.object_type}</span>}</Td>
                          <Td className="text-xs">{log.ip_address || '—'}</Td>
                        </tr>
                        {expanded && (
                          <tr>
                            <Td className="bg-slate-50" colSpan={6}>
                              <div className="grid gap-4 lg:grid-cols-2">
                                <Json title="Changes" value={log.changes} />
                                <Json title="Details" value={log.metadata} />
                                <p className="text-xs text-slate-500 lg:col-span-2">Request {log.request_id || '—'} · {log.user_agent || 'unknown client'}</p>
                              </div>
                            </Td>
                          </tr>
                        )}
                      </Fragment>
                    );
                  })}
                </tbody>
              </Table>
              <Pagination page={list.page} count={data.count} onChange={list.setPage} />
            </>
          ) : <EmptyState title="No audit entries match" />}
        </QueryState>
      </Card>
    </>
  );
}
