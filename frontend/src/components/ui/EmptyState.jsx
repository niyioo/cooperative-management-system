import { Inbox } from 'lucide-react';

export default function EmptyState({ title, children, icon: Icon = Inbox, action }) {
  return (
    <div className="flex flex-col items-center justify-center px-6 py-10 text-center">
      <span className="rounded-full bg-slate-100 p-3 text-slate-400">
        <Icon className="h-6 w-6" aria-hidden="true" />
      </span>
      <p className="mt-3 font-semibold text-slate-800">{title}</p>
      {children && <p className="mt-1 max-w-sm text-sm text-slate-500">{children}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}
