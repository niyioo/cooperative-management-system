import { useEffect, useState } from 'react';
import { useForm } from 'react-hook-form';
import { Link, useSearchParams } from 'react-router-dom';
import { authApi } from '../../api/client';
import Button from '../../components/ui/Button';
import { Alert, ErrorAlert } from '../../components/ui/Alert';
import { TextField } from '../../components/ui/Field';
import { applyFieldErrors } from '../../lib/errors';

const MODES = {
  reset: { title: 'Choose a new password', action: authApi.confirmReset, done: 'Your password has been reset.' },
  activate: { title: 'Activate your account', action: authApi.activate, done: 'Your account is active.' },
};

/** Shared page for the emailed links: /reset-password and /activate (?uid=…&token=…). */
export default function SetPassword({ mode }) {
  const { title, action, done } = MODES[mode];
  const [params, setParams] = useSearchParams();
  const [finished, setFinished] = useState(false);
  const [error, setError] = useState(null);
  const { register, handleSubmit, formState, setError: setFieldError, getValues } = useForm();
  // Kept in state, then removed from the URL so the token isn't left in the
  // address bar, the browser history or a copied link.
  const [{ uid, token }] = useState(() => ({ uid: params.get('uid'), token: params.get('token') }));
  useEffect(() => {
    if (params.has('token') || params.has('uid')) setParams({}, { replace: true });
  }, [params, setParams]);

  const onSubmit = async ({ new_password: newPassword }) => {
    setError(null);
    try {
      await action({ uid, token, new_password: newPassword });
      setFinished(true);
    } catch (err) {
      if (!applyFieldErrors(err, setFieldError)) setError(err);
    }
  };

  if (!uid || !token) {
    return <Alert tone="error" title="This link is incomplete">Open the link from your email again, or request a new one.</Alert>;
  }

  return (
    <>
      <h1 className="text-xl font-bold text-slate-900">{title}</h1>
      {finished ? (
        <Alert tone="success" className="mt-5" title={done}>
          <Link to="/login" className="font-semibold underline">
            Sign in now
          </Link>
        </Alert>
      ) : (
        <form className="mt-5 space-y-4" onSubmit={handleSubmit(onSubmit)} noValidate>
          <ErrorAlert error={error} />
          <TextField label="New password" type="password" autoComplete="new-password" required hint="At least 10 characters; avoid common words."
            error={formState.errors.new_password?.message}
            {...register('new_password', { required: 'Choose a password.', minLength: { value: 10, message: 'Use at least 10 characters.' } })} />
          <TextField label="Confirm password" type="password" autoComplete="new-password" required error={formState.errors.confirm?.message}
            {...register('confirm', { validate: (v) => v === getValues('new_password') || 'The passwords do not match.' })} />
          <Button type="submit" className="w-full" loading={formState.isSubmitting}>
            Save password
          </Button>
        </form>
      )}
    </>
  );
}
