import { ErrorAlert } from './Alert';
import { LoadingBlock } from './Spinner';

/** Show loading and error states for a React Query result, then render children(data). */
export default function QueryState({ query, children, loadingLabel }) {
  if (query.isPending) return <LoadingBlock label={loadingLabel} />;
  if (query.isError) return <ErrorAlert error={query.error} />;
  return children(query.data);
}
