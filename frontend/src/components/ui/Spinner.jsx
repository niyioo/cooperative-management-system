import { Loader2 } from 'lucide-react';

export function Spinner({ label = 'Loading…' }) {
  return (
    <span className="inline-flex items-center gap-2 text-sm text-slate-500" role="status">
      <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
      {label}
    </span>
  );
}

export function LoadingBlock({ label }) {
  return (
    <div className="flex min-h-[160px] items-center justify-center">
      <Spinner label={label} />
    </div>
  );
}

export function FullPageSpinner() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-50">
      <Spinner />
    </div>
  );
}
