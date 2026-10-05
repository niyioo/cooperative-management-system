import { Card, CardHeader } from '../ui/Card';
import EmptyState from '../ui/EmptyState';
import Pagination from '../ui/Pagination';
import QueryState from '../ui/QueryState';
import { Table, Td, Th } from '../ui/Table';

/**
 * A card with a paginated table for a list query.
 *   columns: [{ header, cell: (row) => node, align, className }]
 */
export default function DataTable({ title, description, action, query, columns, page, onPage, empty = 'Nothing here yet.', rowKey = (r) => r.id, toolbar }) {
  return (
    <Card>
      {(title || action) && <CardHeader title={title} description={description} action={action} />}
      {toolbar && <div className="border-b border-slate-100 px-5 py-3">{toolbar}</div>}
      <QueryState query={query}>
        {(data) => {
          const rows = Array.isArray(data) ? data : data.results;
          if (!rows.length) return <EmptyState title={empty} />;
          return (
            <>
              <Table caption={title}>
                <thead>
                  <tr>{columns.map((c) => <Th key={c.header} align={c.align}>{c.header}</Th>)}</tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {rows.map((row) => (
                    <tr key={rowKey(row)} className="hover:bg-slate-50">
                      {columns.map((c) => <Td key={c.header} align={c.align} className={c.className}>{c.cell(row)}</Td>)}
                    </tr>
                  ))}
                </tbody>
              </Table>
              {!Array.isArray(data) && onPage && <Pagination page={page} count={data.count} onChange={onPage} />}
            </>
          );
        }}
      </QueryState>
    </Card>
  );
}
