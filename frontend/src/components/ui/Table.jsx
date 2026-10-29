import { formatNaira } from '../../lib/format';

// Full class names, so Tailwind's build can see them.
const ALIGN = { left: 'text-left', right: 'text-right', center: 'text-center' };

/** Responsive table: scrolls sideways inside its card on small screens instead of breaking the layout. */
export function Table({ children, caption }) {
  return (
    <div className="overflow-x-auto">
      <table className="min-w-full divide-y divide-slate-100 text-sm">
        {caption && <caption className="sr-only">{caption}</caption>}
        {children}
      </table>
    </div>
  );
}

export function Th({ children, align = 'left', className = '', ...props }) {
  return (
    <th scope="col" {...props} className={`whitespace-nowrap bg-slate-50 px-4 py-2.5 text-xs font-semibold uppercase tracking-wide text-slate-500 ${ALIGN[align]} ${className}`}>
      {children}
    </th>
  );
}

export function Td({ children, align = 'left', className = '', ...props }) {
  return <td {...props} className={`px-4 py-3 text-slate-700 ${ALIGN[align]} ${className}`}>{children}</td>;
}

export function Money({ value, className = '' }) {
  return <span className={`tabular whitespace-nowrap ${className}`}>{formatNaira(value)}</span>;
}
