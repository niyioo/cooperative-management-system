import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { useNavigate } from 'react-router-dom';
import { authApi } from '../../api/client';
import Button from '../../components/ui/Button';
import { Alert, ErrorAlert } from '../../components/ui/Alert';
import { TextField } from '../../components/ui/Field';
import { homePath, useAuth } from '../../auth/AuthProvider';
import { applyFieldErrors } from '../../lib/errors';

export default function ChangePassword() {
  const { user, replaceSession, logout } = useAuth();
  const navigate = useNavigate();
  const [error, setError] = useState(null);
  const { register, handleSubmit, formState, setError: setFieldError, getValues } = useForm();
  const forced = user.must_change_password;

  const onSubmit = async ({ current_password: current, new_password: next }) => {
    setError(null);
    try {
      // The server revokes every old session and returns a fresh one.
      const updated = replaceSession(await authApi.changePassword({ current_password: current, new_password: next }));
      navigate(homePath(updated), { replace: true });
    } catch (err) {
      if (!applyFieldErrors(err, setFieldError)) setError(err);
    }
  };

  return (
    <>
      <h1 className="text-xl font-bold text-slate-900">Change your password</h1>
      {forced && (
        <Alert tone="warning" className="mt-4">
          You signed in with a temporary password. Choose your own password to continue.
        </Alert>
      )}
      <form className="mt-5 space-y-4" onSubmit={handleSubmit(onSubmit)} noValidate>
        <ErrorAlert error={error} />
        <TextField label={forced ? 'Temporary password' : 'Current password'} type="password" autoComplete="current-password" required
          error={formState.errors.current_password?.message} {...register('current_password', { required: 'Enter your current password.' })} />
        <TextField label="New password" type="password" autoComplete="new-password" required hint="At least 10 characters; avoid common words."
          error={formState.errors.new_password?.message}
          {...register('new_password', { required: 'Choose a new password.', minLength: { value: 10, message: 'Use at least 10 characters.' } })} />
        <TextField label="Confirm new password" type="password" autoComplete="new-password" required error={formState.errors.confirm?.message}
          {...register('confirm', { validate: (v) => v === getValues('new_password') || 'The passwords do not match.' })} />
        <Button type="submit" className="w-full" loading={formState.isSubmitting}>
          Change password
        </Button>
        <div className="flex justify-between text-sm">
          {!forced ? (
            <button type="button" className="font-medium text-brand-600 hover:underline" onClick={() => navigate(-1)}>
              Cancel
            </button>
          ) : <span />}
          <button type="button" className="font-medium text-slate-500 hover:underline" onClick={logout}>
            Sign out
          </button>
        </div>
      </form>
    </>
  );
}
