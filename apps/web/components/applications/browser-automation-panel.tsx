'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Textarea } from '@/components/ui/textarea'
import {
  AlertTriangle,
  Bot,
  CheckCircle2,
  ExternalLink,
  Loader2,
  Play,
  Send,
  ShieldAlert,
  Square,
  XCircle,
} from 'lucide-react'
import { apiClient } from '@/lib/api-client'
import type { BrowserStatus } from '@/lib/types'

interface BrowserAutomationPanelProps {
  applicationId: string
}

const POLL_INTERVAL_MS = 3000

const IN_PROGRESS_STATUSES = new Set(['pending', 'running'])

const STEP_LABELS: Record<string, string> = {
  queued: 'Queued - waiting for the browser worker to pick this up',
  approved_for_submit: 'Submission approved - proceeding to submit',
  manual_intervention_resumed: 'Resuming after manual intervention',
  question_answered: 'Answer recorded - resuming',
}

export function BrowserAutomationPanel({ applicationId }: BrowserAutomationPanelProps) {
  const [status, setStatus] = useState<BrowserStatus | null>(null)
  const [loading, setLoading] = useState(true)
  const [starting, setStarting] = useState(false)
  const [acting, setActing] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [answerText, setAnswerText] = useState('')
  const [replayLoading, setReplayLoading] = useState(false)
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const fetchStatus = useCallback(async () => {
    try {
      const data = await apiClient.getBrowserStatus(applicationId)
      setStatus(data)
      return data
    } catch (err) {
      const httpStatus = (err as { status?: number } | undefined)?.status
      if (httpStatus === 404) {
        setStatus(null)
      } else {
        console.error('Failed to load browser status:', err)
      }
      return null
    }
  }, [applicationId])

  useEffect(() => {
    setLoading(true)
    fetchStatus().finally(() => setLoading(false))
  }, [fetchStatus])

  useEffect(() => {
    if (pollRef.current) {
      clearInterval(pollRef.current)
      pollRef.current = null
    }
    if (status && IN_PROGRESS_STATUSES.has(status.status)) {
      pollRef.current = setInterval(() => {
        fetchStatus()
      }, POLL_INTERVAL_MS)
    }
    return () => {
      if (pollRef.current) clearInterval(pollRef.current)
    }
  }, [status, fetchStatus])

  const handleStart = async () => {
    try {
      setStarting(true)
      setError(null)
      await apiClient.startBrowserAutomation(applicationId)
      await fetchStatus()
    } catch (err) {
      setError((err as Error).message || 'Failed to start browser submission')
      console.error(err)
    } finally {
      setStarting(false)
    }
  }

  const handleCancel = async () => {
    try {
      setActing(true)
      setError(null)
      await apiClient.cancelBrowserAutomation(applicationId)
      await fetchStatus()
    } catch (err) {
      setError((err as Error).message || 'Failed to cancel browser submission')
      console.error(err)
    } finally {
      setActing(false)
    }
  }

  const handleApproveSubmit = async () => {
    try {
      setActing(true)
      setError(null)
      await apiClient.approveSubmit(applicationId)
      await fetchStatus()
    } catch (err) {
      setError((err as Error).message || 'Failed to approve submission')
      console.error(err)
    } finally {
      setActing(false)
    }
  }

  const handleResumeManualIntervention = async () => {
    try {
      setActing(true)
      setError(null)
      await apiClient.resumeManualIntervention(applicationId)
      await fetchStatus()
    } catch (err) {
      setError((err as Error).message || 'Failed to resume')
      console.error(err)
    } finally {
      setActing(false)
    }
  }

  const handleAnswerQuestion = async () => {
    if (!answerText.trim()) return
    try {
      setActing(true)
      setError(null)
      await apiClient.answerPendingQuestion(applicationId, answerText.trim())
      setAnswerText('')
      await fetchStatus()
    } catch (err) {
      setError((err as Error).message || 'Failed to submit answer')
      console.error(err)
    } finally {
      setActing(false)
    }
  }

  const handleViewReplay = async () => {
    try {
      setReplayLoading(true)
      setError(null)
      const blobUrl = await apiClient.getReplayReportUrl(applicationId)
      window.open(blobUrl, '_blank', 'noopener,noreferrer')
    } catch (err) {
      setError('No replay report available yet')
      console.error(err)
    } finally {
      setReplayLoading(false)
    }
  }

  if (loading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Bot className="h-5 w-5" />
            Browser Submission
          </CardTitle>
        </CardHeader>
        <CardContent className="flex items-center justify-center py-8">
          <Loader2 className="h-6 w-6 animate-spin text-primary" />
        </CardContent>
      </Card>
    )
  }

  // No task has ever been started for this application yet.
  if (!status) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Bot className="h-5 w-5" />
            Browser Submission
          </CardTitle>
          <CardDescription>
            Automatically fill out this application on the ATS site. You&apos;ll approve the final submission before anything is sent.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {error && <p className="text-sm text-red-600">{error}</p>}
          <Button onClick={handleStart} disabled={starting}>
            {starting ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            ) : (
              <Play className="mr-2 h-4 w-4" />
            )}
            Start Browser Submission
          </Button>
        </CardContent>
      </Card>
    )
  }

  const step = status.task_metadata?.step
  const pendingQuestion = status.task_metadata?.pending_question

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between gap-2">
          <CardTitle className="flex items-center gap-2">
            <Bot className="h-5 w-5" />
            Browser Submission
          </CardTitle>
          <Badge variant="outline" className="capitalize">
            {status.status.replace(/_/g, ' ')}
          </Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {error && <p className="text-sm text-red-600">{error}</p>}

        {status.status === 'pending' || status.status === 'running' ? (
          <div className="flex items-center gap-3 py-2">
            <Loader2 className="h-5 w-5 animate-spin text-primary" />
            <span className="text-sm text-muted-foreground">
              {(step && STEP_LABELS[step]) || 'The browser worker is filling out this application...'}
            </span>
          </div>
        ) : null}

        {status.status === 'waiting_user_input' && step === 'paused_question' && pendingQuestion && (
          <div className="space-y-3 rounded-lg border border-amber-200 bg-amber-50 p-4">
            <div className="flex items-center gap-2 text-amber-800">
              <AlertTriangle className="h-4 w-4" />
              <span className="text-sm font-semibold">The site asked a question we don&apos;t have an answer for</span>
            </div>
            <p className="text-sm font-medium">{pendingQuestion.label}</p>
            <Textarea
              value={answerText}
              onChange={(e) => setAnswerText(e.target.value)}
              placeholder="Type your answer..."
              rows={3}
            />
            <p className="text-xs text-muted-foreground">
              This answer will be saved and reused automatically for similar questions in the future.
            </p>
            <Button size="sm" onClick={handleAnswerQuestion} disabled={acting || !answerText.trim()}>
              {acting ? (
                <Loader2 className="mr-2 h-3 w-3 animate-spin" />
              ) : (
                <Send className="mr-2 h-3 w-3" />
              )}
              Submit Answer & Resume
            </Button>
          </div>
        )}

        {status.status === 'waiting_user_input' && step === 'manual_intervention' && (
          <div className="space-y-3 rounded-lg border border-red-200 bg-red-50 p-4">
            <div className="flex items-center gap-2 text-red-800">
              <ShieldAlert className="h-4 w-4" />
              <span className="text-sm font-semibold">Manual intervention needed</span>
            </div>
            <p className="text-sm text-red-800">
              {status.error ||
                'The worker could not proceed automatically (this can happen for a CAPTCHA, MFA prompt, email verification, login failure, or missing document). Handle it directly on the ATS site, then resume.'}
            </p>
            <Button size="sm" onClick={handleResumeManualIntervention} disabled={acting}>
              {acting ? (
                <Loader2 className="mr-2 h-3 w-3 animate-spin" />
              ) : (
                <Play className="mr-2 h-3 w-3" />
              )}
              I&apos;ve Handled It - Resume
            </Button>
          </div>
        )}

        {status.status === 'waiting_user_input' && step === 'awaiting_approval' && (
          <div className="space-y-3 rounded-lg border border-blue-200 bg-blue-50 p-4">
            <div className="flex items-center gap-2 text-blue-800">
              <CheckCircle2 className="h-4 w-4" />
              <span className="text-sm font-semibold">Ready to submit</span>
            </div>
            <p className="text-sm text-blue-800">
              The application has been filled out. Review the replay report, then approve to have the worker click submit.
            </p>
            <div className="flex flex-wrap gap-2">
              <Button size="sm" variant="outline" onClick={handleViewReplay} disabled={replayLoading}>
                {replayLoading ? (
                  <Loader2 className="mr-2 h-3 w-3 animate-spin" />
                ) : (
                  <ExternalLink className="mr-2 h-3 w-3" />
                )}
                View Replay Report
              </Button>
              <Button size="sm" onClick={handleApproveSubmit} disabled={acting}>
                {acting ? (
                  <Loader2 className="mr-2 h-3 w-3 animate-spin" />
                ) : (
                  <CheckCircle2 className="mr-2 h-3 w-3" />
                )}
                Approve & Submit
              </Button>
            </div>
          </div>
        )}

        {status.status === 'completed' && (
          <div className="flex items-center gap-2 rounded-lg border border-green-200 bg-green-50 p-4 text-green-800">
            <CheckCircle2 className="h-5 w-5" />
            <span className="text-sm font-medium">Application submitted successfully</span>
          </div>
        )}

        {status.status === 'failed' && (
          <div className="space-y-3 rounded-lg border border-red-200 bg-red-50 p-4">
            <div className="flex items-center gap-2 text-red-800">
              <XCircle className="h-4 w-4" />
              <span className="text-sm font-semibold">Submission failed</span>
            </div>
            {status.error && <p className="text-sm text-red-800">{status.error}</p>}
            <Button size="sm" onClick={handleStart} disabled={starting}>
              {starting ? (
                <Loader2 className="mr-2 h-3 w-3 animate-spin" />
              ) : (
                <Play className="mr-2 h-3 w-3" />
              )}
              Retry
            </Button>
          </div>
        )}

        {status.status === 'cancelled' && (
          <div className="space-y-3 rounded-lg border bg-muted p-4">
            <span className="text-sm text-muted-foreground">This submission was cancelled.</span>
            <div>
              <Button size="sm" onClick={handleStart} disabled={starting}>
                {starting ? (
                  <Loader2 className="mr-2 h-3 w-3 animate-spin" />
                ) : (
                  <Play className="mr-2 h-3 w-3" />
                )}
                Start Again
              </Button>
            </div>
          </div>
        )}

        <div className="flex flex-wrap gap-2 border-t pt-3">
          {status.status !== 'completed' && status.status !== 'cancelled' && status.status !== 'failed' && (
            <Button size="sm" variant="outline" onClick={handleCancel} disabled={acting}>
              <Square className="mr-2 h-3 w-3" />
              Cancel
            </Button>
          )}
          {status.status !== 'waiting_user_input' && (
            <Button size="sm" variant="ghost" onClick={handleViewReplay} disabled={replayLoading}>
              {replayLoading ? (
                <Loader2 className="mr-2 h-3 w-3 animate-spin" />
              ) : (
                <ExternalLink className="mr-2 h-3 w-3" />
              )}
              View Replay Report
            </Button>
          )}
        </div>
      </CardContent>
    </Card>
  )
}
