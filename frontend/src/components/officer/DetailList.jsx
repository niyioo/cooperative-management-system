/** Label/value pairs in a responsive grid. items: [[label, value]]; empty values show a dash. */
export default function DetailList({ items, columns = 2 }) {
  const cols = columns === 3 ? 'sm:grid-cols-2 lg:grid-cols-3' : 'sm:grid-cols-2';
  return (
    <dl className={`grid gap-x-6 gap-y-4 ${cols}`}>
      {items.filter(Boolean).map(([label, value]) => (
        <div key={label}>
          <dt className="text-xs font-medium uppercase tracking-wide text-slate-500">{label}</dt>
          <dd className="mt-0.5 break-words text-sm text-slate-900">{value === null || value === undefined || value === '' ? '—' : value}</dd>
        </div>
      ))}
    </dl>
  );
}
