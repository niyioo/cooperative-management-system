import { useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { ArrowLeft, Download, Upload } from 'lucide-react';
import { adminApi } from '../../../api/admin';
import ActionButton from '../../../components/officer/ActionButton';
import DataTable from '../../../components/officer/DataTable';
import useList from '../../../components/officer/useList';
import { Alert, ErrorAlert } from '../../../components/ui/Alert';
import { StatusBadge } from '../../../components/ui/Badge';
import Button from '../../../components/ui/Button';
import { Card, CardBody, CardHeader } from '../../../components/ui/Card';
import { CheckboxField } from '../../../components/ui/Field';
import PageHeader from '../../../components/ui/PageHeader';
import { Table, Td, Th } from '../../../components/ui/Table';
import { saveBlob } from '../../../lib/download';
import { formatDateTime } from '../../../lib/format';

function Report({ item, onCommitted }) {
  const [sendActivation, setSendActivation] = useState(true);
  const { report } = item;
  return (
    <Card>
      <CardHeader title={`Import ${item.reference}`} description={item.original_filename} action={<StatusBadge status={item.status === 'READY' ? 'APPROVED' : item.status === 'HAS_ERRORS' ? 'REJECTED' : 'CLOSED'} label={item.status_label} />} />
      <CardBody className="space-y-4">
        <p className="text-sm text-slate-700">
          {item.total_rows} row(s) read · <strong>{item.valid_rows} valid</strong>
          {report.error_rows ? <> · <strong className="text-red-700">{report.error_rows} with errors</strong></> : null}
          {item.status === 'COMMITTED' && <> · {item.created_count} member(s) created</>}
        </p>
        {report.file_errors?.length > 0 && <Alert tone="error">{report.file_errors.join(' ')}</Alert>}
        {report.unknown_columns?.length > 0 && <Alert tone="warning" title="Ignored columns">{report.unknown_columns.join(', ')}</Alert>}
        {report.errors?.length > 0 && (
          <div className="max-h-96 overflow-y-auto rounded-lg border border-red-100">
            <Table caption="Row errors">
              <thead><tr><Th>Row</Th><Th>Problems</Th></tr></thead>
              <tbody className="divide-y divide-slate-100">
                {report.errors.map((e) => (
                  <tr key={e.row}>
                    <Td className="font-semibold">{e.row}</Td>
                    <Td><ul className="space-y-0.5 text-xs text-red-700">{Object.entries(e.errors).map(([f, msgs]) => <li key={f}><strong>{f}:</strong> {[].concat(msgs).join(' ')}</li>)}</ul></Td>
                  </tr>
                ))}
              </tbody>
            </Table>
          </div>
        )}
        {item.status === 'HAS_ERRORS' && <Alert tone="warning">Fix the rows above in your spreadsheet and upload it again. Nothing is imported until every row is valid.</Alert>}
        {item.status === 'READY' && (
          <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg bg-slate-50 p-4">
            <CheckboxField label="Email activation links to members who have an email address" checked={sendActivation} onChange={(e) => setSendActivation(e.target.checked)} />
            <ActionButton label={`Import ${item.valid_rows} member(s)`} description="All rows are created together, or none are if anything has changed since the upload."
              action={() => adminApi.memberImports.commit(item.id, sendActivation)} onDone={onCommitted} />
          </div>
        )}
      </CardBody>
    </Card>
  );
}

export default function MemberImports() {
  const queryClient = useQueryClient();
  const [current, setCurrent] = useState(null);
  const list = useList(['admin', 'member-imports'], adminApi.memberImports.list);
  const upload = useMutation({
    mutationFn: adminApi.memberImports.upload,
    onSuccess: (data) => {
      setCurrent(data);
      queryClient.invalidateQueries({ queryKey: ['admin', 'member-imports'] });
    },
  });
  const template = useMutation({ mutationFn: () => adminApi.memberImports.template().then((res) => saveBlob(res, 'member-import-template.xlsx')) });

  return (
    <>
      <Link to="/admin/members" className="inline-flex items-center gap-1 text-sm font-medium text-brand-600 hover:underline">
        <ArrowLeft className="h-4 w-4" aria-hidden="true" /> Members
      </Link>
      <div className="mt-2">
        <PageHeader title="Import members" description="Register many members at once from an Excel or CSV file."
          actions={<Button variant="secondary" icon={Download} loading={template.isPending} onClick={() => template.mutate()}>Download template</Button>} />
      </div>
      <div className="space-y-6">
        <Card>
          <CardBody className="space-y-3">
            <p className="text-sm text-slate-600">Upload the completed template. Each row is checked first; you then review the report and confirm the import.</p>
            <label className="inline-flex cursor-pointer items-center gap-2 rounded-lg bg-brand-600 px-4 py-2 text-sm font-semibold text-white hover:bg-brand-700">
              <Upload className="h-4 w-4" aria-hidden="true" /> {upload.isPending ? 'Checking file…' : 'Choose file'}
              <input type="file" accept=".xlsx,.csv" className="sr-only" disabled={upload.isPending}
                onChange={(e) => { if (e.target.files[0]) upload.mutate(e.target.files[0]); e.target.value = ''; }} />
            </label>
            <ErrorAlert error={upload.error || template.error} />
          </CardBody>
        </Card>

        {current && <Report item={current} onCommitted={setCurrent} />}

        <DataTable title="Previous imports" query={list.query} page={list.page} onPage={list.setPage} empty="No imports yet."
          columns={[
            { header: 'Reference', cell: (i) => <button type="button" className="font-medium text-brand-600 hover:underline" onClick={() => setCurrent(i)}>{i.reference}</button> },
            { header: 'File', cell: (i) => i.original_filename },
            { header: 'Rows', align: 'right', cell: (i) => `${i.valid_rows}/${i.total_rows}` },
            { header: 'Uploaded', cell: (i) => <span className="text-xs">{formatDateTime(i.created_at)}<br />{i.created_by}</span> },
            { header: 'Status', cell: (i) => i.status_label },
          ]} />
      </div>
    </>
  );
}
