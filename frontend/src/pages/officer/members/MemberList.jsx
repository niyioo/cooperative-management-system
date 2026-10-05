import { Link } from 'react-router-dom';
import { FileSpreadsheet, UserPlus } from 'lucide-react';
import { adminApi } from '../../../api/admin';
import DataTable from '../../../components/officer/DataTable';
import { FilterBar, FilterDate, FilterSelect, SearchInput } from '../../../components/officer/Filters';
import useList from '../../../components/officer/useList';
import useReference from '../../../components/officer/useReference';
import { StatusBadge } from '../../../components/ui/Badge';
import Button from '../../../components/ui/Button';
import PageHeader from '../../../components/ui/PageHeader';
import { EMPLOYMENT, MEMBER_STATUS } from '../../../lib/choices';
import { formatDate } from '../../../lib/format';
import { P, useCan } from '../../../lib/permissions';

export default function MemberList() {
  const can = useCan();
  const list = useList(['admin', 'members'], adminApi.members.list, { search: '', status: '', department: '', employment_status: '', joined_from: '', joined_to: '' });
  const departments = useReference('departments');

  return (
    <>
      <PageHeader
        title="Members"
        description="Search, register and manage cooperative members."
        actions={
          <>
            {can(P.IMPORT_MEMBERS) && <Link to="/admin/members/imports"><Button variant="secondary" icon={FileSpreadsheet}>Import</Button></Link>}
            {can(P.ADD_MEMBER) && <Link to="/admin/members/new"><Button icon={UserPlus}>Register member</Button></Link>}
          </>
        }
      />
      <DataTable
        query={list.query}
        page={list.page}
        onPage={list.setPage}
        empty="No members match these filters."
        toolbar={
          <FilterBar>
            <SearchInput value={list.filters.search} onChange={(v) => list.setFilter('search', v)} placeholder="Name, membership/staff/IPPIS number, phone or email" />
            <FilterSelect label="Status" value={list.filters.status} onChange={(v) => list.setFilter('status', v)} options={MEMBER_STATUS} />
            <FilterSelect label="Department" value={list.filters.department} onChange={(v) => list.setFilter('department', v)}
              options={(departments.data || []).map((d) => [d.id, d.name])} />
            <FilterSelect label="Employment" value={list.filters.employment_status} onChange={(v) => list.setFilter('employment_status', v)} options={EMPLOYMENT} />
            <FilterDate label="Joined from" value={list.filters.joined_from} onChange={(v) => list.setFilter('joined_from', v)} />
            <FilterDate label="Joined to" value={list.filters.joined_to} onChange={(v) => list.setFilter('joined_to', v)} />
          </FilterBar>
        }
        columns={[
          {
            header: 'Member',
            cell: (m) => (
              <Link to={`/admin/members/${m.id}`} className="group block">
                <span className="font-semibold text-slate-900 group-hover:text-brand-600 group-hover:underline">{m.full_name}</span>
                <span className="block text-xs text-slate-500">{m.membership_number}{m.staff_number ? ` · Staff ${m.staff_number}` : ''}</span>
              </Link>
            ),
          },
          { header: 'Department', cell: (m) => m.department?.name || '—' },
          { header: 'Phone', cell: (m) => <span className="whitespace-nowrap">{m.phone}</span> },
          { header: 'Joined', cell: (m) => <span className="whitespace-nowrap">{formatDate(m.date_joined)}</span> },
          { header: 'Status', cell: (m) => <StatusBadge status={m.status} label={m.status_label} /> },
        ]}
      />
    </>
  );
}
