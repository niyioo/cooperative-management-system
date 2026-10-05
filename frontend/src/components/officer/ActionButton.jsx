import { useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { ErrorAlert } from '../ui/Alert';
import Button from '../ui/Button';
import { TextAreaField } from '../ui/Field';
import Modal from '../ui/Modal';

/**
 * A button that confirms in a dialog, optionally asks for a reason/notes, then
 * runs `action(text)`. On success it refreshes cached data and calls onDone.
 *
 *   input: undefined (no text) | "optional" | "required"
 */
export default function ActionButton({
  label,
  title,
  description,
  action,
  onDone,
  input,
  inputLabel = 'Reason',
  confirmLabel,
  variant = 'primary',
  confirmVariant,
  icon,
  size = 'md',
  disabled,
  invalidate = [['admin']],
}) {
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [text, setText] = useState('');
  const mutation = useMutation({
    mutationFn: () => action(text.trim()),
    onSuccess: (data) => {
      invalidate.forEach((queryKey) => queryClient.invalidateQueries({ queryKey }));
      setOpen(false);
      setText('');
      onDone?.(data);
    },
  });
  const blocked = input === 'required' && !text.trim();

  return (
    <>
      <Button variant={variant} icon={icon} size={size} disabled={disabled} onClick={() => { mutation.reset(); setOpen(true); }}>
        {label}
      </Button>
      <Modal
        open={open}
        onClose={() => setOpen(false)}
        title={title || label}
        footer={
          <>
            <Button variant="secondary" onClick={() => setOpen(false)}>Cancel</Button>
            <Button variant={confirmVariant || variant} loading={mutation.isPending} disabled={blocked} onClick={() => mutation.mutate()}>
              {confirmLabel || label}
            </Button>
          </>
        }
      >
        <div className="space-y-3">
          {description && <div>{description}</div>}
          {input && (
            <TextAreaField label={`${inputLabel}${input === 'optional' ? ' (optional)' : ''}`} rows={3} value={text}
              onChange={(e) => setText(e.target.value)} required={input === 'required'} />
          )}
          <ErrorAlert error={mutation.error} />
          {mutation.error?.response?.data?.error?.fields?.lines && (
            <ul className="list-disc space-y-1 pl-5 text-xs text-red-700">
              {mutation.error.response.data.error.fields.lines.map((line) => (
                <li key={line.reference}>{line.member}: {line.errors.join(' ')}</li>
              ))}
            </ul>
          )}
        </div>
      </Modal>
    </>
  );
}
