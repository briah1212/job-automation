'use client'

import { useState, useEffect } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Briefcase, FileText, Loader2, Sparkles } from 'lucide-react'
import { QuestionList } from '@/components/applications/question-list'
import { ReviewFindings } from '@/components/applications/review-findings'
import { CoverLetterCard } from '@/components/applications/cover-letter-card'
import { BrowserAutomationPanel } from '@/components/applications/browser-automation-panel'
import { apiClient } from '@/lib/api-client'
import type {
  Application,
  Job,
  ApplicationQuestionWithAnswer,
  ApplicationReviewResult,
  ResumeVersion,
} from '@/lib/types'

export default function ApplicationDetailPage({ params }: { params: { id: string } }) {
  const [application, setApplication] = useState<Application | null>(null)
  const [job, setJob] = useState<Job | null>(null)
  const [questions, setQuestions] = useState<ApplicationQuestionWithAnswer[]>([])
  const [review, setReview] = useState<ApplicationReviewResult | null>(null)
  const [resumes, setResumes] = useState<ResumeVersion[]>([])

  const [loadingApplication, setLoadingApplication] = useState(true)
  const [loadingQuestions, setLoadingQuestions] = useState(true)
  const [loadingReview, setLoadingReview] = useState(true)
  const [loadingResumes, setLoadingResumes] = useState(true)

  const [generatingQuestions, setGeneratingQuestions] = useState(false)
  const [runningReview, setRunningReview] = useState(false)

  const [error, setError] = useState<string | null>(null)

  // Fetch base application (and nested/linked job)
  useEffect(() => {
    // Guards against applications/A -> applications/B navigation reusing
    // this component instance - a slow response for A landing after a fast
    // response for B would otherwise silently overwrite B's data with A's.
    let cancelled = false
    setApplication(null)
    setJob(null)

    const fetchApplication = async () => {
      try {
        setLoadingApplication(true)
        const data = await apiClient.getApplication(params.id)
        if (cancelled) return
        setApplication(data)
        if (data.job) {
          setJob(data.job)
        } else if (data.job_id) {
          try {
            const jobData = await apiClient.getJob(data.job_id)
            if (!cancelled) setJob(jobData)
          } catch (err) {
            console.error('Failed to load job for application:', err)
          }
        }
      } catch (err) {
        if (!cancelled) {
          setError('Failed to load application details')
          console.error(err)
        }
      } finally {
        if (!cancelled) setLoadingApplication(false)
      }
    }

    fetchApplication()
    return () => {
      cancelled = true
    }
  }, [params.id])

  // Fetch application questions (may not exist yet - not treated as an error)
  useEffect(() => {
    let cancelled = false

    const fetchQuestions = async () => {
      try {
        setLoadingQuestions(true)
        const data = await apiClient.getApplicationQuestions(params.id)
        if (!cancelled) setQuestions(data)
      } catch (err) {
        console.error('No application questions available yet:', err)
        if (!cancelled) setQuestions([])
      } finally {
        if (!cancelled) setLoadingQuestions(false)
      }
    }

    fetchQuestions()
    return () => {
      cancelled = true
    }
  }, [params.id])

  // Fetch existing review result (may not exist yet - not treated as an error)
  useEffect(() => {
    let cancelled = false

    const fetchReview = async () => {
      try {
        setLoadingReview(true)
        const data = await apiClient.getReviewResult(params.id)
        if (!cancelled) setReview(data)
      } catch (err) {
        console.error('No review result available yet:', err)
        if (!cancelled) setReview(null)
      } finally {
        if (!cancelled) setLoadingReview(false)
      }
    }

    fetchReview()
    return () => {
      cancelled = true
    }
  }, [params.id])

  // Fetch resume versions to resolve the selected resume by id
  useEffect(() => {
    const fetchResumes = async () => {
      try {
        setLoadingResumes(true)
        const data = await apiClient.getResumeVersions()
        setResumes(data)
      } catch (err) {
        console.error('Failed to load resume versions:', err)
      } finally {
        setLoadingResumes(false)
      }
    }

    fetchResumes()
  }, [])

  const handleGenerateQuestions = async () => {
    try {
      setGeneratingQuestions(true)
      setError(null)
      const data = await apiClient.generateApplicationQA(params.id)
      setQuestions(data)
    } catch (err) {
      setError((err as Error).message || 'Failed to generate application questions')
      console.error(err)
    } finally {
      setGeneratingQuestions(false)
    }
  }

  const handleAnswerUpdate = (questionId: string, newText: string) => {
    setQuestions((prev) =>
      prev.map((q) =>
        q.id === questionId
          ? {
              ...q,
              answer: {
                ...(q.answer ?? { source: 'user_input', approved: false, answer_text: newText }),
                answer_text: newText,
                source: 'user_input',
              },
            }
          : q
      )
    )
  }

  const handleRunReview = async () => {
    try {
      setRunningReview(true)
      setError(null)
      const data = await apiClient.autoReviewApplication(params.id)
      setReview(data)
    } catch (err) {
      setError((err as Error).message || 'Failed to run application review')
      console.error(err)
    } finally {
      setRunningReview(false)
    }
  }

  const selectedResume = application?.resume_version_id
    ? resumes.find((r) => r.id === application.resume_version_id)
    : undefined

  if (loadingApplication) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="flex flex-col items-center gap-4">
          <Loader2 className="h-8 w-8 animate-spin text-primary" />
          <p className="text-muted-foreground">Loading application...</p>
        </div>
      </div>
    )
  }

  if (error && !application) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <Card className="w-full max-w-md">
          <CardHeader>
            <CardTitle className="text-red-600">Error</CardTitle>
          </CardHeader>
          <CardContent>
            <p>{error}</p>
          </CardContent>
        </Card>
      </div>
    )
  }

  if (!application) {
    return null
  }

  return (
    <div className="space-y-6 pb-8">
      {error && (
        <Card className="border-red-200 bg-red-50">
          <CardContent className="pt-6">
            <p className="text-red-800 text-sm">{error}</p>
          </CardContent>
        </Card>
      )}

      <div>
        <h1 className="text-3xl font-bold">Application Review</h1>
        <p className="text-muted-foreground">
          {job ? `${job.company} - ${job.title}` : 'Loading job details...'}
        </p>
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="lg:col-span-2 space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Job Details</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              {job ? (
                <>
                  <div className="flex items-center gap-2 flex-wrap">
                    <Briefcase className="h-4 w-4 text-muted-foreground shrink-0" />
                    <span className="font-medium">{job.company}</span>
                    <span className="text-muted-foreground">•</span>
                    <span>{job.title}</span>
                  </div>
                  <div className="flex gap-2">
                    {job.match_score != null && <Badge>{job.match_score}% Match</Badge>}
                    {job.location && <Badge variant="outline">{job.location}</Badge>}
                  </div>
                </>
              ) : (
                <p className="text-sm text-muted-foreground">Job details unavailable</p>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Application Questions</CardTitle>
              <CardDescription>Answers sourced from your approved responses and profile</CardDescription>
            </CardHeader>
            <CardContent>
              {loadingQuestions ? (
                <div className="flex items-center justify-center py-8">
                  <Loader2 className="h-6 w-6 animate-spin text-primary" />
                </div>
              ) : questions.length > 0 ? (
                <QuestionList
                  applicationId={params.id}
                  questions={questions}
                  onAnswerUpdate={handleAnswerUpdate}
                />
              ) : (
                <div className="text-center py-8 space-y-4">
                  <p className="text-sm text-muted-foreground">
                    No application questions have been generated yet.
                  </p>
                  <Button onClick={handleGenerateQuestions} disabled={generatingQuestions}>
                    {generatingQuestions ? (
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    ) : (
                      <Sparkles className="mr-2 h-4 w-4" />
                    )}
                    Generate Application Questions
                  </Button>
                </div>
              )}
            </CardContent>
          </Card>

          <CoverLetterCard applicationId={application.id} />
        </div>

        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Status</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <Badge variant="secondary" className="w-full justify-center py-2 capitalize">
                {application.status.replace(/_/g, ' ')}
              </Badge>
              <div className="text-sm text-muted-foreground">
                Pipeline status: {application.pipeline_status}
              </div>
            </CardContent>
          </Card>

          {loadingReview ? (
            <Card>
              <CardContent className="pt-6 flex items-center justify-center py-8">
                <Loader2 className="h-6 w-6 animate-spin text-primary" />
              </CardContent>
            </Card>
          ) : (
            <ReviewFindings review={review} onRunReview={handleRunReview} running={runningReview} />
          )}

          <BrowserAutomationPanel applicationId={params.id} />

          <Card>
            <CardHeader>
              <CardTitle>Selected Resume</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              {loadingResumes ? (
                <div className="flex items-center justify-center py-4">
                  <Loader2 className="h-5 w-5 animate-spin text-primary" />
                </div>
              ) : selectedResume ? (
                <>
                  <div className="flex items-center gap-2">
                    <FileText className="h-4 w-4" />
                    <span className="text-sm font-medium">
                      {selectedResume.parent_id ? 'Tailored Variant' : 'Base Resume'} (v{selectedResume.version})
                    </span>
                  </div>
                  <Badge variant="outline" className="text-xs">
                    {selectedResume.status}
                  </Badge>
                  <Button variant="outline" size="sm" className="w-full" asChild>
                    <a href={`/dashboard/resumes/${selectedResume.family_id}`}>View Resume</a>
                  </Button>
                </>
              ) : (
                <p className="text-sm text-muted-foreground">No resume selected yet</p>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  )
}
