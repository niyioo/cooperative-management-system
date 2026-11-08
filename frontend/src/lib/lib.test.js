import { describe, expect, it } from 'vitest';
import { label, MEMBER_STATUS } from './choices';
import { apiError, applyFieldErrors, errorMessage } from './errors';
import { formatAmount, formatNaira, formatPeriod, monthLabel, monthsInclusive } from './format';
import { isPortalLink } from './links';

describe('format', () => {
  it('formats money strings without float drift', () => {
    expect(formatNaira('1234567.89')).toMatch(/1,234,567\.89$/);
    expect(formatNaira('1234567.89')).toContain('₦');
    expect(formatAmount('0.1')).toBe('0.10');
    expect(formatNaira(null)).toBe('—');
    expect(formatNaira('')).toBe('—');
  });

  it('formats months and periods', () => {
    expect(monthLabel('2026-03')).toBe('Mar');
    expect(monthLabel('2026-03', true)).toBe('March 2026');
    expect(formatPeriod('2026-10-01')).toBe('Oct 2026');
    expect(formatPeriod('2026-10')).toBe('Oct 2026');
    expect(formatPeriod(null)).toBe('—');
  });

  it('counts whole months inclusively (Christmas Savings runs Jan–Oct)', () => {
    expect(monthsInclusive('2026-01-01', '2026-10-31')).toBe(10);
    expect(monthsInclusive('2025-11-01', '2026-02-28')).toBe(4);
  });
});

describe('errors', () => {
  const envelope = { response: { status: 400, data: { error: { code: 'validation_error', message: 'Check the form.', fields: { amount: ['Too large.'], non_field_errors: ['x'] } } } } };

  it('reads the API error envelope', () => {
    expect(apiError(envelope).code).toBe('validation_error');
    expect(errorMessage(envelope)).toBe('Check the form.');
  });

  it('explains network failures and unexpected responses', () => {
    expect(apiError(new Error('offline')).code).toBe('network_error');
    expect(apiError({ response: { status: 502, data: '<html>' } }).message).toMatch(/Something went wrong/);
  });

  it('copies field errors onto a form, skipping non-field errors', () => {
    const set = [];
    expect(applyFieldErrors(envelope, (field, error) => set.push([field, error.message]))).toBe(true);
    expect(set).toEqual([['amount', 'Too large.']]);
  });
});

describe('links', () => {
  it.each(['/member', '/member/', '/member/loans', '/member/loans/3f2a-9c', '/member/loans/apply'])('accepts %s', (link) => {
    expect(isPortalLink(link)).toBe(true);
  });

  it.each(['https://evil.example', '//evil.example', '/member/..\\evil.example', '/member/x?next=//evil', '/admin/settings', '', null, undefined, 42])(
    'rejects %s',
    (link) => {
      expect(isPortalLink(link)).toBe(false);
    },
  );
});

describe('choices', () => {
  it('maps values to labels and falls back to the value', () => {
    expect(label(MEMBER_STATUS, 'SUSPENDED')).toBe('Suspended');
    expect(label(MEMBER_STATUS, 'UNKNOWN')).toBe('UNKNOWN');
  });
});
