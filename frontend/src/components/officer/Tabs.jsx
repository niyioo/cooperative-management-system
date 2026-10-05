import { NavLink } from 'react-router-dom';

const BASE = 'whitespace-nowrap border-b-2 px-4 py-2.5 text-sm font-semibold transition-colors';
const tabClass = (active) => `${BASE} ${active ? 'border-brand-600 text-brand-700' : 'border-transparent text-slate-500 hover:text-slate-800'}`;

function Count({ value }) {
  if (!value) return null;
  return <span className="ml-2 rounded-full bg-red-600 px-1.5 py-0.5 text-[10px] font-bold text-white">{value}</span>;
}

/**
 * Tabs in two modes:
 *  - route tabs ({ to }) when each tab is its own URL (linkable, survive reloads);
 *  - in-page tabs ({ key }) with value/onChange for sections of one page.
 */
export default function Tabs({ tabs, value, onChange, label = 'Sections' }) {
  const visible = tabs.filter((t) => t.show !== false);
  return (
    <div className="no-print mb-6 flex gap-1 overflow-x-auto border-b border-slate-200" role={onChange ? 'tablist' : undefined} aria-label={label}>
      {visible.map((tab) =>
        tab.to ? (
          <NavLink key={tab.to} to={tab.to} end={tab.end} className={({ isActive }) => tabClass(isActive)}>
            {tab.label}
            <Count value={tab.count} />
          </NavLink>
        ) : (
          <button key={tab.key} type="button" role="tab" aria-selected={value === tab.key} className={tabClass(value === tab.key)} onClick={() => onChange(tab.key)}>
            {tab.label}
            <Count value={tab.count} />
          </button>
        ),
      )}
    </div>
  );
}
