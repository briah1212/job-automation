'use client'

import { useEffect, useState } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Checkbox } from '@/components/ui/checkbox'
import { useForm } from 'react-hook-form'
import { Loader2, Save } from 'lucide-react'
import { apiClient } from '@/lib/api-client'
import type { Profile, ProfileUpdate } from '@/lib/types'

interface ProfileForm {
  legal_name: string
  preferred_name: string
  email: string
  phone: string
  linkedin: string
  github: string
  career_interests: string
  target_seniority: string
  work_authorization: string
  date_of_birth: string
  address_line1: string
  address_line2: string
  city: string
  state: string
  postal_code: string
  country: string
  graduation_year: string
  relocation_willingness: string
  salary_expectation_min: string
  salary_expectation_max: string
  citizenship: string
  clearance_eligible: boolean
}

function profileToForm(profile: Profile | null): ProfileForm {
  return {
    legal_name: profile?.legal_name ?? '',
    preferred_name: profile?.preferred_name ?? '',
    email: profile?.email ?? '',
    phone: profile?.phone ?? '',
    linkedin: profile?.linkedin ?? '',
    github: profile?.github ?? '',
    career_interests: profile?.career_interests ?? '',
    target_seniority: profile?.target_seniority ?? '',
    work_authorization: profile?.work_authorization ?? '',
    date_of_birth: profile?.date_of_birth ?? '',
    address_line1: profile?.address_line1 ?? '',
    address_line2: profile?.address_line2 ?? '',
    city: profile?.city ?? '',
    state: profile?.state ?? '',
    postal_code: profile?.postal_code ?? '',
    country: profile?.country ?? '',
    graduation_year: profile?.graduation_year != null ? String(profile.graduation_year) : '',
    relocation_willingness: profile?.relocation_willingness ?? '',
    salary_expectation_min: profile?.salary_expectation_min != null ? String(profile.salary_expectation_min) : '',
    salary_expectation_max: profile?.salary_expectation_max != null ? String(profile.salary_expectation_max) : '',
    citizenship: profile?.citizenship ?? '',
    clearance_eligible: profile?.clearance_eligible ?? false,
  }
}

function formToUpdate(data: ProfileForm): ProfileUpdate {
  const toIntOrUndefined = (value: string) => (value.trim() ? Number(value) : undefined)
  return {
    legal_name: data.legal_name || undefined,
    preferred_name: data.preferred_name || undefined,
    email: data.email || undefined,
    phone: data.phone || undefined,
    linkedin: data.linkedin || undefined,
    github: data.github || undefined,
    career_interests: data.career_interests || undefined,
    target_seniority: data.target_seniority || undefined,
    work_authorization: data.work_authorization || undefined,
    date_of_birth: data.date_of_birth || undefined,
    address_line1: data.address_line1 || undefined,
    address_line2: data.address_line2 || undefined,
    city: data.city || undefined,
    state: data.state || undefined,
    postal_code: data.postal_code || undefined,
    country: data.country || undefined,
    graduation_year: toIntOrUndefined(data.graduation_year),
    relocation_willingness: data.relocation_willingness || undefined,
    salary_expectation_min: toIntOrUndefined(data.salary_expectation_min),
    salary_expectation_max: toIntOrUndefined(data.salary_expectation_max),
    citizenship: data.citizenship || undefined,
    clearance_eligible: data.clearance_eligible,
  }
}

export default function ProfilePage() {
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [saved, setSaved] = useState(false)

  const { register, handleSubmit, reset, watch, setValue, formState: { errors } } = useForm<ProfileForm>({
    defaultValues: profileToForm(null),
  })

  useEffect(() => {
    const load = async () => {
      try {
        setLoading(true)
        const profile = await apiClient.getProfile()
        reset(profileToForm(profile))
      } catch (err) {
        const status = (err as { status?: number } | undefined)?.status
        if (status !== 404) {
          setError('Failed to load profile')
          console.error(err)
        }
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [reset])

  const onSubmit = async (data: ProfileForm) => {
    try {
      setSaving(true)
      setError(null)
      setSaved(false)
      const updated = await apiClient.updateProfile(formToUpdate(data))
      reset(profileToForm(updated))
      setSaved(true)
    } catch (err) {
      setError('Failed to save profile')
      console.error(err)
    } finally {
      setSaving(false)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-24">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-bold">Profile</h1>
      </div>

      {error && (
        <Card className="border-red-200 bg-red-50">
          <CardContent className="pt-6">
            <p className="text-sm text-red-800">{error}</p>
          </CardContent>
        </Card>
      )}

      <form onSubmit={handleSubmit(onSubmit)} className="space-y-6">
        <Card>
          <CardHeader>
            <CardTitle>Personal Information</CardTitle>
            <CardDescription>Basic details for your applications</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-4 md:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="legal_name">Legal Name *</Label>
                <Input id="legal_name" {...register('legal_name', { required: true })} />
                {errors.legal_name && <p className="text-sm text-red-500">Required</p>}
              </div>
              <div className="space-y-2">
                <Label htmlFor="preferred_name">Preferred Name</Label>
                <Input id="preferred_name" {...register('preferred_name')} />
              </div>
            </div>

            <div className="grid gap-4 md:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="email">Email *</Label>
                <Input id="email" type="email" {...register('email', { required: true })} />
                {errors.email && <p className="text-sm text-red-500">Required</p>}
              </div>
              <div className="space-y-2">
                <Label htmlFor="phone">Phone</Label>
                <Input id="phone" {...register('phone')} />
              </div>
            </div>

            <div className="grid gap-4 md:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="linkedin">LinkedIn</Label>
                <Input id="linkedin" {...register('linkedin')} placeholder="https://linkedin.com/in/..." />
              </div>
              <div className="space-y-2">
                <Label htmlFor="github">GitHub</Label>
                <Input id="github" {...register('github')} placeholder="https://github.com/..." />
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="date_of_birth">Date of Birth</Label>
              <Input id="date_of_birth" type="date" {...register('date_of_birth')} className="max-w-xs" />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Address</CardTitle>
            <CardDescription>Used to auto-fill application address fields</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-4 md:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="address_line1">Address Line 1</Label>
                <Input id="address_line1" {...register('address_line1')} />
              </div>
              <div className="space-y-2">
                <Label htmlFor="address_line2">Address Line 2</Label>
                <Input id="address_line2" {...register('address_line2')} />
              </div>
            </div>
            <div className="grid gap-4 md:grid-cols-4">
              <div className="space-y-2">
                <Label htmlFor="city">City</Label>
                <Input id="city" {...register('city')} />
              </div>
              <div className="space-y-2">
                <Label htmlFor="state">State</Label>
                <Input id="state" {...register('state')} />
              </div>
              <div className="space-y-2">
                <Label htmlFor="postal_code">Postal Code</Label>
                <Input id="postal_code" {...register('postal_code')} />
              </div>
              <div className="space-y-2">
                <Label htmlFor="country">Country</Label>
                <Input id="country" {...register('country')} />
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Career Preferences</CardTitle>
            <CardDescription>Help us match you with the right opportunities</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-4 md:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="target_seniority">Target Seniority *</Label>
                <Input id="target_seniority" {...register('target_seniority', { required: true })} placeholder="Senior, Staff, Principal" />
                {errors.target_seniority && <p className="text-sm text-red-500">Required</p>}
              </div>
              <div className="space-y-2">
                <Label htmlFor="work_authorization">Work Authorization *</Label>
                <Input id="work_authorization" {...register('work_authorization', { required: true })} placeholder="US Citizen, Green Card, H1B" />
                {errors.work_authorization && <p className="text-sm text-red-500">Required</p>}
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="career_interests">Career Interests</Label>
              <Input id="career_interests" {...register('career_interests')} placeholder="Backend infrastructure, distributed systems, ..." />
            </div>

            <div className="grid gap-4 md:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="graduation_year">Graduation Year</Label>
                <Input id="graduation_year" type="number" {...register('graduation_year')} />
              </div>
              <div className="space-y-2">
                <Label htmlFor="citizenship">Citizenship</Label>
                <Input id="citizenship" {...register('citizenship')} />
              </div>
            </div>

            <div className="grid gap-4 md:grid-cols-3">
              <div className="space-y-2">
                <Label htmlFor="relocation_willingness">Relocation Willingness</Label>
                <Input id="relocation_willingness" {...register('relocation_willingness')} placeholder="Yes, No, Depends" />
              </div>
              <div className="space-y-2">
                <Label htmlFor="salary_expectation_min">Salary Expectation (Min)</Label>
                <Input id="salary_expectation_min" type="number" {...register('salary_expectation_min')} />
              </div>
              <div className="space-y-2">
                <Label htmlFor="salary_expectation_max">Salary Expectation (Max)</Label>
                <Input id="salary_expectation_max" type="number" {...register('salary_expectation_max')} />
              </div>
            </div>

            <div className="flex items-center gap-2">
              <Checkbox
                id="clearance_eligible"
                checked={watch('clearance_eligible')}
                onCheckedChange={(checked) => setValue('clearance_eligible', checked === true)}
              />
              <Label htmlFor="clearance_eligible" className="font-normal">
                Eligible for security clearance
              </Label>
            </div>
          </CardContent>
        </Card>

        <div className="flex items-center justify-end gap-3">
          {saved && <span className="text-sm text-green-600">Saved</span>}
          <Button type="submit" disabled={saving}>
            {saving ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            ) : (
              <Save className="mr-2 h-4 w-4" />
            )}
            {saving ? 'Saving...' : 'Save Profile'}
          </Button>
        </div>
      </form>
    </div>
  )
}
