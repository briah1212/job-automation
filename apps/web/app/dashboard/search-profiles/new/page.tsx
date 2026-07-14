'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { useForm } from 'react-hook-form'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Checkbox } from '@/components/ui/checkbox'
import { Textarea } from '@/components/ui/textarea'
import { apiClient } from '@/lib/api-client'
import { SearchProfileCreate } from '@/lib/types'
import { Save, Loader2 } from 'lucide-react'

interface SearchProfileFormData {
  name: string
  career_categories: string[]
  include_titles: string
  exclude_titles: string
  include_skills: string
  exclude_skills: string
  locations: string
  remote_policy: 'required' | 'hybrid_ok' | 'no_preference' | 'onsite_only'
  min_salary: string
  max_salary: string
  exclude_companies: string
  require_visa_sponsorship: boolean
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

export default function NewSearchProfilePage() {
  const router = useRouter()
  const [loading, setLoading] = useState(false)
  const [selectedCategories, setSelectedCategories] = useState<string[]>([])
  
  const { register, handleSubmit, formState: { errors }, setValue, watch } = useForm<SearchProfileFormData>({
    defaultValues: {
      name: '',
      career_categories: [],
      include_titles: '',
      exclude_titles: '',
      include_skills: '',
      exclude_skills: '',
      locations: '',
      remote_policy: 'no_preference',
      min_salary: '',
      max_salary: '',
      exclude_companies: '',
      require_visa_sponsorship: false,
    },
  })

  const remotePolicy = watch('remote_policy')

  const handleCategoryToggle = (category: string) => {
    const updated = selectedCategories.includes(category)
      ? selectedCategories.filter((c) => c !== category)
      : [...selectedCategories, category]
    
    setSelectedCategories(updated)
    setValue('career_categories', updated)
  }

  const onSubmit = async (data: SearchProfileFormData) => {
    if (selectedCategories.length === 0) {
      alert('Please select at least one career category')
      return
    }

    setLoading(true)
    try {
      const payload: SearchProfileCreate = {
        name: data.name,
        enabled: true,
        career_categories: selectedCategories,
        include_titles: data.include_titles
          ? data.include_titles.split(',').map((s) => s.trim()).filter(Boolean)
          : [],
        exclude_titles: data.exclude_titles
          ? data.exclude_titles.split(',').map((s) => s.trim()).filter(Boolean)
          : [],
        include_skills: data.include_skills
          ? data.include_skills.split(',').map((s) => s.trim()).filter(Boolean)
          : [],
        exclude_skills: data.exclude_skills
          ? data.exclude_skills.split(',').map((s) => s.trim()).filter(Boolean)
          : [],
        locations: data.locations
          ? data.locations.split(',').map((s) => s.trim()).filter(Boolean)
          : [],
        remote_policy: data.remote_policy,
        min_salary: data.min_salary ? parseInt(data.min_salary) : undefined,
        max_salary: data.max_salary ? parseInt(data.max_salary) : undefined,
        exclude_companies: data.exclude_companies
          ? data.exclude_companies.split(',').map((s) => s.trim()).filter(Boolean)
          : [],
        require_visa_sponsorship: data.require_visa_sponsorship,
      }

      await apiClient.createSearchProfile(payload)
      router.push('/dashboard/search-profiles')
    } catch (error) {
      console.error('Failed to create search profile:', error)
      alert('Failed to create search profile. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">New Search Profile</h1>
          <p className="text-muted-foreground">
            Define your job search criteria to automatically find matching opportunities
          </p>
        </div>
      </div>

      <form onSubmit={handleSubmit(onSubmit)} className="space-y-6">
        <Card>
          <CardHeader>
            <CardTitle>Profile Details</CardTitle>
            <CardDescription>Give your search profile a memorable name</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="name">Profile Name *</Label>
              <Input
                id="name"
                placeholder="e.g., Senior Software Engineer - Remote"
                {...register('name', { required: 'Profile name is required' })}
              />
              {errors.name && (
                <p className="text-sm text-red-500">{errors.name.message}</p>
              )}
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
                  <Label
                    htmlFor={`category-${category}`}
                    className="text-sm font-normal cursor-pointer"
                  >
                    {category}
                  </Label>
                </div>
              ))}
            </div>
            {selectedCategories.length === 0 && (
              <p className="text-sm text-muted-foreground mt-3">
                Select at least one category
              </p>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Job Titles</CardTitle>
            <CardDescription>
              Specify titles to include or exclude (comma-separated)
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="include_titles">Include Titles</Label>
              <Textarea
                id="include_titles"
                placeholder="e.g., Senior Software Engineer, Staff Engineer, Principal Engineer"
                {...register('include_titles')}
                rows={3}
              />
              <p className="text-xs text-muted-foreground">
                Jobs with these titles will be prioritized
              </p>
            </div>

            <div className="space-y-2">
              <Label htmlFor="exclude_titles">Exclude Titles</Label>
              <Textarea
                id="exclude_titles"
                placeholder="e.g., Junior, Intern, Contract"
                {...register('exclude_titles')}
                rows={3}
              />
              <p className="text-xs text-muted-foreground">
                Jobs with these titles will be filtered out
              </p>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Skills</CardTitle>
            <CardDescription>
              Define required and excluded skills (comma-separated)
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="include_skills">Include Skills</Label>
              <Textarea
                id="include_skills"
                placeholder="e.g., Python, React, TypeScript, AWS, Docker"
                {...register('include_skills')}
                rows={3}
              />
              <p className="text-xs text-muted-foreground">
                Jobs requiring these skills will be prioritized
              </p>
            </div>

            <div className="space-y-2">
              <Label htmlFor="exclude_skills">Exclude Skills</Label>
              <Textarea
                id="exclude_skills"
                placeholder="e.g., PHP, WordPress, Cold Calling"
                {...register('exclude_skills')}
                rows={3}
              />
              <p className="text-xs text-muted-foreground">
                Jobs requiring these skills will be filtered out
              </p>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Location & Remote Policy</CardTitle>
            <CardDescription>
              Specify your location preferences and remote work requirements
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="locations">Locations</Label>
              <Textarea
                id="locations"
                placeholder="e.g., San Francisco, New York, Austin, Remote"
                {...register('locations')}
                rows={2}
              />
              <p className="text-xs text-muted-foreground">
                Comma-separated list of acceptable locations
              </p>
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
                    <Label
                      htmlFor={`remote-${policy.value}`}
                      className="text-sm font-normal cursor-pointer"
                    >
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
            <CardTitle>Salary Range</CardTitle>
            <CardDescription>
              Set your desired salary range (optional)
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid gap-4 md:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="min_salary">Minimum Salary (USD)</Label>
                <Input
                  id="min_salary"
                  type="number"
                  placeholder="e.g., 120000"
                  {...register('min_salary')}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="max_salary">Maximum Salary (USD)</Label>
                <Input
                  id="max_salary"
                  type="number"
                  placeholder="e.g., 200000"
                  {...register('max_salary')}
                />
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Additional Filters</CardTitle>
            <CardDescription>
              Specify companies to avoid and visa requirements
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="exclude_companies">Exclude Companies</Label>
              <Textarea
                id="exclude_companies"
                placeholder="e.g., Company A, Company B, Company C"
                {...register('exclude_companies')}
                rows={3}
              />
              <p className="text-xs text-muted-foreground">
                Jobs from these companies will be filtered out (comma-separated)
              </p>
            </div>

            <div className="flex items-center space-x-2">
              <Checkbox
                id="require_visa_sponsorship"
                {...register('require_visa_sponsorship')}
              />
              <Label
                htmlFor="require_visa_sponsorship"
                className="text-sm font-normal cursor-pointer"
              >
                Require Visa Sponsorship
              </Label>
            </div>
          </CardContent>
        </Card>

        <div className="flex justify-end gap-3">
          <Button
            type="button"
            variant="outline"
            onClick={() => router.push('/dashboard/search-profiles')}
            disabled={loading}
          >
            Cancel
          </Button>
          <Button type="submit" disabled={loading}>
            {loading ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Creating...
              </>
            ) : (
              <>
                <Save className="mr-2 h-4 w-4" />
                Create Search Profile
              </>
            )}
          </Button>
        </div>
      </form>
    </div>
  )
}
