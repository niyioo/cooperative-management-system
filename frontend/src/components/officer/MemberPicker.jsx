import { useEffect, useId, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Search, X } from 'lucide-react';
import { adminApi } from '../../api/admin';

/**
 * Search members by name, membership number, staff number or phone and pick one.
 * value/onChange carry the selected member ({ id, full_name, membership_number }) or null.
 */
export default function MemberPicker({ label = 'Member', value, onChange, error, required, status = 'ACTIVE' }) {
  const id = useId();
  const [term, setTerm] = useState('');
  const [debounced, setDebounced] = useState('');
  useEffect(() => {
    const timer = setTimeout(() => setDebounced(term.trim()), 250);
    return () => clearTimeout(timer);
  }, [term]);
  const results = useQuery({
    queryKey: ['admin', 'member-picker', debounced, status],
    queryFn: () => adminApi.members.list({ search: debounced, status, page_size: 8 }),
    enabled: debounced.length >= 2 && !value,
  });

  return (
    <div>
      <label htmlFor={id} className="mb-1 block text-sm font-medium text-slate-700">
        {label}
        {required && <span className="text-red-600" aria-hidden="true"> *</span>}
      </label>
      {value ? (
        <div className="flex items-center justify-between gap-2 rounded-lg border border-slate-300 bg-slate-50 px-3 py-2 text-sm">
          <span>
            <span className="font-semibold text-slate-900">{value.full_name}</span>
            <span className="ml-2 text-slate-500">{value.membership_number}</span>
          </span>
          <button type="button" onClick={() => onChange(null)} className="rounded p-0.5 text-slate-400 hover:bg-slate-200 hover:text-slate-700" aria-label="Clear member">
            <X className="h-4 w-4" />
          </button>
        </div>
      ) : (
        <div className="relative">
          <Search className="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-slate-400" aria-hidden="true" />
          <input
            id={id}
            type="search"
            value={term}
            onChange={(e) => setTerm(e.target.value)}
            placeholder="Name, membership or staff number"
            className={`block w-full rounded-lg border bg-white py-2 pl-9 pr-3 text-sm shadow-sm ${error ? 'border-red-400' : 'border-slate-300'}`}
            aria-invalid={!!error}
            autoComplete="off"
          />
          {debounced.length >= 2 && (
            <ul className="absolute z-10 mt-1 max-h-60 w-full overflow-y-auto rounded-lg border border-slate-200 bg-white py-1 shadow-lg" role="listbox">
              {results.isPending && <li className="px-3 py-2 text-sm text-slate-500">Searching…</li>}
              {results.data?.results.length === 0 && <li className="px-3 py-2 text-sm text-slate-500">No matching members.</li>}
              {results.data?.results.map((m) => (
                <li key={m.id}>
                  <button type="button" role="option" aria-selected="false" className="flex w-full justify-between gap-3 px-3 py-2 text-left text-sm hover:bg-brand-50"
                    onClick={() => { onChange({ id: m.id, full_name: m.full_name, membership_number: m.membership_number }); setTerm(''); }}>
                    <span className="font-medium text-slate-900">{m.full_name}</span>
                    <span className="text-slate-500">{m.membership_number}</span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
      {error && <p className="mt-1 text-xs font-medium text-red-600">{error}</p>}
    </div>
  );
}
