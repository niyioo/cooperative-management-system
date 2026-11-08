/**
 * The API returns {"error": {"code", "message", "fields"}} for every failure.
 * These helpers turn that (or a network failure) into something to show people.
 */
export function apiError(error) {
  const payload = error?.response?.data?.error;
  if (payload) return payload;
  if (error?.response) return { code: 'error', message: 'Something went wrong. Please try again.', fields: {} };
  return { code: 'network_error', message: 'Cannot reach the server. Check your connection and try again.', fields: {} };
}

export function errorMessage(error) {
  return apiError(error).message;
}

/** Copy field errors from the API onto a react-hook-form form. Returns true if any were applied. */
export function applyFieldErrors(error, setError) {
  const { fields } = apiError(error);
  let applied = false;
  Object.entries(fields || {}).forEach(([field, messages]) => {
    if (field === 'non_field_errors') return;
    const message = Array.isArray(messages) ? messages[0] : String(messages);
    setError(field, { type: 'server', message });
    applied = true;
  });
  return applied;
}
