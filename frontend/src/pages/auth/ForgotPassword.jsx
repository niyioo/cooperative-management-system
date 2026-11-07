import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { Link } from 'react-router-dom';
import { authApi } from '../../api/client';
import Button from '../../components/ui/Button';
import { Alert, ErrorAlert } from '../../components/ui/Alert';
import { TextField } from '../../components/ui/Field';

export default function ForgotPassword() {
  const [sent, setSent] = useState(false);
  const [error, setError] = useState(null);
  const { register, handleSubmit, formState } = useForm();

  const onSubmit = async ({ email }) => {
    setError(null);
    try {
      await authApi.requestReset(email.trim());
      setSent(true);
    } catch (err) {
      setError(err);
    }
  };

  return (
    <>
      <h1 className="text-xl font-bold text-slate-900">Reset your password</h1>
      {sent ? (
        <Alert tone="success" className="mt-5" title="Check your email">
          If an account exists for that address, we have sent a link to reset your password. It expires in one hour.
        </Alert>
      ) : (
        <form className="mt-5 space-y-4" onSubmit={handleSubmit(onSubmit)} noValidate>
          <p className="text-sm text-slate-500">Enter the email address on your cooperative record.</p>
          <ErrorAlert error={error} />
          <TextField label="Email address" type="email" autoComplete="email" required error={formState.errors.email?.message}
            {...register('email', { required: 'Enter your email address.' })} />
          <Button type="submit" className="w-full" loading={formState.isSubmitting}>
            Send reset link
          </Button>
          <p className="text-xs text-slate-500">No email on record? Ask the cooperative secretariat for a temporary password.</p>
        </form>
      )}
      <p className="mt-5 text-center text-sm">
        <Link to="/login" className="font-medium text-brand-600 hover:underline">
          Back to sign in
        </Link>
      </p>
    </>
  );
}
