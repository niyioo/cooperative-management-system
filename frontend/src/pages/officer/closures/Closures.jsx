import { useState } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import { Link, useParams } from 'react-router-dom';
import { ArrowLeft, Download } from 'lucide-react';
import { adminApi } from '../../../api/admin';
import ActionButton from '../../../components/officer/ActionButton';
import DataTable from '../../../components/officer/DataTable';
import DetailList from '../../../components/officer/DetailList';
import { FilterBar, FilterSelect, SearchInput } from '../../../components/officer/Filters';
import useList from '../../../components/officer/useList';
import { Alert, ErrorAlert } from '../../../components/ui/Alert';
import { StatusBadge } from '../../../components/ui/Badge';
import Button from '../../../components/ui/Button';
import { Card, CardBody, CardHeader } from '../../../components/ui/Card';
import { TextField } from '../../../components/ui/Field';
import PageHeader from '../../../components/ui/PageHeader';
import QueryState from '../../../components/ui/QueryState';
import { Money, Table, Td, Th } from '../../../components/ui/Table';
import { CLOSURE_STATUS, today } from '../../../lib/choices';
import { saveBlob } from '../../../lib/download';
import { formatDateTime, formatNaira } from '../../../lib/format';
import { P, useCan } from '../../../lib/permissions';

export function ClosureList() {
  const list = useList(['admin', 'closures'], adminApi.closures.list, { search: '', status: '' });
  return (
    <>
      <PageHeader title="Account closures" description="Members' requests to close their membership. Closure needs officer approval; records are kept." />
      <DataTable query={list.query} page={list.page} onPage={list.setPage} empty="No closure requests."
        toolbar={
          <FilterBar>
            <SearchInput value={list.filters.search} onChange={(v) => list.setFilter('search', v)} placeholder="Reference, member name or number" />
            <FilterSelect label="Status" value={list.filters.status} onChange={(v) => list.setFilter('status', v)} options={CLOSURE_STATUS} />
          </FilterBar>
        }
        columns={[
          { header: 'Reference', cell: (r) => <Link to={`/admin/closures/${r.id}`} className="font-semibold text-brand-600 hover:underline">{r.reference}</Link> },
          { header: 'Member', cell: (r) => <><p className="font-medium text-slate-900">{r.member.full_name}</p><p className="text-xs text-slate-500">{r.member.membership_number}</p></> },
          { header: 'Reason', cell: (r) => r.reason_category_label },
          { header: 'Submitted', cell: (r) => <span className="whitespace-nowrap">{formatDateTime(r.created_at)}</span> },
          { header: 'Status', cell: (r) => <StatusBadge status={r.status} label={r.status_label} /> },
        ]} />
    </>
  );
}

function Lines({ title, rows, amountKey, describe }) {
  if (!rows.length) return null;
  return (
    <>
      <tr><Td className="bg-slate-50 text-xs font-semibold uppercase tracking-wide text-slate-500" colSpan={2}>{title}</Td></tr>
      {rows.map((r) => (
        <tr key={r.id || r.financial_year}>
          <Td>{describe(r)}</Td>
          <Td align="right"><Money value={r[amountKey]} /></Td>
        </tr>
      ))}
    </>
  );
}

function Settlement({ statement, frozen }) {
  return (
    <Card>
      <CardHeader title="Settlement statement" description={frozen ? 'Frozen when the request was approved. Balances are re-checked at execution.' : 'Live from current posted balances.'} />
      <Table caption="Settlement statement">
        <thead><tr><Th>Item</Th><Th align="right">Amount</Th></tr></thead>
        <tbody className="divide-y divide-slate-100">
          <Lines title="Savings (paid out)" rows={statement.savings} amountKey="balance" describe={(s) => <>{s.label} <span className="text-xs text-slate-500">{s.account_number}</span></>} />
          <Lines title="Investments (liquidated)" rows={statement.investments} amountKey="balance" describe={(i) => <>{i.label} <span className="text-xs text-slate-500">{i.account_number}</span></>} />
          <Lines title="Loans (offset from funds)" rows={statement.loans} amountKey="outstanding" describe={(l) => l.reference} />
          <Lines title="Approved dividends not yet paid" rows={statement.unpaid_dividends} amountKey="net_amount" describe={(d) => `${d.financial_year} dividend (paid through the dividend cycle)`} />
          <tr className="font-semibold"><Td>Savings total</Td><Td align="right"><Money value={statement.savings_total} /></Td></tr>
          <tr className="font-semibold"><Td>Investments total</Td><Td align="right"><Money value={statement.investment_total} /></Td></tr>
          <tr className="font-semibold"><Td>Less loans outstanding</Td><Td align="right"><Money value={statement.loan_total} className="text-red-700" /></Td></tr>
          <tr className="bg-brand-50 text-base font-bold"><Td>Net payable to member</Td><Td align="right"><Money value={statement.net_payable} /></Td></tr>
        </tbody>
      </Table>
      {(!statement.can_settle || statement.pending_entries > 0) && (
        <CardBody className="space-y-2">
          {Number(statement.net_payable) < 0 && <Alert tone="warning">Loans exceed the member's funds by {formatNaira(-Number(statement.net_payable))}. The shortfall must be repaid before the account can be closed.</Alert>}
          {statement.guarantees?.length > 0 && (
            <Alert tone="warning" title="This member guarantees loans that are still running">
              {statement.guarantees.map((g) => `${g.loan_application} (${g.borrower}, ${formatNaira(g.amount_guaranteed)})`).join('; ')}.
              {' '}A guarantor stays liable until those loans are repaid, so the account cannot be closed before then.
            </Alert>
          )}
          {statement.pending_entries > 0 && <Alert tone="warning">{statement.pending_entries} transaction(s) for this member are awaiting approval. Approve or reject them before executing the closure.</Alert>}
        </CardBody>
      )}
    </Card>
  );
}

export function ClosureDetail() {
  const { id } = useParams();
  const can = useCan();
  const [valueDate, setValueDate] = useState(today());
  const [executed, setExecuted] = useState(null);
  const request = useQuery({ queryKey: ['admin', 'closure', id], queryFn: () => adminApi.closures.get(id) });
  const open = request.data && ['SUBMITTED', 'UNDER_REVIEW'].includes(request.data.status);
  const live = useQuery({ queryKey: ['admin', 'closure', id, 'settlement'], queryFn: () => adminApi.closures.sub(id, 'settlement'), enabled: !!open || request.data?.status === 'APPROVED' });
  const attachment = useMutation({ mutationFn: () => adminApi.closures.attachment(id).then((res) => saveBlob(res, 'closure-attachment')) });

  return (
    <>
      <Link to="/admin/closures" className="inline-flex items-center gap-1 text-sm font-medium text-brand-600 hover:underline">
        <ArrowLeft className="h-4 w-4" aria-hidden="true" /> Account closures
      </Link>
      <QueryState query={request}>
        {(r) => (
          <div className="mt-3 space-y-6">
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div>
                <div className="flex flex-wrap items-center gap-2">
                  <h1 className="text-2xl font-bold text-slate-900">{r.reference}</h1>
                  <StatusBadge status={r.status} label={r.status_label} />
                </div>
                <p className="text-sm text-slate-500">
                  <Link to={`/admin/members/${r.member.id}`} className="font-medium text-brand-600 hover:underline">{r.member.full_name}</Link> · {r.member.membership_number}
                </p>
              </div>
              <div className="no-print flex flex-wrap gap-2">
                {r.status === 'SUBMITTED' && can(P.REVIEW_CLOSURE_REQUEST) && (
                  <ActionButton label="Start review" input="optional" inputLabel="Notes" description="Take this request under review. The member will see it is being reviewed."
                    action={(notes) => adminApi.closures.action(r.id, 'start-review', { notes })} />
                )}
                {r.status === 'UNDER_REVIEW' && can(P.APPROVE_CLOSURE_REQUEST) && (
                  <ActionButton label="Approve" input="optional" inputLabel="Notes" description="Approving freezes the settlement statement. No money moves until the closure is executed."
                    action={(notes) => adminApi.closures.action(r.id, 'approve', { notes })} />
                )}
                {open && can(P.APPROVE_CLOSURE_REQUEST) && (
                  <ActionButton label="Reject" variant="danger" input="required" description="The member will see this reason."
                    action={(reason) => adminApi.closures.action(r.id, 'reject', { reason })} />
                )}
              </div>
            </div>

            {executed && (
              <Alert tone="success" title={executed.batch ? 'Settlement batch created' : 'Membership closed'}>
                {executed.batch ? (
                  <>Settlement batch <Link className="font-semibold underline" to={`/admin/transactions/batches/${executed.batch.id}`}>{executed.batch.reference}</Link> ({formatNaira(executed.batch.total_amount)}) is ready. Open it and submit it for approval; a second officer then approves it, and the membership closes when it is posted.</>
                ) : 'There was nothing to settle, so the membership was closed straight away.'}
              </Alert>
            )}

            <div className="grid gap-6 lg:grid-cols-3">
              <div className="space-y-6 lg:col-span-2">
                {r.settlement_statement && Object.keys(r.settlement_statement).length > 0 && <Settlement statement={r.settlement_statement} frozen />}
                {(open || r.status === 'APPROVED') && (
                  <QueryState query={live}>{(s) => (r.status === 'APPROVED' ? (
                    Number(s.net_payable) !== Number(r.settlement_statement?.net_payable) && <Alert tone="warning">Balances have changed since approval: the net payable is now {formatNaira(s.net_payable)}. Execution uses current balances.</Alert>
                  ) : <Settlement statement={s} />)}</QueryState>
                )}

                {r.status === 'APPROVED' && !r.settlement_batch && can(P.EXECUTE_ACCOUNT_CLOSURE) && (
                  <Card>
                    <CardHeader title="Execute closure" description="Offsets loans from the member's funds, pays out the balance and closes the accounts, as one settlement batch that needs a second officer's approval." />
                    <CardBody className="flex flex-wrap items-end gap-3">
                      <div className="w-48"><TextField label="Value date" type="date" value={valueDate} max={today()} onChange={(e) => setValueDate(e.target.value)} /></div>
                      <ActionButton label="Execute closure" variant="danger" description={`Execute the closure of ${r.member.full_name}'s membership with value date ${valueDate}?`}
                        action={() => adminApi.closures.action(r.id, 'execute', { value_date: valueDate })} onDone={setExecuted} />
                    </CardBody>
                  </Card>
                )}
                {r.settlement_batch && !executed && (
                  <Alert title={`Settlement batch ${r.settlement_batch.reference}`}>
                    {r.settlement_batch.status === 'VALIDATED' ? 'Ready to be submitted for approval.' : 'Submitted; awaiting approval by a second officer.'} The membership closes when it is posted.{' '}
                    <Link className="font-semibold underline" to={`/admin/transactions/batches/${r.settlement_batch.id}`}>Open batch</Link>
                  </Alert>
                )}
              </div>

              <div className="space-y-6">
                <Card>
                  <CardHeader title="Request" />
                  <CardBody className="space-y-4">
                    <DetailList columns={1} items={[
                      ['Reason', r.reason_category_label],
                      ['Explanation', r.reason],
                      ['Additional information', r.additional_information],
                      ['Submitted', formatDateTime(r.created_at)],
                    ]} />
                    {r.has_attachment && <Button size="sm" variant="secondary" icon={Download} loading={attachment.isPending} onClick={() => attachment.mutate()}>Attachment</Button>}
                    <ErrorAlert error={attachment.error} />
                  </CardBody>
                </Card>
                <Card>
                  <CardHeader title="Decision trail" />
                  <CardBody>
                    <DetailList columns={1} items={[
                      ['Reviewed by', r.reviewed_by && `${r.reviewed_by} · ${formatDateTime(r.reviewed_at)}`],
                      ['Review notes', r.review_notes],
                      ['Decided by', r.decided_by && `${r.decided_by} · ${formatDateTime(r.decided_at)}`],
                      ['Decision notes', r.decision_reason],
                      ['Closed by', r.closed_by && `${r.closed_by} · ${formatDateTime(r.closed_at)}`],
                      r.withdrawn_at && ['Withdrawn by member', formatDateTime(r.withdrawn_at)],
                    ]} />
                  </CardBody>
                </Card>
              </div>
            </div>
          </div>
        )}
      </QueryState>
    </>
  );
}
