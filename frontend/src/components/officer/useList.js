import { useState } from 'react';
import { keepPreviousData, useQuery } from '@tanstack/react-query';

/**
 * List state for officer tables: filters + page, and the query.
 *   const list = useList(['admin', 'members'], adminApi.members.list, { status: '' });
 *   list.setFilter('status', 'ACTIVE')
 */
export default function useList(key, fetcher, initialFilters = {}) {
  const [filters, setFilters] = useState(initialFilters);
  const [page, setPage] = useState(1);
  const params = Object.fromEntries(Object.entries({ ...filters, page }).filter(([, v]) => v !== '' && v !== undefined && v !== null));
  const query = useQuery({ queryKey: [...key, params], queryFn: () => fetcher(params), placeholderData: keepPreviousData });
  return {
    query,
    filters,
    page,
    setPage,
    setFilter: (name, value) => {
      setFilters((f) => ({ ...f, [name]: value }));
      setPage(1);
    },
  };
}
