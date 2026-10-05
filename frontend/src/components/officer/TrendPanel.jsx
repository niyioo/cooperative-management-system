import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { formatNaira, monthLabel } from '../../lib/format';

// Brand 500 — passes the palette validator's lightness band and contrast on white
// (brand-600 #293c9c is too dark for a data mark).
const BAR = '#3a4fb6';
const compact = new Intl.NumberFormat('en-NG', { notation: 'compact', maximumFractionDigits: 1 });

function ChartTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs shadow-lg">
      <p className="font-semibold text-slate-900">{monthLabel(label, true)}</p>
      <p className="tabular mt-0.5 text-slate-700">{formatNaira(payload[0].value)}</p>
    </div>
  );
}

/**
 * One small-multiple panel: a single monthly series, so the title names it and
 * no legend is needed. A table view sits underneath for screen readers and exact figures.
 */
export default function TrendPanel({ title, data, dataKey }) {
  const rows = data.map((d) => ({ month: d.month, value: Number(d[dataKey]) }));
  const total = rows.reduce((sum, r) => sum + r.value, 0);
  return (
    <figure className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
      <figcaption>
        <p className="text-sm font-semibold text-slate-900">{title}</p>
        <p className="text-xs text-slate-500">
          Last 12 months · <span className="tabular font-medium text-slate-700">{formatNaira(total)}</span>
        </p>
      </figcaption>
      <div className="mt-3 h-40" aria-hidden="true">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={rows} margin={{ top: 4, right: 4, bottom: 0, left: 0 }}>
            <CartesianGrid vertical={false} stroke="#eef2f7" />
            <XAxis dataKey="month" tickFormatter={(m) => monthLabel(m).charAt(0)} tickLine={false} axisLine={{ stroke: '#cbd5e1' }}
              tick={{ fontSize: 11, fill: '#64748b' }} interval={0} />
            <YAxis tickFormatter={(v) => compact.format(v)} tickLine={false} axisLine={false} width={44} tick={{ fontSize: 11, fill: '#64748b' }} />
            <Tooltip content={<ChartTooltip />} cursor={{ fill: '#f1f5f9' }} />
            <Bar dataKey="value" fill={BAR} radius={[4, 4, 0, 0]} maxBarSize={14} />
          </BarChart>
        </ResponsiveContainer>
      </div>
      <details className="mt-2 text-xs">
        <summary className="cursor-pointer text-slate-500 hover:text-slate-700">Table view</summary>
        <table className="mt-2 w-full">
          <caption className="sr-only">{title} by month</caption>
          <thead>
            <tr className="text-left text-slate-500"><th scope="col" className="py-1 font-medium">Month</th><th scope="col" className="py-1 text-right font-medium">Amount</th></tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.month} className="border-t border-slate-100">
                <td className="py-1 text-slate-700">{monthLabel(r.month, true)}</td>
                <td className="tabular py-1 text-right text-slate-900">{formatNaira(r.value)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </details>
    </figure>
  );
}
