'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { useForm } from 'react-hook-form'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Checkbox } from '@/components/ui/checkbox'
import { Textarea } from '@/components/ui/textarea'
import { apiClient } from '@/lib/api-client'
import { SearchProfileUpdate } from '@/lib/types'
import { Save, Loader2 } from 'lucide-react'

interface SearchProfileFormData {
  name: string
  include_titles: string
  exclude_titles: string
  include_skills: string
  exclude_skills: string
  locations: string
  remote_policy: 'required' | 'hybrid_ok' | 'no_preference' | 'onsite_only'
  min_salary: string
  excluded_companies: string
}

const CAREER_CATEGORIES = [
  'Software Engineering',
  'Data Science',
  'Product Management',
  'Design',
  'DevOps',
]

const REMOTE_POLICIES = [
  { value: 'required', label: 'Remote Required' },
  { value: 'hybrid_ok', label: 'Hybrid OK' },
  { value: 'no_preference', label: 'No Preference' },
  { value: 'onsite_only', label: 'Onsite Only' },
] as const

export default function EditSearchProfilePage({ params }: { params: { id: string } }) {
  const router = useRouter()
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [notFound, setNotFound] = useState(false)
  const [selectedCategories, setSelectedCategories] = useState<string[]>([])

  const { register, handleSubmit, formState: { errors }, setValue, watch, reset } = useForm<SearchProfileFormData>({
    defaultValues: {
      name: '',
      include_titles: '',
      exclude_titles: '',
      include_skills: '',
      exclude_skills: '',
      locations: '',
      remote_policy: 'no_preference',
      min_salary: '',
      excluded_companies: '',
    },
  })

  useEffect(() => {
    const load = async () => {
      try {
        setLoading(true)
        const profile = await apiClient.getSearchProfile(params.id)
        setSelectedCategories(profile.career_categories)
        reset({
          name: profile.name,
          include_titles: profile.include_titles.join(', '),
          exclude_titles: profile.exclude_titles.join(', '),
          include_skills: profile.include_skills.join(', '),
          exclude_skills: profile.exclude_skills.join(', '),
          locations: profile.locations.join(', '),
          remote_policy: profile.remote_policy ?? 'no_preference',
          min_salary: profile.min_salary != null ? String(profile.min_salary) : '',
          excluded_companies: profile.excluded_companies.join(', '),
        })
      } catch (err) {
        const status = (err as { status?: number } | undefined)?.status
        if (status === 404) setNotFound(true)
        console.error('Failed to load search profile:', err)
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [params.id, reset])

  const handleCategoryToggle = (category: string) => {
    setSelectedCategories((prev) =>
      prev.includes(category) ? prev.filter((c) => c !== category) : [...prev, category]
    )
  }

  const onSubmit = async (data: SearchProfileFormData) => {
    if (selectedCategories.length === 0) {
      alert('Please select at least one career category')
      return
    }

    setSaving(true)
    try {
      const payload: SearchProfileUpdate = {
        name: data.name,
        career_categories: selectedCategories,
        include_titles: data.include_titles ? data.include_titles.split(',').map((s) => s.trim()).filter(Boolean) : [],
        exclude_titles: data.exclude_titles ? data.exclude_titles.split(',').map((s) => s.trim()).filter(Boolean) : [],
        include_skills: data.include_skills ? data.include_skills.split(',').map((s) => s.trim()).filter(Boolean) : [],
        exclude_skills: data.exclude_skills ? data.exclude_skills.split(',').map((s) => s.trim()).filter(Boolean) : [],
        locations: data.locations ? data.locations.split(',').map((s) => s.trim()).filter(Boolean) : [],
        remote_policy: data.remote_policy,
        min_salary: data.min_salary ? parseInt(data.min_salary) : undefined,
        excluded_companies: data.excluded_companies ? data.excluded_companies.split(',').map((s) => s.trim()).filter(Boolean) : [],
      }

      await apiClient.updateSearchProfile(params.id, payload)
      router.push('/dashboard/search-profiles')
    } catch (error) {
      console.error('Failed to update search profile:', error)
      alert('Failed to update search profile. Please try again.')
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

  if (notFound) {
    return (
      <Card className="max-w-lg mx-auto mt-12">
        <CardContent className="pt-6">
          <p className="text-sm text-muted-foreground">Search profile not found.</p>
        </CardContent>
      </Card>
    )
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold">Edit Search Profile</h1>
        <p className="text-muted-foreground">Update your job search criteria</p>
      </div>

      <form onSubmit={handleSubmit(onSubmit)} className="space-y-6">
        <Card>
          <CardHeader>
            <CardTitle>Profile Details</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="name">Profile Name *</Label>
              <Input id="name" {...register('name', { required: 'Profile name is required' })} />
              {errors.name && <p className="text-sm text-red-500">{errors.name.message}</p>}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Career Categories *</CardTitle>
            <CardDescription>Select all categories that interest you</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {CAREER_CATEGORIES.map((category) => (
                <div key={category} className="flex items-center space-x-2">
                  <Checkbox
                    id={`category-${category}`}
                    checked={selectedCategories.includes(category)}
                    onCheckedChange={() => handleCategoryToggle(category)}
                  />
                  <Label htmlFor={`category-${category}`} className="text-sm font-normal cursor-pointer">
                    {category}
                  </Label>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Job Titles</CardTitle>
            <CardDescription>Specify titles to include or exclude (comma-separated)</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="include_titles">Include Titles</Label>
              <Textarea id="include_titles" {...register('include_titles')} rows={3} />
            </div>
            <div className="space-y-2">
              <Label htmlFor="exclude_titles">Exclude Titles</Label>
              <Textarea id="exclude_titles" {...register('exclude_titles')} rows={3} />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Skills</CardTitle>
            <CardDescription>Define required and excluded skills (comma-separated)</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="include_skills">Include Skills</Label>
              <Textarea id="include_skills" {...register('include_skills')} rows={3} />
            </div>
            <div className="space-y-2">
              <Label htmlFor="exclude_skills">Exclude Skills</Label>
              <Textarea id="exclude_skills" {...register('exclude_skills')} rows={3} />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Location & Remote Policy</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="locations">Locations</Label>
              <Textarea id="locations" {...register('locations')} rows={2} />
            </div>
            <div className="space-y-3">
              <Label>Remote Policy *</Label>
              <div className="space-y-2">
                {REMOTE_POLICIES.map((policy) => (
                  <div key={policy.value} className="flex items-center space-x-2">
                    <input
                      type="radio"
                      id={`remote-${policy.value}`}
                      value={policy.value}
                      {...register('remote_policy', { required: true })}
                      className="h-4 w-4 border-gray-300 text-primary focus:ring-primary"
                    />
                    <Label htmlFor={`remote-${policy.value}`} className="text-sm font-normal cursor-pointer">
                      {policy.label}
                    </Label>
                  </div>
                ))}
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Salary</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2 max-w-xs">
              <Label htmlFor="min_salary">Minimum Salary (USD)</Label>
              <Input id="min_salary" type="number" {...register('min_salary')} />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Additional Filters</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="excluded_companies">Excluded Companies</Label>
              <Textarea id="excluded_companies" {...register('excluded_companies')} rows={3} />
            </div>
          </CardContent>
        </Card>

        <div className="flex justify-end gap-3">
          <Button type="button" variant="outline" onClick={() => router.push('/dashboard/search-profiles')} disabled={saving}>
            Cancel
          </Button>
          <Button type="submit" disabled={saving}>
            {saving ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Saving...
              </>
            ) : (
              <>
                <Save className="mr-2 h-4 w-4" />
                Save Changes
              </>
            )}
          </Button>
        </div>
      </form>
    </div>
  )
}
