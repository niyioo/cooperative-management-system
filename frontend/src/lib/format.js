const naira = new Intl.NumberFormat('en-NG', { style: 'currency', currency: 'NGN', minimumFractionDigits: 2 });
const plain = new Intl.NumberFormat('en-NG', { minimumFractionDigits: 2, maximumFractionDigits: 2 });

/** Money arrives from the API as strings ("5000.00") so no precision is lost; format, never do maths on floats. */
export function formatNaira(value) {
  if (value === null || value === undefined || value === '') return '—';
  return naira.format(Number(value));
}

export function formatAmount(value) {
  if (value === null || value === undefined || value === '') return '—';
  return plain.format(Number(value));
}

export function formatDate(value, options = { day: 'numeric', month: 'short', year: 'numeric' }) {
  if (!value) return '—';
  return new Date(value.length === 10 ? `${value}T00:00:00` : value).toLocaleDateString('en-NG', options);
}

export function formatDateTime(value) {
  if (!value) return '—';
  return new Date(value).toLocaleString('en-NG', { day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' });
}

/** "2026-03" -> "Mar" (or "March 2026" with long=true). */
export function monthLabel(key, long = false) {
  const [year, month] = key.split('-').map(Number);
  const date = new Date(year, month - 1, 1);
  return long ? date.toLocaleDateString('en-NG', { month: 'long', year: 'numeric' }) : date.toLocaleDateString('en-NG', { month: 'short' });
}

/** A ledger period ("2026-10" or "2026-10-01") -> "Oct 2026". */
export function formatPeriod(value) {
  if (!value) return '—';
  const [year, month] = value.split('-').map(Number);
  return new Date(year, month - 1, 1).toLocaleDateString('en-NG', { month: 'short', year: 'numeric' });
}

/** Whole months from start to end date inclusive ("2026-01-01" to "2026-10-31" -> 10). */
export function monthsInclusive(start, end) {
  const [sy, sm] = start.split('-').map(Number);
  const [ey, em] = end.split('-').map(Number);
  return (ey - sy) * 12 + (em - sm) + 1;
}

export function isPositive(value) {
  return Number(value) > 0;
}
