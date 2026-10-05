import { Table, Td, Th } from '../ui/Table';
import { formatNaira, monthLabel } from '../../lib/format';

/** Month-by-month expected vs paid for the statutory monthly contribution (newest first). */
export default function ContributionHistory({ history, caption = 'Monthly contributions' }) {
  if (!history?.length) return <p className="px-5 py-4 text-sm text-slate-500">No months are due yet.</p>;
  return (
    <Table caption={caption}>
      <thead>
        <tr><Th>Month</Th><Th align="right">Expected</Th><Th align="right">Paid</Th><Th align="right">Difference</Th></tr>
      </thead>
      <tbody className="divide-y divide-slate-100">
        {history.map((m) => {
          const short = Number(m.paid) - Number(m.expected);
          return (
            <tr key={m.month}>
              <Td className="whitespace-nowrap">{monthLabel(m.month, true)}</Td>
              <Td align="right" className="tabular">{formatNaira(m.expected)}</Td>
              <Td align="right" className="tabular">{Number(m.paid) ? formatNaira(m.paid) : '—'}</Td>
              <Td align="right" className={`tabular ${short < 0 ? 'font-semibold text-red-700' : short > 0 ? 'text-emerald-700' : 'text-slate-400'}`}>
                {short === 0 ? '—' : `${short > 0 ? '+' : '−'}${formatNaira(Math.abs(short))}`}
              </Td>
            </tr>
          );
        })}
      </tbody>
    </Table>
  );
}
