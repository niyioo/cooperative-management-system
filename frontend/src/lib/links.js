const PORTAL_PATH = /^\/member(\/[A-Za-z0-9_-]+)*\/?$/;

/**
 * True for a plain member-portal path such as "/member/loans/123". Links that
 * arrive from the API (notifications) are only rendered when this holds, so a
 * value like "//host" or "/member/..\\host" can never become an off-site link.
 * The API validates the same pattern.
 */
export function isPortalLink(link) {
  return typeof link === 'string' && PORTAL_PATH.test(link);
}
