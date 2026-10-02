import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { ErrorAlert } from '../ui/Alert';
import Button from '../ui/Button';
import Modal from '../ui/Modal';
import { applyFieldErrors } from '../../lib/errors';

/**
 * A button that opens a react-hook-form in a dialog and submits it.
 *   renderFields({ register, errors, watch }) -> fields
 */
export default function FormModal({ trigger, title, submitLabel = 'Save', defaultValues, onSubmit, renderFields, onDone, transform = (v) => v, invalidate = [['admin']], triggerVariant = 'primary', triggerIcon, triggerSize = 'md' }) {
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const formApi = useForm({ defaultValues });
  const { handleSubmit, setError, reset, formState } = formApi;
  const mutation = useMutation({
    mutationFn: (values) => onSubmit(transform(values)),
    onSuccess: (data) => {
      invalidate.forEach((queryKey) => queryClient.invalidateQueries({ queryKey }));
      setOpen(false);
      reset(defaultValues);
      onDone?.(data);
    },
    onError: (error) => applyFieldErrors(error, setError),
  });

  return (
    <>
      <Button variant={triggerVariant} icon={triggerIcon} size={triggerSize} onClick={() => { mutation.reset(); reset(defaultValues); setOpen(true); }}>
        {trigger}
      </Button>
      <Modal
        open={open}
        onClose={() => setOpen(false)}
        title={title || trigger}
        footer={
          <>
            <Button variant="secondary" onClick={() => setOpen(false)}>Cancel</Button>
            <Button loading={mutation.isPending} onClick={handleSubmit((values) => mutation.mutate(values))}>{submitLabel}</Button>
          </>
        }
      >
        <form className="space-y-4" onSubmit={handleSubmit((values) => mutation.mutate(values))} noValidate>
          <ErrorAlert error={mutation.error} />
          {renderFields({ register: formApi.register, errors: formState.errors, watch: formApi.watch, setValue: formApi.setValue })}
          <button type="submit" className="hidden" aria-hidden="true" tabIndex={-1} />
        </form>
      </Modal>
    </>
  );
}
