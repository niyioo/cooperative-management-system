import { ChevronLeft, ChevronRight } from 'lucide-react';
import Button from './Button';

export default function Pagination({ page, count, pageSize = 20, onChange }) {
  const pages = Math.max(1, Math.ceil((count || 0) / pageSize));
  if (pages <= 1) return null;
  return (
    <nav className="no-print flex flex-wrap items-center justify-between gap-2 border-t border-slate-100 px-5 py-3 text-sm text-slate-600" aria-label="Pagination">
      <span>
        Page {page} of {pages} · {count} records
      </span>
      <div className="flex gap-2">
        <Button variant="secondary" size="sm" icon={ChevronLeft} disabled={page <= 1} onClick={() => onChange(page - 1)}>
          Previous
        </Button>
        <Button variant="secondary" size="sm" disabled={page >= pages} onClick={() => onChange(page + 1)}>
          Next <ChevronRight className="h-4 w-4" aria-hidden="true" />
        </Button>
      </div>
    </nav>
  );
}
