import { useState } from 'react';
import { Search, UserCheck } from 'lucide-react';
import { memberApi } from '../../api/member';
import { apiError } from '../../lib/errors';
import Button from '../ui/Button';

/**
 * Find a fellow member by membership number, confirm the name, then add them.
 * onAdd({ membership_number, full_name }) may return a promise; errors it throws are shown here.
 */
export default function GuarantorFinder({ onAdd, exclude = [], disabled }) {
  const [number, setNumber] = useState('');
  const [found, setFound] = useState(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  const find = async (event) => {
    event?.preventDefault();
    if (!number.trim()) return;
    setBusy(true);
    setError('');
    setFound(null);
    try {
      const member = await memberApi.lookupGuarantor(number.trim());
      if (exclude.some((n) => n.toLowerCase() === member.membership_number.toLowerCase())) {
        setError(`${member.full_name} is already one of your guarantors.`);
      } else {
        setFound(member);
      }
    } catch (err) {
      const { fields, message } = apiError(err);
      setError(fields?.membership_number?.[0] || message);
    } finally {
      setBusy(false);
    }
  };

  const add = async () => {
    setBusy(true);
    setError('');
    try {
      await onAdd(found);
      setFound(null);
      setNumber('');
    } catch (err) {
      const { fields, message } = apiError(err);
      setError(fields?.membership_number?.[0] || message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-2">
      <form className="flex flex-wrap items-end gap-2" onSubmit={find}>
        <label className="min-w-[14rem] flex-1 text-sm font-medium text-slate-700">
          Guarantor's membership number
          <input
            value={number}
            onChange={(e) => { setNumber(e.target.value); setFound(null); setError(''); }}
            placeholder="e.g. EMDI/COOP/0002"
            autoComplete="off"
            disabled={disabled}
            className="mt-1 block w-full rounded-lg border border-slate-300 px-3 py-2 text-sm uppercase placeholder:normal-case"
          />
        </label>
        <Button type="submit" variant="secondary" icon={Search} loading={busy && !found} disabled={disabled || !number.trim()}>Find</Button>
      </form>
      {error && <p className="text-sm font-medium text-red-600" role="alert">{error}</p>}
      {found && (
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3">
          <p className="text-sm text-emerald-900">
            <UserCheck className="mr-1 inline h-4 w-4" aria-hidden="true" />
            <span className="font-semibold">{found.full_name}</span> · {found.membership_number}
          </p>
          <Button size="sm" loading={busy} onClick={add}>Add as guarantor</Button>
        </div>
      )}
    </div>
  );
}
