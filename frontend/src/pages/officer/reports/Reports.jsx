import { useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { useMutation, useQuery } from '@tanstack/react-query';
import { ArrowLeft, ChevronRight, FileSpreadsheet, FileText, Play, Printer } from 'lucide-react';
import { adminApi } from '../../../api/admin';
import MemberPicker from '../../../components/officer/MemberPicker';
import useReference from '../../../components/officer/useReference';
import { Alert, ErrorAlert } from '../../../components/ui/Alert';
import Button from '../../../components/ui/Button';
import { Card, CardBody, CardHeader } from '../../../components/ui/Card';
import EmptyState from '../../../components/ui/EmptyState';
import { SelectField, TextField } from '../../../components/ui/Field';
import PageHeader from '../../../components/ui/PageHeader';
import QueryState from '../../../components/ui/QueryState';
import { Money, Table, Td, Th } from '../../../components/ui/Table';
import { today } from '../../../lib/choices';
import { saveBlob } from '../../../lib/download';
import { formatDate, formatDateTime } from '../../../lib/format';

const MODULE_ORDER = ['Members', 'Savings', 'Loans', 'Investments', 'Dividends', 'Ledger'];
const PRODUCT_SOURCE = { Savings: 'savingsProducts', Loans: 'loanProducts', Investments: 'investmentProducts' };
const ALIGN = { money: 'right', int: 'right', percent: 'right' };

function useCatalogue() {
  return useQuery({ queryKey: ['admin', 'report-catalogue'], queryFn: adminApi.reports.catalogue, staleTime: 5 * 60_000 });
}

export function ReportsHome() {
  const catalogue = useCatalogue();
  return (
    <>
      <PageHeader title="Reports" description="Run a report on screen, then export it to Excel or PDF. Exports are recorded in the audit log." />
      <QueryState query={catalogue}>
        {(reports) => {
          if (!reports.length) return <Card><EmptyState title="No reports available for your role" /></Card>;
          const modules = MODULE_ORDER.filter((m) => reports.some((r) => r.module === m));
          return (
            <div className="space-y-6">
              {modules.map((module) => (
                <section key={module} aria-labelledby={`module-${module}`}>
                  <h2 id={`module-${module}`} className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-500">{module}</h2>
                  <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
                    {reports.filter((r) => r.module === module).map((r) => (
                      <Link key={r.key} to={`/admin/reports/${r.key}`}
                        className="group flex items-start justify-between gap-3 rounded-xl border border-slate-200 bg-white p-4 shadow-sm transition hover:border-brand-300 hover:shadow">
                        <span>
                          <span className="block font-semibold text-slate-900 group-hover:text-brand-700">{r.title}</span>
                          <span className="mt-1 block text-sm text-slate-500">{r.description}</span>
                        </span>
                        <ChevronRight className="mt-1 h-4 w-4 shrink-0 text-slate-400 group-hover:text-brand-600" aria-hidden="true" />
                      </Link>
                    ))}
                  </div>
                </section>
              ))}
            </div>
          );
        }}
      </QueryState>
    </>
  );
}

function initialFilters(report) {
  const values = {};
  report.filters.forEach((name) => { values[name] = ''; });
  if (report.filters.includes('as_at')) values.as_at = today();
  if (report.filters.includes('year')) values.year = String(new Date().getFullYear());
  return values;
}

function Filters({ report, values, setValues, member, setMember }) {
  const productSource = PRODUCT_SOURCE[report.module];
  const products = useReference(productSource || 'savingsProducts', {}, !!productSource && report.filters.includes('product'));
  const departments = useReference('departments', {}, report.filters.includes('department'));
  const set = (name) => (e) => setValues((v) => ({ ...v, [name]: e.target.value }));
  const required = (name) => report.required_filters.includes(name);
  const fields = {
    member: <div className="sm:col-span-2"><MemberPicker value={member} onChange={setMember} status="" required={required('member')} /></div>,
    as_at: <TextField label="Balances as at" type="date" max={today()} value={values.as_at} onChange={set('as_at')} />,
    date_from: <TextField label="From" type="date" value={values.date_from} onChange={set('date_from')} />,
    date_to: <TextField label="To" type="date" value={values.date_to} onChange={set('date_to')} />,
    year: <TextField label="Year" type="number" min="2000" max="2100" value={values.year} onChange={set('year')} />,
    status: (
      <SelectField label="Status" value={values.status} onChange={set('status')}>
        <option value="">All</option>
        {report.status_choices.map((c) => <option key={c.value} value={c.value}>{c.label}</option>)}
      </SelectField>
    ),
    txn_type: (
      <SelectField label="Transaction type" value={values.txn_type} onChange={set('txn_type')}>
        <option value="">All</option>
        {report.txn_type_choices.map((c) => <option key={c.value} value={c.value}>{c.label}</option>)}
      </SelectField>
    ),
    product: (
      <SelectField label="Product" value={values.product} onChange={set('product')}>
        <option value="">All</option>
        {(products.data || []).map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
      </SelectField>
    ),
    department: (
      <SelectField label="Department" value={values.department} onChange={set('department')}>
        <option value="">All</option>
        {(departments.data || []).map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
      </SelectField>
    ),
  };
  return <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">{report.filters.map((name) => <div key={name} className={name === 'member' ? 'contents' : ''}>{fields[name]}</div>)}</div>;
}

function cell(value, kind) {
  if (value === null || value === undefined || value === '') return <span className="text-slate-300">—</span>;
  if (kind === 'money') return <Money value={value} />;
  if (kind === 'date') return <span className="whitespace-nowrap">{formatDate(value)}</span>;
  if (kind === 'percent') return `${Number(value)}%`;
  if (kind === 'int') return <span className="tabular">{Number(value).toLocaleString('en-NG')}</span>;
  return value;
}

function summaryValue(item) {
  if (item.kind === 'money') return <Money value={item.value} />;
  if (item.kind === 'percent') return `${Number(item.value)}%`;
  if (item.kind === 'int') return Number(item.value).toLocaleString('en-NG');
  return item.value;
}

function ReportResult({ data }) {
  const hasTotals = data.columns.some((c) => c.total);
  return (
    <div className="space-y-4">
      {data.summary.length > 0 && (
        <dl className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {data.summary.map((s) => (
            <div key={s.label} className="rounded-xl border border-slate-200 bg-white px-4 py-3 shadow-sm">
              <dt className="text-xs font-medium text-slate-500">{s.label}</dt>
              <dd className="tabular mt-1 text-lg font-bold text-slate-900">{summaryValue(s)}</dd>
            </div>
          ))}
        </dl>
      )}
      {data.truncated && (
        <Alert tone="warning">Showing the first {data.rows.length.toLocaleString()} of {data.total_rows.toLocaleString()} rows. Totals and the exports include every row.</Alert>
      )}
      <Card>
        <div className="flex flex-wrap items-baseline justify-between gap-2 border-b border-slate-100 px-5 py-3 text-xs text-slate-500">
          <span>{data.filters.length ? data.filters.map((f) => `${f.label}: ${f.value}`).join(' · ') : 'No filters'}</span>
          <span>{data.total_rows.toLocaleString()} row(s) · generated {formatDateTime(data.generated_at)}</span>
        </div>
        {data.rows.length ? (
          <Table caption={data.title}>
            <thead><tr>{data.columns.map((c) => <Th key={c.key} align={ALIGN[c.kind]}>{c.label}</Th>)}</tr></thead>
            <tbody className="divide-y divide-slate-100">
              {data.rows.map((row, i) => (
                // Report rows have no id; position is their identity within one run.
                <tr key={i} className="hover:bg-slate-50">
                  {data.columns.map((c) => <Td key={c.key} align={ALIGN[c.kind]} className="whitespace-nowrap">{cell(row[c.key], c.kind)}</Td>)}
                </tr>
              ))}
            </tbody>
            {hasTotals && (
              <tfoot className="border-t-2 border-slate-200 bg-slate-50 font-semibold">
                <tr>
                  {data.columns.map((c, i) => (
                    <Td key={c.key} align={ALIGN[c.kind]}>{i === 0 ? 'Totals' : c.total ? cell(data.totals[c.key], c.kind) : ''}</Td>
                  ))}
                </tr>
              </tfoot>
            )}
          </Table>
        ) : <EmptyState title="No records match these filters" />}
      </Card>
    </div>
  );
}

function ReportRunner({ report }) {
  const [values, setValues] = useState(() => initialFilters(report));
  const [member, setMember] = useState(null);
  const params = () => {
    const p = Object.fromEntries(Object.entries(values).filter(([, v]) => v !== ''));
    if (member) p.member = member.id;
    return p;
  };
  const needsMember = report.required_filters.includes('member');
  const [applied, setApplied] = useState(() => (needsMember ? null : params()));
  const result = useQuery({
    queryKey: ['admin', 'report', report.key, applied],
    queryFn: () => adminApi.reports.run(report.key, applied),
    enabled: applied !== null,
  });
  const exporter = useMutation({
    mutationFn: (format) => adminApi.reports.export(report.key, applied, format).then((res) => saveBlob(res, `${report.key}.${format}`)),
  });
  const ready = !needsMember || member;

  return (
    <div className="space-y-6">
      <Card className="no-print">
        <CardHeader title="Filters" />
        <CardBody className="space-y-4">
          <Filters report={report} values={values} setValues={setValues} member={member} setMember={setMember} />
          <div className="flex flex-wrap items-center justify-between gap-3">
            <Button icon={Play} disabled={!ready} loading={result.isFetching} onClick={() => setApplied(params())}>Run report</Button>
            {applied && result.data && (
              <div className="flex flex-wrap gap-2">
                {report.can_export && (
                  <>
                    <Button variant="secondary" icon={FileSpreadsheet} loading={exporter.isPending && exporter.variables === 'xlsx'} onClick={() => exporter.mutate('xlsx')}>Excel</Button>
                    <Button variant="secondary" icon={FileText} loading={exporter.isPending && exporter.variables === 'pdf'} onClick={() => exporter.mutate('pdf')}>PDF</Button>
                  </>
                )}
                <Button variant="ghost" icon={Printer} onClick={() => window.print()}>Print</Button>
              </div>
            )}
          </div>
          <ErrorAlert error={exporter.error} />
          {!report.can_export && <p className="text-xs text-slate-500">Your role can view reports but not export them.</p>}
        </CardBody>
      </Card>
      {applied === null ? (
        <Card><EmptyState title="Choose a member to run this report" /></Card>
      ) : (
        <QueryState query={result} loadingLabel="Running the report…">{(data) => <ReportResult data={data} />}</QueryState>
      )}
    </div>
  );
}

export function ReportPage() {
  const { key } = useParams();
  const catalogue = useCatalogue();
  return (
    <>
      <Link to="/admin/reports" className="no-print inline-flex items-center gap-1 text-sm font-medium text-brand-600 hover:underline">
        <ArrowLeft className="h-4 w-4" aria-hidden="true" /> Reports
      </Link>
      <QueryState query={catalogue}>
        {(reports) => {
          const report = reports.find((r) => r.key === key);
          if (!report) return <Card className="mt-3"><EmptyState title="This report isn't available for your role" /></Card>;
          return (
            <div className="mt-2">
              <PageHeader title={report.title} description={report.description} />
              <ReportRunner key={report.key} report={report} />
            </div>
          );
        }}
      </QueryState>
    </>
  );
}
