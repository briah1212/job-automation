'use client'

import { useState } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { useForm } from 'react-hook-form'
import { Save } from 'lucide-react'

interface ProfileForm {
  legal_name: string
  preferred_name?: string
  email: string
  phone?: string
  linkedin?: string
  github?: string
  target_seniority: string
  work_authorization: string
}

export default function ProfilePage() {
  const [loading, setLoading] = useState(false)
  const { register, handleSubmit, formState: { errors } } = useForm<ProfileForm>()

  const onSubmit = async (data: ProfileForm) => {
    setLoading(true)
    try {
      // TODO: Call API
      console.log('Saving profile:', data)
      alert('Profile saved!')
    } catch (error) {
      console.error(error)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-bold">Profile</h1>
      </div>

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
          </CardContent>
        </Card>

        <div className="flex justify-end">
          <Button type="submit" disabled={loading}>
            <Save className="mr-2 h-4 w-4" />
            {loading ? 'Saving...' : 'Save Profile'}
          </Button>
        </div>
      </form>
    </div>
  )
}
