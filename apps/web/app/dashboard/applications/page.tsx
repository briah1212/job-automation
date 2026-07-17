'use client'

import { useState, useEffect } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import Link from 'next/link'
import { AlertTriangle, CheckCircle, Loader2, FileText } from 'lucide-react'
import { apiClient } from '@/lib/api-client'
import type { Application, Job } from '@/lib/types'

const STATUS_COLUMNS: Application['status'][] = [
  'preparing',
  'needs_review',
  'ready',
  'applied',
  'interview',
]

function riskBadgeVariant(risk?: 'low' | 'medium' | 'high') {
  if (risk === 'high') return 'destructive' as const
  if (risk === 'medium') return 'secondary' as const
  return 'outline' as const
}

export default function ApplicationsPage() {
  const [applications, setApplications] = useState<Application[]>([])
  const [jobsById, setJobsById] = useState<Record<string, Job>>({})
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const fetchData = async () => {
      try {
        setLoading(true)
        setError(null)
        const apps = await apiClient.getApplications()
        setApplications(apps)

        try {
          const jobs = await apiClient.getJobs()
          const map: Record<string, Job> = {}
          jobs.forEach((job) => {
            map[job.id] = job
          })
          setJobsById(map)
        } catch (err) {
          console.error('Failed to load jobs for applications list:', err)
        }
      } catch (err) {
        setError('Failed to load applications')
        console.error(err)
      } finally {
        setLoading(false)
      }
    }

    fetchData()
  }, [])

  const groupedByStatus = STATUS_COLUMNS.reduce<Record<string, Application[]>>((acc, status) => {
    acc[status] = applications.filter((a) => a.status === status)
    return acc
  }, {})

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <div className="flex flex-col items-center gap-4">
          <Loader2 className="h-8 w-8 animate-spin text-primary" />
          <p className="text-muted-foreground">Loading applications...</p>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="space-y-6">
        <h1 className="text-3xl font-bold">Applications</h1>
        <Card className="border-red-200 bg-red-50">
          <CardContent className="pt-6">
            <p className="text-red-800 text-sm">{error}</p>
          </CardContent>
        </Card>
      </div>
    )
  }

  if (applications.length === 0) {
    return (
      <div className="space-y-6">
        <h1 className="text-3xl font-bold">Applications</h1>
        <Card>
          <CardContent className="flex flex-col items-center justify-center gap-3 py-16 text-center">
            <FileText className="h-10 w-10 text-muted-foreground" />
            <CardTitle className="text-xl">No applications yet</CardTitle>
            <CardDescription>
              Once you apply to a job, it will show up here so you can track its progress.
            </CardDescription>
            <Button asChild className="mt-2">
              <Link href="/dashboard/jobs">Browse Jobs</Link>
            </Button>
          </CardContent>
        </Card>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-bold">Applications</h1>
      </div>

      <Tabs defaultValue="kanban">
        <TabsList>
          <TabsTrigger value="kanban">Kanban View</TabsTrigger>
          <TabsTrigger value="table">Table View</TabsTrigger>
        </TabsList>

        <TabsContent value="kanban" className="mt-6">
          <div className="grid gap-4 md:grid-cols-5">
            {STATUS_COLUMNS.map((status) => {
              const apps = groupedByStatus[status] || []
              return (
                <div key={status}>
                  <div className="mb-4">
                    <h3 className="font-medium capitalize">{status.replace('_', ' ')}</h3>
                    <p className="text-sm text-muted-foreground">{apps.length} applications</p>
                  </div>
                  <div className="space-y-3">
                    {apps.map((app) => {
                      const job = app.job ?? jobsById[app.job_id]
                      return (
                        <Card key={app.id} className="hover:border-primary transition-colors">
                          <CardHeader className="p-4">
                            <div className="flex items-start justify-between">
                              <div>
                                <CardTitle className="text-sm">
                                  {job?.company ?? 'Unknown Company'}
                                </CardTitle>
                                <CardDescription className="text-xs">
                                  {job?.title ?? 'Unknown Role'}
                                </CardDescription>
                              </div>
                              {app.risk_level && (
                                <Badge variant={riskBadgeVariant(app.risk_level)} className="text-xs">
                                  {app.risk_level === 'high' && (
                                    <AlertTriangle className="mr-1 h-3 w-3" />
                                  )}
                                  {app.risk_level === 'low' && (
                                    <CheckCircle className="mr-1 h-3 w-3" />
                                  )}
                                  {app.risk_level}
                                </Badge>
                              )}
                            </div>
                          </CardHeader>
                          <CardContent className="p-4 pt-0">
                            <Button asChild variant="outline" size="sm" className="w-full">
                              <Link href={`/dashboard/applications/${app.id}`}>View</Link>
                            </Button>
                          </CardContent>
                        </Card>
                      )
                    })}
                  </div>
                </div>
              )
            })}
          </div>
        </TabsContent>

        <TabsContent value="table" className="mt-6">
          <Card>
            <CardContent className="p-6">
              <p className="text-center text-muted-foreground">Table view coming soon</p>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  )
}
