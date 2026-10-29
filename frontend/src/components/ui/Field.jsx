import { forwardRef, useId } from 'react';

const CONTROL = 'block w-full rounded-lg border bg-white px-3 py-2 text-sm text-slate-900 shadow-sm placeholder:text-slate-400 disabled:bg-slate-50';
const tone = (error) => (error ? 'border-red-400 focus:border-red-500' : 'border-slate-300 focus:border-brand-500');

function Wrapper({ id, label, hint, error, required, children }) {
  return (
    <div>
      {label && (
        <label htmlFor={id} className="mb-1 block text-sm font-medium text-slate-700">
          {label}
          {required && (
            <span className="text-red-600" aria-hidden="true">
              {' '}*
            </span>
          )}
        </label>
      )}
      {children}
      {hint && !error && (
        <p id={`${id}-hint`} className="mt-1 text-xs text-slate-500">
          {hint}
        </p>
      )}
      {error && (
        <p id={`${id}-error`} className="mt-1 text-xs font-medium text-red-600">
          {error}
        </p>
      )}
    </div>
  );
}

function describedBy(id, hint, error) {
  return [error && `${id}-error`, hint && !error && `${id}-hint`].filter(Boolean).join(' ') || undefined;
}

export const TextField = forwardRef(function TextField({ label, hint, error, required, className = '', ...props }, ref) {
  const id = useId();
  return (
    <Wrapper id={id} label={label} hint={hint} error={error} required={required}>
      <input ref={ref} id={id} className={`${CONTROL} ${tone(error)} ${className}`} aria-invalid={!!error} aria-describedby={describedBy(id, hint, error)} {...props} />
    </Wrapper>
  );
});

export const SelectField = forwardRef(function SelectField({ label, hint, error, required, children, ...props }, ref) {
  const id = useId();
  return (
    <Wrapper id={id} label={label} hint={hint} error={error} required={required}>
      <select ref={ref} id={id} className={`${CONTROL} ${tone(error)}`} aria-invalid={!!error} aria-describedby={describedBy(id, hint, error)} {...props}>
        {children}
      </select>
    </Wrapper>
  );
});

export const TextAreaField = forwardRef(function TextAreaField({ label, hint, error, required, rows = 4, ...props }, ref) {
  const id = useId();
  return (
    <Wrapper id={id} label={label} hint={hint} error={error} required={required}>
      <textarea ref={ref} id={id} rows={rows} className={`${CONTROL} ${tone(error)}`} aria-invalid={!!error} aria-describedby={describedBy(id, hint, error)} {...props} />
    </Wrapper>
  );
});

export const CheckboxField = forwardRef(function CheckboxField({ label, error, ...props }, ref) {
  const id = useId();
  return (
    <div>
      <label htmlFor={id} className="flex items-start gap-2 text-sm text-slate-700">
        <input ref={ref} id={id} type="checkbox" className="mt-0.5 h-4 w-4 rounded border-slate-300 text-brand-600" aria-invalid={!!error} {...props} />
        <span>{label}</span>
      </label>
      {error && <p className="mt-1 text-xs font-medium text-red-600">{error}</p>}
    </div>
  );
});
