import { useEffect, useMemo, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Link, useNavigate } from 'react-router-dom';
import { ArrowLeft, ArrowRight, Check, CheckCircle2, Handshake, Paperclip, Trash2, XCircle } from 'lucide-react';
import { memberApi } from '../../api/member';
import GuarantorFinder from '../../components/member/GuarantorFinder';
import { Alert, ErrorAlert } from '../../components/ui/Alert';
import Button from '../../components/ui/Button';
import { Card, CardBody } from '../../components/ui/Card';
import EmptyState from '../../components/ui/EmptyState';
import { CheckboxField, SelectField, TextAreaField, TextField } from '../../components/ui/Field';
import PageHeader from '../../components/ui/PageHeader';
import QueryState from '../../components/ui/QueryState';
import { Spinner } from '../../components/ui/Spinner';
import { formatDate, formatNaira } from '../../lib/format';

const STEPS = ['Choose a loan', 'Amount and term', 'Purpose and documents', 'Guarantors', 'Review and submit'];
const RATE_BASIS = { PER_ANNUM: 'a year', PER_MONTH: 'a month', PER_LOAN: 'for the whole loan' };
// Checks that depend on the amount or term are judged on step 2, not when choosing a product.
const AMOUNT_CHECKS = ['amount_range', 'term', 'savings_security'];

function useDebounced(value, delay = 400) {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delay);
    return () => clearTimeout(timer);
  }, [value, delay]);
  return debounced;
}

function Checks({ checks }) {
  return (
    <ul className="space-y-1.5">
      {checks.map((c) => (
        <li key={c.code} className="flex items-start gap-2 text-sm">
          {c.passed ? (
            <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-emerald-600" aria-label="Met" />
          ) : (
            <XCircle className="mt-0.5 h-4 w-4 shrink-0 text-red-600" aria-label="Not met" />
          )}
          <span>
            <span className={c.passed ? 'text-slate-700' : 'font-medium text-red-700'}>{c.label}</span>
            {c.detail && <span className="block text-xs text-slate-500">{c.detail}</span>}
          </span>
        </li>
      ))}
    </ul>
  );
}

export default function ApplyForLoan() {
  const products = useQuery({ queryKey: ['me', 'loan-products'], queryFn: memberApi.loanProducts });
  const [step, setStep] = useState(0);
  const [form, setForm] = useState({ productId: null, amount: '', term: '', purpose: '', files: [], guarantors: [], confirmed: false });
  const update = (patch) => setForm((f) => ({ ...f, ...patch }));

  return (
    <div className="space-y-6">
      <PageHeader title="Apply for a loan" description="Your application goes to the loan committee for review." />
      <ol className="grid grid-cols-2 gap-2 sm:grid-cols-5" aria-label="Application steps">
        {STEPS.map((label, i) => (
          <li key={label} className={`rounded-lg border px-3 py-2 text-xs font-semibold ${i === step ? 'border-brand-600 bg-brand-50 text-brand-800' : i < step ? 'border-emerald-200 bg-emerald-50 text-emerald-800' : 'border-slate-200 bg-white text-slate-500'}`}
            aria-current={i === step ? 'step' : undefined}>
            <span className="mr-1">{i < step ? <Check className="inline h-3.5 w-3.5" aria-hidden="true" /> : `${i + 1}.`}</span>
            {label}
          </li>
        ))}
      </ol>
      <QueryState query={products}>
        {(list) => {
          if (!list.length) return <Card><EmptyState title="No loan products are open">Please check back later or contact the cooperative office.</EmptyState></Card>;
          const product = list.find((p) => p.id === form.productId);
          return (
            <>
              {step === 0 && <ChooseProduct products={list} selected={form.productId} onSelect={(id) => update({ productId: id, amount: '', term: '' })} onNext={() => setStep(1)} />}
              {step === 1 && product && <AmountAndTerm product={product} form={form} update={update} onBack={() => setStep(0)} onNext={() => setStep(2)} />}
              {step === 2 && product && <PurposeAndDocuments product={product} form={form} update={update} onBack={() => setStep(1)} onNext={() => setStep(3)} />}
              {step === 3 && product && <Guarantors product={product} form={form} update={update} onBack={() => setStep(2)} onNext={() => setStep(4)} />}
              {step === 4 && product && <Review product={product} form={form} update={update} onBack={() => setStep(3)} />}
            </>
          );
        }}
      </QueryState>
    </div>
  );
}

function ChooseProduct({ products, selected, onSelect, onNext }) {
  return (
    <div className="space-y-4">
      <div className="grid gap-4 md:grid-cols-2">
        {products.map((p) => {
          const general = p.eligibility.checks.filter((c) => !AMOUNT_CHECKS.includes(c.code));
          const eligible = general.every((c) => c.passed || !c.hard);
          const active = selected === p.id;
          return (
            <Card key={p.id} className={active ? 'ring-2 ring-brand-600' : ''}>
              <CardBody className="space-y-3">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <h2 className="font-semibold text-slate-900">{p.name}</h2>
                    <p className="text-sm text-slate-500">{p.description}</p>
                  </div>
                  <span className="whitespace-nowrap rounded-lg bg-brand-50 px-2 py-1 text-sm font-bold text-brand-700">
                    {Number(p.interest_rate)}% <span className="font-normal">{RATE_BASIS[p.interest_rate_basis]}</span>
                  </span>
                </div>
                <dl className="grid grid-cols-2 gap-2 text-sm">
                  <div><dt className="text-xs text-slate-500">You can borrow up to</dt><dd className="font-semibold">{formatNaira(p.eligibility.max_amount)}</dd></div>
                  <div><dt className="text-xs text-slate-500">Repayment period</dt><dd className="font-semibold">{p.allowed_terms.length ? `${p.allowed_terms.join(', ')} months` : `${p.min_term_months}–${p.max_term_months} months`}</dd></div>
                  <div><dt className="text-xs text-slate-500">Interest</dt><dd>{p.interest_collection === 'UPFRONT' ? 'Deducted when paid out' : 'Repaid monthly'}</dd></div>
                  <div><dt className="text-xs text-slate-500">Product limit</dt><dd>{formatNaira(p.min_amount)} – {formatNaira(p.max_amount)}</dd></div>
                </dl>
                <details className="text-sm">
                  <summary className="cursor-pointer font-medium text-brand-600">Your eligibility</summary>
                  <div className="mt-2"><Checks checks={general} /></div>
                </details>
                <Button variant={active ? 'primary' : 'secondary'} className="w-full" disabled={!eligible} onClick={() => onSelect(p.id)}>
                  {eligible ? (active ? 'Selected' : 'Choose this loan') : 'Not eligible at the moment'}
                </Button>
              </CardBody>
            </Card>
          );
        })}
      </div>
      <div className="flex justify-end">
        <Button icon={ArrowRight} disabled={!selected} onClick={onNext}>Continue</Button>
      </div>
    </div>
  );
}

function AmountAndTerm({ product, form, update, onBack, onNext }) {
  const amount = useDebounced(form.amount);
  const term = useDebounced(form.term);
  const ready = Number(amount) > 0 && Number(term) > 0;
  const quote = useQuery({
    queryKey: ['me', 'quote', product.id, amount, term],
    queryFn: () => memberApi.loanQuote(product.id, amount, term),
    enabled: ready,
    retry: false,
  });
  const eligible = quote.data?.eligibility?.eligible;

  return (
    <div className="grid gap-6 lg:grid-cols-5">
      <Card className="lg:col-span-2">
        <CardBody className="space-y-4">
          <TextField label="Amount (₦)" type="number" inputMode="decimal" min={product.min_amount} max={product.eligibility.max_amount} step="1000"
            value={form.amount} onChange={(e) => update({ amount: e.target.value })} required
            hint={`Between ${formatNaira(product.min_amount)} and ${formatNaira(product.eligibility.max_amount)} for you.`} />
          {product.allowed_terms.length ? (
            <SelectField label="Repayment period" value={form.term} onChange={(e) => update({ term: e.target.value })} required>
              <option value="">Choose…</option>
              {product.allowed_terms.map((t) => <option key={t} value={t}>{t} months</option>)}
            </SelectField>
          ) : (
            <TextField label="Repayment period (months)" type="number" min={product.min_term_months} max={product.max_term_months}
              value={form.term} onChange={(e) => update({ term: e.target.value })} required hint={`${product.min_term_months} to ${product.max_term_months} months.`} />
          )}
        </CardBody>
      </Card>
      <Card className="lg:col-span-3">
        <CardBody>
          {!ready && <p className="text-sm text-slate-500">Enter an amount and repayment period to see what the loan will cost.</p>}
          {ready && quote.isFetching && <Spinner label="Working out your repayments…" />}
          {ready && quote.isError && <ErrorAlert error={quote.error} />}
          {ready && quote.data && !quote.isFetching && (
            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-4 sm:grid-cols-3">
                <div><p className="text-xs text-slate-500">Monthly repayment</p><p className="tabular text-xl font-bold text-brand-800">{formatNaira(quote.data.monthly_payment)}</p></div>
                <div><p className="text-xs text-slate-500">Total interest</p><p className="tabular text-lg font-semibold">{formatNaira(quote.data.total_interest)}</p></div>
                <div><p className="text-xs text-slate-500">Total to repay</p><p className="tabular text-lg font-semibold">{formatNaira(quote.data.total_payable)}</p></div>
              </div>
              <p className="text-sm text-slate-600">
                First repayment {formatDate(quote.data.first_due_date)}, last {formatDate(quote.data.maturity_date)}.
                {quote.data.interest_deducted_upfront && ' The interest is deducted from the amount paid to you.'}
              </p>
              <Checks checks={quote.data.eligibility.checks.filter((c) => AMOUNT_CHECKS.includes(c.code))} />
            </div>
          )}
        </CardBody>
      </Card>
      <div className="flex justify-between lg:col-span-5">
        <Button variant="secondary" icon={ArrowLeft} onClick={onBack}>Back</Button>
        <Button icon={ArrowRight} disabled={!ready || !eligible || quote.isFetching} onClick={onNext}>Continue</Button>
      </div>
    </div>
  );
}

function PurposeAndDocuments({ product, form, update, onBack, onNext }) {
  const addFiles = (event) => {
    const picked = Array.from(event.target.files || []).map((file) => ({ file, title: file.name.replace(/\.[^.]+$/, '') }));
    update({ files: [...form.files, ...picked] });
    event.target.value = '';
  };
  return (
    <Card>
      <CardBody className="space-y-5">
        <TextAreaField label="What is the loan for?" required value={form.purpose} onChange={(e) => update({ purpose: e.target.value })}
          hint="A short explanation helps the committee, e.g. “School fees for two children”." maxLength={2000} />
        <div>
          <p className="text-sm font-medium text-slate-700">Supporting documents</p>
          {product.required_documents.length > 0 && (
            <p className="mt-1 text-sm text-slate-500">This loan needs: {product.required_documents.join(', ')}.</p>
          )}
          <label className="mt-2 inline-flex cursor-pointer items-center gap-2 rounded-lg border border-dashed border-slate-300 px-4 py-2 text-sm font-medium text-brand-700 hover:bg-brand-50">
            <Paperclip className="h-4 w-4" aria-hidden="true" /> Add PDF, JPG or PNG (max 5 MB)
            <input type="file" className="sr-only" accept=".pdf,.jpg,.jpeg,.png" multiple onChange={addFiles} />
          </label>
          {form.files.length > 0 && (
            <ul className="mt-3 space-y-2">
              {form.files.map((item, i) => (
                <li key={`${item.file.name}-${i}`} className="flex items-center gap-2">
                  <input aria-label="Document title" className="flex-1 rounded-lg border border-slate-300 px-3 py-1.5 text-sm" value={item.title}
                    onChange={(e) => update({ files: form.files.map((f, j) => (j === i ? { ...f, title: e.target.value } : f)) })} />
                  <Button variant="ghost" size="sm" onClick={() => update({ files: form.files.filter((_, j) => j !== i) })}>Remove</Button>
                </li>
              ))}
            </ul>
          )}
        </div>
        <div className="flex justify-between">
          <Button variant="secondary" icon={ArrowLeft} onClick={onBack}>Back</Button>
          <Button icon={ArrowRight} disabled={form.purpose.trim().length < 3} onClick={onNext}>Continue</Button>
        </div>
      </CardBody>
    </Card>
  );
}

function Guarantors({ product, form, update, onBack, onNext }) {
  const needed = product.guarantors_required;
  const enough = form.guarantors.length >= needed;
  return (
    <Card>
      <CardBody className="space-y-5">
        <div className="flex gap-3">
          <span className="rounded-lg bg-brand-50 p-2 text-brand-600"><Handshake className="h-5 w-5" aria-hidden="true" /></span>
          <div>
            <p className="font-semibold text-slate-900">This loan needs {needed} guarantor{needed > 1 ? 's' : ''}</p>
            <p className="text-sm text-slate-500">
              A guarantor is a fellow member who agrees to stand behind your loan. Enter their membership number. When you submit,
              they are asked by e-mail and in the portal to accept or decline, and the committee can only approve once they accept.
            </p>
          </div>
        </div>
        {form.guarantors.length > 0 && (
          <ul className="divide-y divide-slate-100 rounded-lg border border-slate-200">
            {form.guarantors.map((g) => (
              <li key={g.membership_number} className="flex items-center justify-between gap-3 px-4 py-3 text-sm">
                <span><span className="font-semibold text-slate-900">{g.full_name}</span> <span className="text-slate-500">{g.membership_number}</span></span>
                <Button variant="ghost" size="sm" icon={Trash2} onClick={() => update({ guarantors: form.guarantors.filter((x) => x.membership_number !== g.membership_number) })}>Remove</Button>
              </li>
            ))}
          </ul>
        )}
        <GuarantorFinder exclude={form.guarantors.map((g) => g.membership_number)} disabled={form.guarantors.length >= 5}
          onAdd={(member) => update({ guarantors: [...form.guarantors, member] })} />
        <div className="flex justify-between">
          <Button variant="secondary" icon={ArrowLeft} onClick={onBack}>Back</Button>
          <Button icon={ArrowRight} disabled={!enough} onClick={onNext}>Continue</Button>
        </div>
      </CardBody>
    </Card>
  );
}

function Review({ product, form, update, onBack }) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [error, setError] = useState(null);
  const [draftId, setDraftId] = useState(null);
  const [busy, setBusy] = useState(false);
  const summary = useMemo(() => [
    ['Loan', product.name],
    ['Amount', formatNaira(form.amount)],
    ['Repayment period', `${form.term} months`],
    ['Purpose', form.purpose],
    ['Documents', form.files.length ? form.files.map((f) => f.title).join(', ') : 'None'],
    ['Guarantors', form.guarantors.map((g) => `${g.full_name} (${g.membership_number})`).join(', ')],
  ], [product, form]);

  const submit = async () => {
    setBusy(true);
    setError(null);
    try {
      let id = draftId;
      if (!id) {
        const draft = await memberApi.createApplication({ product: product.id, amount_requested: form.amount, term_months: Number(form.term), purpose: form.purpose.trim() });
        id = draft.id;
        setDraftId(id);
        for (const guarantor of form.guarantors) {
          await memberApi.addGuarantor(id, guarantor.membership_number);
        }
        for (const item of form.files) {
          await memberApi.uploadApplicationDocument(id, item.title || item.file.name, item.file);
        }
      }
      await memberApi.submitApplication(id);
      queryClient.invalidateQueries({ queryKey: ['me'] });
      navigate(`/member/loans/applications/${id}`, { replace: true, state: { justSubmitted: true } });
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card>
      <CardBody className="space-y-5">
        <dl className="divide-y divide-slate-100 rounded-lg border border-slate-200">
          {summary.map(([label, value]) => (
            <div key={label} className="grid gap-1 px-4 py-3 sm:grid-cols-3">
              <dt className="text-sm text-slate-500">{label}</dt>
              <dd className="text-sm font-medium text-slate-800 sm:col-span-2">{value}</dd>
            </div>
          ))}
        </dl>
        <CheckboxField label="I confirm the information is correct and I agree to repayments being deducted from my salary." checked={form.confirmed}
          onChange={(e) => update({ confirmed: e.target.checked })} />
        <ErrorAlert error={error} />
        {draftId && error && (
          <Alert tone="info">Your application was saved as a draft. <Link to={`/member/loans/applications/${draftId}`} className="font-semibold underline">Open the draft</Link> to fix it later.</Alert>
        )}
        <div className="flex justify-between">
          <Button variant="secondary" icon={ArrowLeft} onClick={onBack} disabled={busy || !!draftId}>Back</Button>
          <Button icon={Check} loading={busy} disabled={!form.confirmed} onClick={submit}>Submit application</Button>
        </div>
      </CardBody>
    </Card>
  );
}
