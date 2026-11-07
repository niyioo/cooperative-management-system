import { useForm } from 'react-hook-form';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { ArrowLeft } from 'lucide-react';
import { adminApi } from '../../../api/admin';
import useReference from '../../../components/officer/useReference';
import { ErrorAlert } from '../../../components/ui/Alert';
import Button from '../../../components/ui/Button';
import { Card, CardBody, CardHeader } from '../../../components/ui/Card';
import { CheckboxField, SelectField, TextAreaField, TextField } from '../../../components/ui/Field';
import PageHeader from '../../../components/ui/PageHeader';
import QueryState from '../../../components/ui/QueryState';
import { EMPLOYMENT, GENDERS, MARITAL, MEMBERSHIP_TYPE, TITLES, options } from '../../../lib/choices';
import { applyFieldErrors } from '../../../lib/errors';

// Optional fields the API stores as NULL rather than an empty string.
const NULLABLE = ['date_of_birth', 'employment_date', 'staff_number', 'ippis_number', 'department', 'referee_one', 'referee_two',
  'application_date', 'membership_fee_paid', 'monthly_net_pay'];

const EMPTY = {
  membership_number: '', email: '', title: '', first_name: '', middle_name: '', last_name: '', gender: '', date_of_birth: '', marital_status: '',
  phone: '', alt_phone: '', residential_address: '', state_of_origin: '', lga: '',
  staff_number: '', ippis_number: '', department: '', unit: '', designation: '', grade_level: '', employment_date: '', employment_status: 'ACTIVE',
  date_joined: '', bank_name: '', bank_account_number: '', bank_account_name: '',
  former_name: '', permanent_address: '', other_cooperatives: '', other_debts: '', referee_one: '', referee_two: '',
  application_date: '', membership_fee_paid: '', is_official: false, monthly_net_pay: '',
  membership_type: 'MEMBER', status: 'ACTIVE', send_activation: true,
  kin_full_name: '', kin_relationship: '', kin_phone: '', kin_email: '', kin_address: '',
};

function fromMember(m) {
  const values = { ...EMPTY };
  Object.keys(EMPTY).forEach((k) => {
    if (k in m && m[k] !== null) values[k] = m[k];
  });
  values.department = m.department?.id || '';
  values.email = m.portal?.has_email ? m.email : '';
  values.referee_one = m.referees?.[0]?.membership_number || '';
  values.referee_two = m.referees?.[1]?.membership_number || '';
  return values;
}

function toPayload(values, creating) {
  const { kin_full_name, kin_relationship, kin_phone, kin_email, kin_address, status, send_activation, membership_type, ...data } = values;
  NULLABLE.forEach((k) => { if (data[k] === '') data[k] = null; });
  if (!data.date_joined) delete data.date_joined;
  if (!data.membership_number) delete data.membership_number;
  if (!data.email) delete data.email;
  if (creating) {
    Object.assign(data, { membership_type, status, send_activation: membership_type === 'MEMBER' && send_activation && !!values.email });
    if (kin_full_name) {
      data.next_of_kin = { full_name: kin_full_name, relationship: kin_relationship, phone: kin_phone, email: kin_email, address: kin_address };
    }
  }
  return data;
}

// Next of kin is optional, but once a name is given the API needs the relationship and phone too.
const kinRequired = (value, values) => !values.kin_full_name || !!value.trim() || 'Required when a next of kin is given.';

function Section({ title, description, children }) {
  return (
    <Card>
      <CardHeader title={title} description={description} />
      <CardBody className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">{children}</CardBody>
    </Card>
  );
}

function MemberFormBody({ member }) {
  const creating = !member;
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const departments = useReference('departments', { is_active: true });
  const { register, handleSubmit, setError, watch, formState: { errors } } = useForm({ defaultValues: member ? fromMember(member) : EMPTY });
  const mutation = useMutation({
    mutationFn: (values) => (creating ? adminApi.members.create(toPayload(values, true)) : adminApi.members.update(member.id, toPayload(values, false))),
    onSuccess: (saved) => {
      queryClient.invalidateQueries({ queryKey: ['admin'] });
      navigate(`/admin/members/${saved.id}`);
    },
    onError: (error) => {
      const fields = error?.response?.data?.error?.fields;
      if (fields?.next_of_kin && typeof fields.next_of_kin === 'object') {
        Object.entries(fields.next_of_kin).forEach(([k, msgs]) => setError(`kin_${k}`, { type: 'server', message: [].concat(msgs)[0] }));
      }
      applyFieldErrors(error, setError);
    },
  });
  const err = (name) => errors[name]?.message;
  const req = { required: 'This field is required.' };
  const hasEmail = !!watch('email');
  const isSaver = watch('membership_type') === 'CHRISTMAS_SAVER';

  return (
    <form onSubmit={handleSubmit((v) => mutation.mutate(v))} noValidate className="space-y-6">
      <ErrorAlert error={mutation.error} />

      <Section title="Personal details">
        <SelectField label="Title" {...register('title')} error={err('title')}><option value="">—</option>{options(TITLES)}</SelectField>
        <TextField label="First name" required {...register('first_name', req)} error={err('first_name')} />
        <TextField label="Middle name" {...register('middle_name')} error={err('middle_name')} />
        <TextField label="Last name" required {...register('last_name', req)} error={err('last_name')} />
        <SelectField label="Gender" {...register('gender')} error={err('gender')}><option value="">—</option>{options(GENDERS)}</SelectField>
        <TextField label="Date of birth" type="date" {...register('date_of_birth')} error={err('date_of_birth')} />
        <SelectField label="Marital status" {...register('marital_status')} error={err('marital_status')}><option value="">—</option>{options(MARITAL)}</SelectField>
        <TextField label="State of origin" {...register('state_of_origin')} error={err('state_of_origin')} />
        <TextField label="LGA" {...register('lga')} error={err('lga')} />
        <TextField label="Former or maiden name" {...register('former_name')} error={err('former_name')} />
      </Section>

      <Section title="Contact">
        <TextField label="Phone" required type="tel" {...register('phone', req)} error={err('phone')} />
        <TextField label="Alternative phone" type="tel" {...register('alt_phone')} error={err('alt_phone')} />
        <TextField label="Email" type="email" {...register('email')} error={err('email')} hint="Needed for portal access by email." />
        <div className="sm:col-span-2 lg:col-span-3">
          <TextAreaField label="Current home address" rows={2} {...register('residential_address')} error={err('residential_address')} />
        </div>
        <div className="sm:col-span-2 lg:col-span-3">
          <TextAreaField label="Permanent home address" rows={2} {...register('permanent_address')} error={err('permanent_address')} />
        </div>
      </Section>

      <Section title="Employment">
        <TextField label="Staff number" {...register('staff_number')} error={err('staff_number')} />
        <TextField label="IPPIS number" {...register('ippis_number')} error={err('ippis_number')} />
        <SelectField label="Department" {...register('department')} error={err('department')}>
          <option value="">—</option>
          {(departments.data || []).map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
        </SelectField>
        <TextField label="Unit" {...register('unit')} error={err('unit')} />
        <TextField label="Designation" {...register('designation')} error={err('designation')} />
        <TextField label="Grade level" {...register('grade_level')} error={err('grade_level')} />
        <TextField label="Employment date" type="date" {...register('employment_date')} error={err('employment_date')} />
        <SelectField label="Employment status" {...register('employment_status')} error={err('employment_status')}>{options(EMPLOYMENT)}</SelectField>
        <TextField label="Monthly net pay (₦)" inputMode="decimal" {...register('monthly_net_pay')} error={err('monthly_net_pay')}
          hint="Shown to the secretary and chairman when deciding loans." />
      </Section>

      <Section title="Membership form" description="From the paper membership form.">
        <TextField label="Referee 1 (membership no.)" {...register('referee_one')} error={err('referee_one')} hint="EMDI staff, CR 07 or above, and a member" />
        <TextField label="Referee 2 (membership no.)" {...register('referee_two')} error={err('referee_two')} hint="Liable if the applicant defaults" />
        <TextField label="Date form submitted" type="date" {...register('application_date')} error={err('application_date')} />
        <TextField label="Membership fee paid (₦)" inputMode="decimal" {...register('membership_fee_paid')} error={err('membership_fee_paid')} />
        <div className="sm:col-span-2 lg:col-span-3">
          <TextAreaField label="Other cooperative societies and their location" rows={2} {...register('other_cooperatives')} error={err('other_cooperatives')} />
        </div>
        <div className="sm:col-span-2 lg:col-span-3">
          <TextAreaField label="Organisations currently owed (if any)" rows={2} {...register('other_debts')} error={err('other_debts')} />
        </div>
        {!isSaver && (
          <CheckboxField label="An official of the society (chairman, secretary or treasurer): may borrow more on the cooperative loan"
            {...register('is_official')} />
        )}
      </Section>

      <Section title="Membership & bank">
        {creating && (
          <div className="sm:col-span-2">
            <SelectField label="Type" {...register('membership_type')} error={err('membership_type')}>{options(MEMBERSHIP_TYPE)}</SelectField>
            {isSaver && (
              <p className="mt-1 text-xs text-slate-500">
                A Christmas saver is not a member: they save only in Christmas Savings through payroll, are numbered separately
                (e.g. EMDI/XMAS/0001) and have no portal access. They can be made a full member later.
              </p>
            )}
          </div>
        )}
        <TextField label="Membership number" {...register('membership_number')} error={err('membership_number')} hint={creating ? 'Leave blank to generate the next number.' : undefined} />
        <TextField label="Date joined" type="date" {...register('date_joined')} error={err('date_joined')} hint={creating ? 'Defaults to today.' : undefined} />
        {creating && (
          <SelectField label="Initial status" {...register('status')} error={err('status')}>
            <option value="ACTIVE">Active</option>
            <option value="PENDING">Pending (activate later)</option>
          </SelectField>
        )}
        <TextField label="Bank name" {...register('bank_name')} error={err('bank_name')} />
        <TextField label="Account number" inputMode="numeric" {...register('bank_account_number')} error={err('bank_account_number')} />
        <TextField label="Account name" {...register('bank_account_name')} error={err('bank_account_name')} />
      </Section>

      {creating && (
        <Section title="Next of kin" description="Optional now; more can be added from the member's profile.">
          <TextField label="Full name" {...register('kin_full_name')} error={err('kin_full_name')} />
          <TextField label="Relationship" {...register('kin_relationship', { validate: kinRequired })} error={err('kin_relationship')} />
          <TextField label="Phone" type="tel" {...register('kin_phone', { validate: kinRequired })} error={err('kin_phone')} />
          <TextField label="Email" type="email" {...register('kin_email')} error={err('kin_email')} />
          <div className="sm:col-span-2">
            <TextField label="Address" {...register('kin_address')} error={err('kin_address')} />
          </div>
        </Section>
      )}

      {creating && !isSaver && (
        <CheckboxField label={hasEmail ? 'Email the member a link to set up portal access' : 'Email an activation link (add an email address first)'}
          disabled={!hasEmail} {...register('send_activation')} />
      )}

      <div className="flex justify-end gap-2">
        <Link to={member ? `/admin/members/${member.id}` : '/admin/members'}><Button variant="secondary">Cancel</Button></Link>
        <Button type="submit" loading={mutation.isPending}>{creating ? 'Register member' : 'Save changes'}</Button>
      </div>
    </form>
  );
}

export default function MemberForm() {
  const { id } = useParams();
  const member = useQuery({ queryKey: ['admin', 'member', id], queryFn: () => adminApi.members.get(id), enabled: !!id });
  return (
    <>
      <Link to={id ? `/admin/members/${id}` : '/admin/members'} className="inline-flex items-center gap-1 text-sm font-medium text-brand-600 hover:underline">
        <ArrowLeft className="h-4 w-4" aria-hidden="true" /> {id ? 'Back to member' : 'Members'}
      </Link>
      <div className="mt-2">
        <PageHeader title={id ? 'Edit member' : 'Register a member'} />
      </div>
      {id ? <QueryState query={member}>{(m) => <MemberFormBody member={m} />}</QueryState> : <MemberFormBody />}
    </>
  );
}
