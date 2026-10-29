import { useState } from 'react';
import { keepPreviousData, useQuery } from '@tanstack/react-query';
import { Download, FileSpreadsheet, Printer, Search } from 'lucide-react';
import { memberApi } from '../../api/member';
import { ErrorAlert } from '../../components/ui/Alert';
import { StatusBadge } from '../../components/ui/Badge';
import Button from '../../components/ui/Button';
import { Card, CardBody } from '../../components/ui/Card';
import EmptyState from '../../components/ui/EmptyState';
import { SelectField, TextField } from '../../components/ui/Field';
import PageHeader from '../../components/ui/PageHeader';
import Pagination from '../../components/ui/Pagination';
import QueryState from '../../components/ui/QueryState';
import { Money, Table, Td, Th } from '../../components/ui/Table';
import { saveBlob } from '../../lib/download';
import { formatDate } from '../../lib/format';

const TYPES = [
  ['', 'All types'],
  ['SAVINGS_CONTRIBUTION', 'Savings contributions'],
  ['SAVINGS_OPENING_BALANCE', 'Savings balance brought forward'],
  ['SAVINGS_CYCLE_PAYOUT', 'Christmas Savings payout'],
  ['LOAN_DISBURSEMENT', 'Loan disbursements'],
  ['LOAN_INTEREST_CHARGE', 'Loan interest'],
  ['LOAN_REPAYMENT', 'Loan repayments'],
  ['INVESTMENT_CONTRIBUTION', 'Investment contributions'],
  ['DIVIDEND_PAYMENT', 'Dividend payments'],
  ['ADJUSTMENT', 'Adjustments'],
  ['REVERSAL', 'Reversals'],
];

export default function Transactions() {
  const [filters, setFilters] = useState({ search: '', txn_type: '', date_from: '', date_to: '' });
  const [page, setPage] = useState(1);
  const [downloading, setDownloading] = useState(null);
  const [downloadError, setDownloadError] = useState(null);
  const params = Object.fromEntries(Object.entries({ ...filters, page }).filter(([, v]) => v !== ''));
  const query = useQuery({ queryKey: ['me', 'transactions', params], queryFn: () => memberApi.transactions(params), placeholderData: keepPreviousData });

  const setFilter = (key, value) => {
    setFilters((f) => ({ ...f, [key]: value }));
    setPage(1);
  };

  const download = async (format) => {
    setDownloading(format);
    setDownloadError(null);
    try {
      const response = await memberApi.statement({ format, date_from: filters.date_from || undefined, date_to: filters.date_to || undefined });
      saveBlob(response, `statement.${format}`);
    } catch (err) {
      setDownloadError(err);
    } finally {
      setDownloading(null);
    }
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title="Transactions"
        description="Every transaction on your accounts."
        actions={
          <>
            <Button variant="secondary" icon={Download} loading={downloading === 'pdf'} onClick={() => download('pdf')}>Statement (PDF)</Button>
            <Button variant="secondary" icon={FileSpreadsheet} loading={downloading === 'xlsx'} onClick={() => download('xlsx')}>Excel</Button>
            <Button variant="ghost" icon={Printer} onClick={() => window.print()}>Print</Button>
          </>
        }
      />
      <ErrorAlert error={downloadError} />
      <Card className="no-print">
        <CardBody className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <div className="relative">
            <TextField label="Search" placeholder="Reference or description" value={filters.search} onChange={(e) => setFilter('search', e.target.value)} />
            <Search className="pointer-events-none absolute right-3 top-9 h-4 w-4 text-slate-400" aria-hidden="true" />
          </div>
          <SelectField label="Type" value={filters.txn_type} onChange={(e) => setFilter('txn_type', e.target.value)}>
            {TYPES.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
          </SelectField>
          <TextField label="From" type="date" value={filters.date_from} onChange={(e) => setFilter('date_from', e.target.value)} />
          <TextField label="To" type="date" value={filters.date_to} onChange={(e) => setFilter('date_to', e.target.value)} />
        </CardBody>
      </Card>
      <Card>
        <QueryState query={query}>
          {(data) =>
            data.results.length ? (
              <>
                <Table caption="Transactions">
                  <thead>
                    <tr><Th>Date</Th><Th>Reference</Th><Th>Type</Th><Th>Description</Th><Th align="right">Amount</Th><Th>Status</Th></tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {data.results.map((t) => (
                      <tr key={t.id}>
                        <Td className="whitespace-nowrap">{formatDate(t.value_date)}</Td>
                        <Td className="whitespace-nowrap font-mono text-xs">{t.reference}</Td>
                        <Td>{t.type_label}</Td>
                        <Td>
                          <p>{t.description}</p>
                          {t.account && <p className="text-xs text-slate-500">{t.account.label} · {t.account.number}</p>}
                        </Td>
                        <Td align="right"><Money value={t.signed_amount} className={t.entry_side === 'CREDIT' ? 'font-semibold text-emerald-700' : 'font-semibold text-slate-800'} /></Td>
                        <Td><StatusBadge status={t.status} label={t.status_label} /></Td>
                      </tr>
                    ))}
                  </tbody>
                </Table>
                <Pagination page={page} count={data.count} onChange={setPage} />
              </>
            ) : (
              <EmptyState title="No transactions match">Try clearing the filters.</EmptyState>
            )
          }
        </QueryState>
      </Card>
      <p className="text-xs text-slate-500">
        Credits (green) add to an account; debits reduce it. For loans, the disbursement and interest are what you owe and repayments reduce it.
      </p>
    </div>
  );
}
