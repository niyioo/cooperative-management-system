import { AlertTriangle, CheckCircle2, Info, XCircle } from 'lucide-react';
import { errorMessage } from '../../lib/errors';

const STYLES = {
  error: ['border-red-200 bg-red-50 text-red-800', XCircle],
  warning: ['border-amber-200 bg-amber-50 text-amber-900', AlertTriangle],
  success: ['border-emerald-200 bg-emerald-50 text-emerald-800', CheckCircle2],
  info: ['border-brand-100 bg-brand-50 text-brand-800', Info],
};

export function Alert({ tone = 'info', title, children, className = '' }) {
  const [style, Icon] = STYLES[tone];
  return (
    <div className={`flex gap-3 rounded-lg border px-4 py-3 text-sm ${style} ${className}`} role={tone === 'error' ? 'alert' : 'status'}>
      <Icon className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
      <div>
        {title && <p className="font-semibold">{title}</p>}
        {children && <div className={title ? 'mt-0.5' : ''}>{children}</div>}
      </div>
    </div>
  );
}

export function ErrorAlert({ error, className }) {
  if (!error) return null;
  return (
    <Alert tone="error" className={className}>
      {errorMessage(error)}
    </Alert>
  );
}
