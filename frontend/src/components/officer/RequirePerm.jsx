import { Outlet } from 'react-router-dom';
import { ShieldOff } from 'lucide-react';
import { useCan } from '../../lib/permissions';
import { Card } from '../ui/Card';
import EmptyState from '../ui/EmptyState';

/** Route guard: renders the child routes only for officers holding any of `perm`. The API enforces the same rules. */
export default function RequirePerm({ perm }) {
  const can = useCan();
  if (can(perm)) return <Outlet />;
  return (
    <Card>
      <EmptyState icon={ShieldOff} title="You don't have access to this page">
        Your role does not include this area. Ask the Super Admin if you need access.
      </EmptyState>
    </Card>
  );
}
