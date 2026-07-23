'use client'

import { useEffect, useState } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Loader2, Briefcase, FileText, Send } from 'lucide-react'
import { apiClient } from '@/lib/api-client'
import type { Job, ResumeVersion } from '@/lib/types'

export default function PrepareApplicationPage() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const jobId = searchParams.get('jobId')
  const initialResumeVersionId = searchParams.get('resumeVersionId') || undefined

  const [job, setJob] = useState<Job | null>(null)
  const [resumes, setResumes] = useState<ResumeVersion[]>([])
  const [selectedResumeId, setSelectedResumeId] = useState<string | undefined>(initialResumeVersionId)
  const [loading, setLoading] = useState(true)
  const [creating, setCreating] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!jobId) return
    let cancelled = false

    const load = async () => {
      try {
        setLoading(true)
        const [jobData, resumesData] = await Promise.all([
          apiClient.getJob(jobId),
          apiClient.getResumeVersions(),
        ])
        if (cancelled) return
        setJob(jobData)
        setResumes(resumesData)
      } catch (err) {
        if (!cancelled) {
          setError('Failed to load job or resumes')
          console.error(err)
        }
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    load()
    return () => {
      cancelled = true
    }
  }, [jobId])

  const handleCreate = async () => {
    if (!jobId) return
    try {
      setCreating(true)
      setError(null)
      const application = await apiClient.createApplication(jobId, selectedResumeId)
      router.push(`/dashboard/applications/${application.id}`)
    } catch (err) {
      setError((err as Error).message || 'Failed to create application')
      console.error(err)
    } finally {
      setCreating(false)
    }
  }

  if (!jobId) {
    return (
      <Card className="max-w-lg mx-auto mt-12">
        <CardContent className="pt-6">
          <p className="text-sm text-muted-foreground">No job specified.</p>
        </CardContent>
      </Card>
    )
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-24">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    )
  }

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      <div>
        <h1 className="text-3xl font-bold">Prepare Application</h1>
        <p className="text-muted-foreground">Choose a resume and create the application draft</p>
      </div>

      {error && (
        <Card className="border-red-200 bg-red-50">
          <CardContent className="pt-6">
            <p className="text-sm text-red-800">{error}</p>
          </CardContent>
        </Card>
      )}

      {job && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Briefcase className="h-5 w-5" />
              {job.title || 'Untitled'}
            </CardTitle>
            <CardDescription>{job.company || 'Unknown company'}</CardDescription>
          </CardHeader>
        </Card>
      )}

      <Card>
        <CardHeader>
          <CardTitle>Select a Resume</CardTitle>
          <CardDescription>Optional - you can also select or tailor a resume later</CardDescription>
        </CardHeader>
        <CardContent className="space-y-2">
          {resumes.length === 0 ? (
            <p className="text-sm text-muted-foreground">No resumes uploaded yet.</p>
          ) : (
            resumes.map((resume) => (
              <button
                key={resume.id}
                onClick={() => setSelectedResumeId(resume.id)}
                className={`w-full flex items-center justify-between rounded-lg border p-3 text-left transition-colors ${
                  selectedResumeId === resume.id ? 'border-primary bg-primary/5' : 'hover:bg-muted'
                }`}
              >
                <div className="flex items-center gap-2">
                  <FileText className="h-4 w-4" />
                  <span className="text-sm font-medium">
                    {resume.family_name || (resume.parent_id ? 'Tailored Variant' : 'Base Resume')} (v{resume.version})
                  </span>
                </div>
                <Badge variant="outline" className="text-xs">
                  {resume.status}
                </Badge>
              </button>
            ))
          )}
        </CardContent>
      </Card>

      <div className="flex justify-end">
        <Button size="lg" onClick={handleCreate} disabled={creating}>
          {creating ? (
            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
          ) : (
            <Send className="mr-2 h-4 w-4" />
          )}
          Create Application
        </Button>
      </div>
    </div>
  )
}
