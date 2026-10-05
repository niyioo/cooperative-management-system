import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { LogIn } from 'lucide-react';
import Button from '../../components/ui/Button';
import { ErrorAlert } from '../../components/ui/Alert';
import { TextField } from '../../components/ui/Field';
import { homePath, useAuth } from '../../auth/AuthProvider';

export default function Login() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [error, setError] = useState(null);
  const { register, handleSubmit, formState } = useForm();

  const onSubmit = async ({ identifier, password }) => {
    setError(null);
    try {
      const user = await login(identifier.trim(), password);
      const from = location.state?.from?.pathname;
      navigate(from && !user.must_change_password ? from : homePath(user), { replace: true });
    } catch (err) {
      setError(err);
    }
  };

  return (
    <>
      <h1 className="text-xl font-bold text-slate-900">Sign in</h1>
      <p className="mt-1 text-sm text-slate-500">Use your email address or membership number.</p>
      <form className="mt-6 space-y-4" onSubmit={handleSubmit(onSubmit)} noValidate>
        <ErrorAlert error={error} />
        <TextField
          label="Email or membership number"
          autoComplete="username"
          autoFocus
          required
          error={formState.errors.identifier?.message}
          {...register('identifier', { required: 'Enter your email address or membership number.' })}
        />
        <TextField
          label="Password"
          type="password"
          autoComplete="current-password"
          required
          error={formState.errors.password?.message}
          {...register('password', { required: 'Enter your password.' })}
        />
        <Button type="submit" className="w-full" size="lg" icon={LogIn} loading={formState.isSubmitting}>
          Sign in
        </Button>
      </form>
      <p className="mt-5 text-center text-sm">
        <Link to="/forgot-password" className="font-medium text-brand-600 hover:underline">
          Forgot your password?
        </Link>
      </p>
    </>
  );
}
