import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { KeyRound } from 'lucide-react';
import { memberApi } from '../../api/member';
import { Alert, ErrorAlert } from '../../components/ui/Alert';
import { StatusBadge } from '../../components/ui/Badge';
import Button from '../../components/ui/Button';
import { Card, CardBody, CardHeader } from '../../components/ui/Card';
import { TextAreaField, TextField } from '../../components/ui/Field';
import PageHeader from '../../components/ui/PageHeader';
import QueryState from '../../components/ui/QueryState';
import { applyFieldErrors } from '../../lib/errors';
import { formatDate } from '../../lib/format';

export default function Profile() {
  const query = useQuery({ queryKey: ['me', 'profile'], queryFn: memberApi.profile });
  return (
    <div className="space-y-6">
      <PageHeader title="Profile" description="Your cooperative record. Contact the secretariat to correct anything you can't edit here."
        actions={<Link to="/change-password"><Button variant="secondary" icon={KeyRound}>Change password</Button></Link>} />
      <QueryState query={query}>{(member) => <ProfileView member={member} />}</QueryState>
    </div>
  );
}

function Detail({ label, value }) {
  return (
    <div>
      <dt className="text-xs font-medium uppercase tracking-wide text-slate-500">{label}</dt>
      <dd className="mt-0.5 text-sm text-slate-800">{value || '—'}</dd>
    </div>
  );
}

function ProfileView({ member }) {
  return (
    <div className="grid gap-6 lg:grid-cols-3">
      <div className="space-y-6 lg:col-span-2">
        <Card>
          <CardHeader title="Membership" action={<StatusBadge status={member.status} label={member.status_label} />} />
          <CardBody>
            <dl className="grid gap-4 sm:grid-cols-3">
              <Detail label="Membership number" value={member.membership_number} />
              <Detail label="Member since" value={formatDate(member.date_joined)} />
              <Detail label="Email" value={member.email} />
            </dl>
          </CardBody>
        </Card>
        <Card>
          <CardHeader title="Personal information" />
          <CardBody>
            <dl className="grid gap-4 sm:grid-cols-3">
              <Detail label="Name" value={[member.title && member.title.charAt(0) + member.title.slice(1).toLowerCase(), member.full_name].filter(Boolean).join(' ')} />
              <Detail label="Gender" value={member.gender && member.gender.charAt(0) + member.gender.slice(1).toLowerCase()} />
              <Detail label="Date of birth" value={formatDate(member.date_of_birth)} />
              <Detail label="State of origin" value={member.state_of_origin} />
              <Detail label="LGA" value={member.lga} />
            </dl>
          </CardBody>
        </Card>
        <Card>
          <CardHeader title="Employment" />
          <CardBody>
            <dl className="grid gap-4 sm:grid-cols-3">
              <Detail label="Staff number" value={member.staff_number} />
              <Detail label="IPPIS number" value={member.ippis_number} />
              <Detail label="Department" value={member.department?.name} />
              <Detail label="Unit" value={member.unit} />
              <Detail label="Designation" value={member.designation} />
              <Detail label="Grade level" value={member.grade_level} />
            </dl>
          </CardBody>
        </Card>
        <Card>
          <CardHeader title="Next of kin" />
          <CardBody>
            {member.next_of_kin.length ? (
              <ul className="space-y-3">
                {member.next_of_kin.map((k) => (
                  <li key={k.id} className="text-sm">
                    <p className="font-semibold text-slate-800">{k.full_name} {k.is_primary && <span className="text-xs font-normal text-slate-500">(primary)</span>}</p>
                    <p className="text-slate-600">{k.relationship} · {k.phone}</p>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-sm text-slate-500">No next of kin recorded.</p>
            )}
          </CardBody>
        </Card>
      </div>
      <ContactForm member={member} />
    </div>
  );
}

function ContactForm({ member }) {
  const queryClient = useQueryClient();
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState(null);
  const { register, handleSubmit, formState, setError: setFieldError } = useForm({
    defaultValues: { phone: member.phone, alt_phone: member.alt_phone, residential_address: member.residential_address },
  });
  const onSubmit = async (values) => {
    setSaved(false);
    setError(null);
    try {
      queryClient.setQueryData(['me', 'profile'], await memberApi.updateProfile(values));
      setSaved(true);
    } catch (err) {
      if (!applyFieldErrors(err, setFieldError)) setError(err);
    }
  };
  return (
    <Card className="h-fit">
      <CardHeader title="Contact details" description="You can update these yourself." />
      <CardBody>
        <form className="space-y-4" onSubmit={handleSubmit(onSubmit)} noValidate>
          {saved && <Alert tone="success">Contact details saved.</Alert>}
          <ErrorAlert error={error} />
          <TextField label="Phone" type="tel" autoComplete="tel" required error={formState.errors.phone?.message} {...register('phone', { required: 'A phone number is required.' })} />
          <TextField label="Alternative phone" type="tel" error={formState.errors.alt_phone?.message} {...register('alt_phone')} />
          <TextAreaField label="Residential address" rows={3} error={formState.errors.residential_address?.message} {...register('residential_address')} />
          <Button type="submit" className="w-full" loading={formState.isSubmitting}>Save contact details</Button>
        </form>
      </CardBody>
    </Card>
  );
}
