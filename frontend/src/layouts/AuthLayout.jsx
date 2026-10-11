import { Outlet } from 'react-router-dom';
import BrandLogo from '../components/brand/BrandLogo';

export default function AuthLayout() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-slate-50 px-4 py-10">
      <BrandLogo size={112} />
      <main className="mt-8 w-full max-w-md rounded-xl border border-slate-200 bg-white p-6 shadow-lg sm:p-8">
        <Outlet />
      </main>
      <p className="mt-6 text-center text-xs text-slate-400">© {new Date().getFullYear()} EMDI Cooperative Society · Akure</p>
    </div>
  );
}
