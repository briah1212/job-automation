'use client'

import { useEffect, useState } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Loader2, Briefcase, Send, Plus, Upload } from 'lucide-react'
import Link from 'next/link'
import { apiClient } from '@/lib/api-client'
import type { Application, Job } from '@/lib/types'

const PIPELINE_STAGES: Application['pipeline_status'][] = [
  'draft',
  'awaiting_review',
  'approved',
  'browser_running',
  'submitted',
]

export default function DashboardPage() {
  const [jobs, setJobs] = useState<Job[]>([])
  const [applications, setApplications] = useState<Application[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const load = async () => {
      try {
        setLoading(true)
        const [jobsData, applicationsData] = await Promise.all([
          apiClient.getJobs(),
          apiClient.getApplications(),
        ])
        setJobs(jobsData)
        setApplications(applicationsData)
      } catch (err) {
        console.error('Failed to load dashboard data:', err)
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [])

  const recentJobs = [...jobs]
    .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
    .slice(0, 5)

  const pendingApplications = applications.filter(
    (a) => !['confirmed', 'failed_terminal'].includes(a.pipeline_status)
  ).length
  const needsReviewCount = applications.filter((a) => a.pipeline_status === 'awaiting_review').length

  const pipelineCounts = PIPELINE_STAGES.reduce<Record<string, number>>((acc, stage) => {
    acc[stage] = applications.filter((a) => a.pipeline_status === stage).length
    return acc
  }, {})

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
        <h1 className="text-3xl font-bold">Dashboard</h1>
        <div className="flex gap-2">
          <Button asChild>
            <Link href="/dashboard/jobs">
              <Plus className="mr-2 h-4 w-4" />
              Import Job
            </Link>
          </Button>
          <Button variant="outline" asChild>
            <Link href="/dashboard/profile">
              <Upload className="mr-2 h-4 w-4" />
              Update Profile
            </Link>
          </Button>
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Jobs Discovered</CardTitle>
            <Briefcase className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{jobs.length}</div>
            <p className="text-xs text-muted-foreground">Total imported</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Applications In Progress</CardTitle>
            <Send className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{pendingApplications}</div>
            <p className="text-xs text-muted-foreground">{needsReviewCount} need review</p>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Recent Jobs</CardTitle>
          <CardDescription>Most recently imported opportunities</CardDescription>
        </CardHeader>
        <CardContent>
          {recentJobs.length === 0 ? (
            <p className="text-sm text-muted-foreground py-4">
              No jobs yet.{' '}
              <Link href="/dashboard/jobs" className="underline">
                Import your first one
              </Link>
              .
            </p>
          ) : (
            <div className="space-y-4">
              {recentJobs.map((job, idx) => (
                <div
                  key={job.id}
                  className={`flex items-center justify-between ${idx < recentJobs.length - 1 ? 'border-b pb-4' : ''}`}
                >
                  <div>
                    <div className="font-medium">{job.title || 'Untitled'}</div>
                    <div className="text-sm text-muted-foreground">
                      {job.company || 'Unknown company'} {job.location ? `• ${job.location}` : ''}
                    </div>
                  </div>
                  <div className="flex items-center gap-4">
                    <div className="text-right">
                      {job.score != null && (
                        <div className="text-sm font-medium text-green-600">{job.score}% Match</div>
                      )}
                      <div className="text-xs text-muted-foreground">
                        {new Date(job.created_at).toLocaleDateString()}
                      </div>
                    </div>
                    <Button size="sm" asChild>
                      <Link href={`/dashboard/jobs/${job.id}`}>View</Link>
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Application Pipeline</CardTitle>
          <CardDescription>Current status of your applications</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-5 gap-4">
            {PIPELINE_STAGES.map((stage) => (
              <div key={stage} className="text-center">
                <div className="text-2xl font-bold">{pipelineCounts[stage] || 0}</div>
                <div className="text-xs text-muted-foreground capitalize">{stage.replace(/_/g, ' ')}</div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
