import { useEffect, useState } from 'react';
import { Search } from 'lucide-react';

/** One row of filters above a table. */
export function FilterBar({ children }) {
  return <div className="flex flex-wrap items-end gap-3">{children}</div>;
}

/** Debounced search box. */
export function SearchInput({ value, onChange, placeholder = 'Search…', label = 'Search' }) {
  const [text, setText] = useState(value || '');
  useEffect(() => {
    const timer = setTimeout(() => {
      if (text !== (value || '')) onChange(text);
    }, 300);
    return () => clearTimeout(timer);
  }, [text]); // eslint-disable-line react-hooks/exhaustive-deps
  return (
    <div className="relative min-w-[14rem] flex-1">
      <Search className="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-slate-400" aria-hidden="true" />
      <input type="search" aria-label={label} value={text} onChange={(e) => setText(e.target.value)} placeholder={placeholder}
        className="block w-full rounded-lg border border-slate-300 bg-white py-2 pl-9 pr-3 text-sm shadow-sm" />
    </div>
  );
}

/** Compact select for filters. options: [[value, label]] */
export function FilterSelect({ label, value, onChange, options, allLabel = 'All' }) {
  return (
    <label className="text-xs font-medium text-slate-500">
      <span className="sr-only sm:not-sr-only sm:mb-1 sm:block">{label}</span>
      <select aria-label={label} value={value} onChange={(e) => onChange(e.target.value)}
        className="block rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 shadow-sm">
        <option value="">{allLabel}</option>
        {options.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
      </select>
    </label>
  );
}

export function FilterDate({ label, value, onChange }) {
  return (
    <label className="text-xs font-medium text-slate-500">
      <span className="sr-only sm:not-sr-only sm:mb-1 sm:block">{label}</span>
      <input type="date" aria-label={label} value={value} onChange={(e) => onChange(e.target.value)}
        className="block rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 shadow-sm" />
    </label>
  );
}
