import { useQuery } from '@tanstack/react-query';
import { adminApi, allPages } from '../../api/admin';

/** Small reference lists for drop-downs, cached for a few minutes. */
const SOURCES = {
  savingsProducts: adminApi.savingsProducts.list,
  savingsCycles: adminApi.savingsCycles.list,
  loanProducts: adminApi.loanProducts.list,
  investmentProducts: adminApi.investmentProducts.list,
  departments: adminApi.departments.list,
  roles: adminApi.roles.list,
};

export default function useReference(name, params = {}, enabled = true) {
  return useQuery({
    queryKey: ['admin', 'ref', name, params],
    queryFn: () => allPages(SOURCES[name], params),
    staleTime: 5 * 60_000,
    enabled,
  });
}
