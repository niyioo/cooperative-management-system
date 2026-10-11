import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { Bell, CheckCheck } from 'lucide-react';
import { memberApi } from '../../api/member';
import Button from '../../components/ui/Button';
import { Card, CardHeader } from '../../components/ui/Card';
import EmptyState from '../../components/ui/EmptyState';
import PageHeader from '../../components/ui/PageHeader';
import Pagination from '../../components/ui/Pagination';
import QueryState from '../../components/ui/QueryState';
import { formatDateTime } from '../../lib/format';
import { isPortalLink } from '../../lib/links';

export default function Notifications() {
  const queryClient = useQueryClient();
  const [page, setPage] = useState(1);
  const notifications = useQuery({ queryKey: ['me', 'notifications', page], queryFn: () => memberApi.notifications(page) });
  const announcements = useQuery({ queryKey: ['me', 'announcements'], queryFn: memberApi.announcements });
  const refresh = () => queryClient.invalidateQueries({ queryKey: ['me'] });
  const markRead = useMutation({ mutationFn: memberApi.markRead, onSuccess: refresh });
  const markAll = useMutation({ mutationFn: memberApi.markAllRead, onSuccess: refresh });

  return (
    <div className="space-y-6">
      <PageHeader title="Notifications" actions={<Button variant="secondary" icon={CheckCheck} loading={markAll.isPending} onClick={() => markAll.mutate()}>Mark all as read</Button>} />
      <Card>
        <CardHeader title="Your notifications" />
        <QueryState query={notifications}>
          {(data) =>
            data.results.length ? (
              <>
                <ul className="divide-y divide-slate-100">
                  {data.results.map((n) => (
                    <li key={n.id} className={`flex gap-3 px-5 py-4 ${n.is_read ? '' : 'bg-brand-50/50'}`}>
                      <span className={`mt-1.5 h-2 w-2 shrink-0 rounded-full ${n.is_read ? 'bg-transparent' : 'bg-accent'}`} aria-hidden="true" />
                      <div className="min-w-0 flex-1">
                        <p className={`text-sm ${n.is_read ? 'text-slate-700' : 'font-semibold text-slate-900'}`}>{n.title}</p>
                        <p className="mt-0.5 text-sm text-slate-600">{n.body}</p>
                        <div className="mt-1 flex flex-wrap gap-3 text-xs text-slate-400">
                          <span>{formatDateTime(n.created_at)}</span>
                          {isPortalLink(n.link) && <Link to={n.link} className="font-semibold text-brand-600 hover:underline" onClick={() => !n.is_read && markRead.mutate(n.id)}>Open</Link>}
                          {!n.is_read && <button type="button" className="font-semibold text-brand-600 hover:underline" onClick={() => markRead.mutate(n.id)}>Mark as read</button>}
                        </div>
                      </div>
                    </li>
                  ))}
                </ul>
                <Pagination page={page} count={data.count} onChange={setPage} />
              </>
            ) : (
              <EmptyState icon={Bell} title="No notifications">We will let you know about loan decisions, dividends and other updates here.</EmptyState>
            )
          }
        </QueryState>
      </Card>
      <Card>
        <CardHeader title="Cooperative announcements" />
        <QueryState query={announcements}>
          {(data) =>
            data.results.length ? (
              <ul className="divide-y divide-slate-100">
                {data.results.map((a) => (
                  <li key={a.id} className="px-5 py-4">
                    <p className="text-sm font-semibold text-slate-900">{a.title}</p>
                    <p className="mt-1 whitespace-pre-line text-sm text-slate-600">{a.body}</p>
                    <p className="mt-1 text-xs text-slate-400">{formatDateTime(a.publish_at)}</p>
                  </li>
                ))}
              </ul>
            ) : (
              <EmptyState title="No announcements" />
            )
          }
        </QueryState>
      </Card>
    </div>
  );
}
