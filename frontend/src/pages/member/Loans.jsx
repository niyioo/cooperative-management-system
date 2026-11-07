import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { FilePlus2, HandCoins } from 'lucide-react';
import { memberApi } from '../../api/member';
import { StatusBadge } from '../../components/ui/Badge';
import Button from '../../components/ui/Button';
import { Card, CardHeader } from '../../components/ui/Card';
import EmptyState from '../../components/ui/EmptyState';
import PageHeader from '../../components/ui/PageHeader';
import QueryState from '../../components/ui/QueryState';
import { Money, Table, Td, Th } from '../../components/ui/Table';
import { formatDate } from '../../lib/format';

export default function Loans() {
  const loans = useQuery({ queryKey: ['me', 'loans'], queryFn: memberApi.loans });
  const applications = useQuery({ queryKey: ['me', 'applications'], queryFn: memberApi.applications });

  return (
    <div className="space-y-6">
      <PageHeader
        title="My Loans"
        description="Your loans, repayments and applications."
        actions={
          <Link to="/member/loans/apply">
            <Button icon={FilePlus2}>APPLY FOR LOAN</Button>
          </Link>
        }
      />

      <Card>
        <CardHeader title="Loans" />
        <QueryState query={loans}>
          {(data) =>
            data.results.length ? (
              <Table caption="Your loans">
                <thead>
                  <tr>
                    <Th>Loan</Th><Th align="right">Amount</Th><Th align="right">Interest</Th><Th align="right">Outstanding</Th><Th>Matures</Th><Th>Status</Th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {data.results.map((loan) => (
                    <tr key={loan.id} className="hover:bg-slate-50">
                      <Td>
                        <Link to={`/member/loans/${loan.id}`} className="font-semibold text-brand-700 hover:underline">{loan.reference}</Link>
                        <p className="text-xs text-slate-500">{loan.product_name} · disbursed {formatDate(loan.disbursed_on)}</p>
                      </Td>
                      <Td align="right"><Money value={loan.principal} /></Td>
                      <Td align="right"><Money value={loan.total_interest} /></Td>
                      <Td align="right"><Money value={loan.outstanding} className="font-semibold" /></Td>
                      <Td className="whitespace-nowrap">{formatDate(loan.maturity_date)}</Td>
                      <Td><StatusBadge status={loan.status} label={loan.status_label} /></Td>
                    </tr>
                  ))}
                </tbody>
              </Table>
            ) : (
              <EmptyState icon={HandCoins} title="You have no loans">When a loan is disbursed it appears here with its repayment schedule.</EmptyState>
            )
          }
        </QueryState>
      </Card>

      <Card>
        <CardHeader title="Applications" />
        <QueryState query={applications}>
          {(data) =>
            data.results.length ? (
              <Table caption="Your loan applications">
                <thead>
                  <tr><Th>Application</Th><Th align="right">Requested</Th><Th>Term</Th><Th>Submitted</Th><Th>Status</Th></tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {data.results.map((a) => (
                    <tr key={a.id} className="hover:bg-slate-50">
                      <Td>
                        <Link to={`/member/loans/applications/${a.id}`} className="font-semibold text-brand-700 hover:underline">{a.reference}</Link>
                        <p className="text-xs text-slate-500">{a.product_name}</p>
                      </Td>
                      <Td align="right"><Money value={a.amount_requested} /></Td>
                      <Td>{a.term_months} months</Td>
                      <Td className="whitespace-nowrap">{formatDate(a.submitted_at)}</Td>
                      <Td><StatusBadge status={a.status} label={a.status_label} /></Td>
                    </tr>
                  ))}
                </tbody>
              </Table>
            ) : (
              <EmptyState title="No applications">Use “Apply for loan” to start one.</EmptyState>
            )
          }
        </QueryState>
      </Card>
    </div>
  );
}
