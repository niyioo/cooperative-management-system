import { Link } from 'react-router-dom';
import BrandLogo from '../components/brand/BrandLogo';

export default function NotFound() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-slate-50 px-4 text-center">
      <BrandLogo size={80} showName={false} />
      <h1 className="mt-6 text-2xl font-bold text-slate-900">Page not found</h1>
      <p className="mt-2 text-sm text-slate-600">The page you were looking for doesn't exist or has moved.</p>
      <Link to="/" className="mt-6 font-semibold text-brand-600 hover:underline">Go to the home page</Link>
    </div>
  );
}
