import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { CheckCircle2 } from 'lucide-react';
import { publicApi } from '../../api/client';
import BrandLogo from '../../components/brand/BrandLogo';
import { ErrorAlert } from '../../components/ui/Alert';
import Button from '../../components/ui/Button';
import { Card, CardBody, CardHeader } from '../../components/ui/Card';
import { CheckboxField, SelectField, TextAreaField, TextField } from '../../components/ui/Field';
import { GENDERS, MARITAL, TITLES, options } from '../../lib/choices';
import { applyFieldErrors } from '../../lib/errors';

// The paper membership form, online (BR-39). Open to anyone; the Secretary recommends and the Chairman approves.
const EMPTY = {
  title: '', first_name: '', middle_name: '', last_name: '', former_name: '', gender: '', date_of_birth: '', marital_status: '',
  email: '', phone: '', alt_phone: '', residential_address: '', permanent_address: '', state_of_origin: '', lga: '',
  staff_number: '', department: '', designation: '', grade_level: '', employment_date: '',
  bank_name: '', bank_account_number: '', bank_account_name: '', other_cooperatives: '', other_debts: '',
  referee_one: '', referee_two: '', kin_full_name: '', kin_relationship: '', kin_phone: '', kin_email: '', kin_address: '',
  certify: false, website: '',
};
const NULLABLE = ['date_of_birth', 'employment_date', 'department', 'staff_number'];

function Section({ title, description, children }) {
  return (
    <Card>
      <CardHeader title={title} description={description} />
      <CardBody className="grid gap-4 sm:grid-cols-2">{children}</CardBody>
    </Card>
  );
}

export default function JoinApplication() {
  const [received, setReceived] = useState(null);
  const info = useQuery({ queryKey: ['public', 'departments'], queryFn: publicApi.departments, retry: false });
  const { register, handleSubmit, setError, formState: { errors, isSubmitting } } = useForm({ defaultValues: EMPTY });
  const [error, setErrorState] = useState(null);
  const req = { required: 'This field is required.' };
  const err = (name) => errors[name]?.message;

  const onSubmit = async (values) => {
    setErrorState(null);
    const { kin_full_name, kin_relationship, kin_phone, kin_email, kin_address, ...data } = values;
    NULLABLE.forEach((k) => { if (data[k] === '') data[k] = null; });
    data.next_of_kin = { full_name: kin_full_name, relationship: kin_relationship, phone: kin_phone, email: kin_email, address: kin_address };
    try {
      setReceived(await publicApi.apply(data));
      window.scrollTo(0, 0);
    } catch (e) {
      const kin = e?.response?.data?.error?.fields?.next_of_kin;
      if (kin && typeof kin === 'object') Object.entries(kin).forEach(([k, m]) => setError(`kin_${k}`, { type: 'server', message: [].concat(m)[0] }));
      applyFieldErrors(e, setError);
      setErrorState(e);
    }
  };

  const society = info.data?.society || 'EMDI Cooperative Multipurpose Society Ltd';
  return (
    <div className="min-h-screen bg-slate-50 px-4 py-8">
      <div className="mx-auto max-w-3xl">
        <div className="flex flex-col items-center text-center">
          <BrandLogo size={88} />
          <h1 className="mt-4 text-2xl font-bold text-slate-900">Apply to join</h1>
          <p className="mt-1 text-sm text-slate-600">{society} · Membership is open to EMDI and EMDI CMS staff.</p>
        </div>

        {received ? (
          <Card className="mt-8">
            <CardBody className="space-y-3 text-center">
              <CheckCircle2 className="mx-auto h-12 w-12 text-emerald-600" aria-hidden="true" />
              <h2 className="text-lg font-semibold text-slate-900">Application received</h2>
              <p className="text-sm text-slate-600">
                Thank you, {received.full_name}. Your application number is <strong>{received.reference}</strong>.
                The Secretary will check your details and referees, and the Chairman will approve it. If you gave an email address,
                you will receive a link to set your password once you are approved.
              </p>
              <Link to="/login" className="inline-block text-sm font-medium text-brand-600 hover:underline">Go to sign in</Link>
            </CardBody>
          </Card>
        ) : (
          <form onSubmit={handleSubmit(onSubmit)} noValidate className="mt-8 space-y-6">
            <p className="text-sm text-slate-600">All sections must be filled in. Fields marked * are required.</p>
            <ErrorAlert error={error} />

            <Section title="About you">
              <SelectField label="Title" {...register('title')} error={err('title')}><option value="">—</option>{options(TITLES)}</SelectField>
              <TextField label="Surname" required {...register('last_name', req)} error={err('last_name')} />
              <TextField label="First name" required {...register('first_name', req)} error={err('first_name')} />
              <TextField label="Other names" {...register('middle_name')} error={err('middle_name')} />
              <TextField label="Former or maiden name" {...register('former_name')} error={err('former_name')} />
              <TextField label="Date of birth" type="date" {...register('date_of_birth')} error={err('date_of_birth')} />
              <SelectField label="Sex" {...register('gender')} error={err('gender')}><option value="">—</option>{options(GENDERS)}</SelectField>
              <SelectField label="Marital status" {...register('marital_status')} error={err('marital_status')}><option value="">—</option>{options(MARITAL)}</SelectField>
              <TextField label="State of origin" {...register('state_of_origin')} error={err('state_of_origin')} />
              <TextField label="Local government area" {...register('lga')} error={err('lga')} />
            </Section>

            <Section title="Contact">
              <TextField label="Mobile number" required type="tel" {...register('phone', req)} error={err('phone')} />
              <TextField label="Email address" type="email" {...register('email')} error={err('email')} hint="To receive your sign-in link once approved." />
              <div className="sm:col-span-2"><TextAreaField label="Current home address" required rows={2} {...register('residential_address', req)} error={err('residential_address')} /></div>
              <div className="sm:col-span-2"><TextAreaField label="Permanent home address" rows={2} {...register('permanent_address')} error={err('permanent_address')} /></div>
            </Section>

            <Section title="Work at EMDI">
              <TextField label="Current designation" required {...register('designation', req)} error={err('designation')} />
              <TextField label="Grade (CR)" {...register('grade_level')} error={err('grade_level')} hint="e.g. CR 07" />
              <SelectField label="Department" {...register('department')} error={err('department')}>
                <option value="">—</option>
                {(info.data?.departments || []).map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
              </SelectField>
              <TextField label="Staff number" {...register('staff_number')} error={err('staff_number')} />
              <TextField label="Date you joined EMDI" type="date" {...register('employment_date')} error={err('employment_date')} />
            </Section>

            <Section title="Bank account" description="For payouts such as dividends.">
              <TextField label="Bank" {...register('bank_name')} error={err('bank_name')} />
              <TextField label="Account number" inputMode="numeric" {...register('bank_account_number')} error={err('bank_account_number')} />
              <div className="sm:col-span-2"><TextField label="Account name" {...register('bank_account_name')} error={err('bank_account_name')} /></div>
            </Section>

            <Section title="Other societies and debts">
              <div className="sm:col-span-2"><TextAreaField label="Cooperative societies you belong to, and where" rows={2} {...register('other_cooperatives')} error={err('other_cooperatives')} /></div>
              <div className="sm:col-span-2"><TextAreaField label="Organisations you currently owe (if any)" rows={2} {...register('other_debts')} error={err('other_debts')} /></div>
            </Section>

            <Section title="Next of kin">
              <TextField label="Full name" required {...register('kin_full_name', req)} error={err('kin_full_name')} />
              <TextField label="Relationship" required {...register('kin_relationship', req)} error={err('kin_relationship')} />
              <TextField label="Mobile number" required type="tel" {...register('kin_phone', req)} error={err('kin_phone')} />
              <TextField label="Email address" type="email" {...register('kin_email')} error={err('kin_email')} />
              <div className="sm:col-span-2"><TextField label="Permanent or work address" {...register('kin_address')} error={err('kin_address')} /></div>
            </Section>

            <Section title="Referees" description="Two EMDI staff, not below CR 07, who are members of the society. By standing for you, they accept liability if you default or abscond.">
              <TextField label="First referee's membership number" required {...register('referee_one', req)} error={err('referee_one')} />
              <TextField label="Second referee's membership number" required {...register('referee_two', req)} error={err('referee_two')} />
            </Section>

            {/* Hidden from people; automated spam fills it in. */}
            <input type="text" tabIndex={-1} autoComplete="off" aria-hidden="true" className="hidden" {...register('website')} />

            <Card>
              <CardBody className="space-y-4">
                <CheckboxField label="I certify that all the information given above is true." {...register('certify', { required: 'Please confirm.' })} />
                {errors.certify && <p className="text-xs text-red-600">{errors.certify.message}</p>}
                <Button type="submit" className="w-full sm:w-auto" loading={isSubmitting}>Submit application</Button>
              </CardBody>
            </Card>
          </form>
        )}
        <p className="mt-8 text-center text-xs text-slate-400">Already a member? <Link to="/login" className="text-brand-600 hover:underline">Sign in</Link></p>
      </div>
    </div>
  );
}
