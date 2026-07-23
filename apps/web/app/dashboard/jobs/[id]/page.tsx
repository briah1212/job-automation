'use client'

import { useState, useEffect } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { ExternalLink, Send, MapPin, DollarSign, Briefcase, ChevronDown, ChevronUp, RefreshCw, Loader2, Sparkles } from 'lucide-react'
import { MatchAnalysis } from '@/components/jobs/match-analysis'
import { ResumeRecommendation } from '@/components/jobs/resume-recommendation'
import { apiClient } from '@/lib/api-client'
import type { Job, JobMatchScore, ResumeSelectionResult, ResumeVersion } from '@/lib/types'
import { useRouter } from 'next/navigation'

export default function JobDetailPage({ params }: { params: { id: string } }) {
  const router = useRouter()
  
  // State management
  const [job, setJob] = useState<Job | null>(null)
  const [matchScore, setMatchScore] = useState<JobMatchScore | null>(null)
  const [resumeSelection, setResumeSelection] = useState<ResumeSelectionResult | null>(null)
  const [resumes, setResumes] = useState<ResumeVersion[]>([])
  
  const [loadingJob, setLoadingJob] = useState(true)
  const [loadingMatch, setLoadingMatch] = useState(true)
  const [loadingResumes, setLoadingResumes] = useState(true)
  const [recalculating, setRecalculating] = useState(false)
  const [selectingResume, setSelectingResume] = useState(false)

  const [error, setError] = useState<string | null>(null)
  const [descriptionExpanded, setDescriptionExpanded] = useState(true)

  // Fetch job details
  useEffect(() => {
    const fetchJob = async () => {
      try {
        setLoadingJob(true)
        const jobData = await apiClient.getJob(params.id)
        setJob(jobData)
      } catch (err) {
        setError('Failed to load job details')
        console.error(err)
      } finally {
        setLoadingJob(false)
      }
    }

    fetchJob()
  }, [params.id])

  // Fetch match score
  useEffect(() => {
    const fetchMatchScore = async () => {
      try {
        setLoadingMatch(true)
        const matchData = await apiClient.getMatchScore(params.id)
        setMatchScore(matchData)
      } catch (err) {
        console.error('Failed to load match score:', err)
        // Don't set error, match score might not exist yet
      } finally {
        setLoadingMatch(false)
      }
    }

    fetchMatchScore()
  }, [params.id])

  // Fetch resume versions (resume selection is computed on demand, not persisted for retrieval)
  useEffect(() => {
    const fetchResumes = async () => {
      try {
        setLoadingResumes(true)
        const resumesData = await apiClient.getResumeVersions()
        setResumes(resumesData)
      } catch (err) {
        console.error('Failed to load resumes:', err)
      } finally {
        setLoadingResumes(false)
      }
    }

    fetchResumes()
  }, [params.id])

  const handleSelectResume = async () => {
    try {
      setSelectingResume(true)
      setError(null)
      const selection = await apiClient.selectResume(params.id)
      setResumeSelection(selection)
    } catch (err) {
      setError('Failed to select a resume for this job')
      console.error(err)
    } finally {
      setSelectingResume(false)
    }
  }

  // Action handlers
  const handleRecalculateMatch = async () => {
    try {
      setRecalculating(true)
      setError(null)
      const newMatchScore = await apiClient.calculateMatchScore(params.id)
      setMatchScore(newMatchScore)
    } catch (err) {
      setError('Failed to recalculate match score')
      console.error(err)
    } finally {
      setRecalculating(false)
    }
  }

  const handlePrepareApplication = () => {
    const resumeParam = resumeSelection?.recommended_resume_id
      ? `&resumeVersionId=${resumeSelection.recommended_resume_id}`
      : ''
    router.push(`/dashboard/applications/prepare?jobId=${params.id}${resumeParam}`)
  }

  const handleViewResume = (resumeId: string) => {
    router.push(`/dashboard/resumes/${resumeId}`)
  }

  // Loading state
  if (loadingJob) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="flex flex-col items-center gap-4">
          <Loader2 className="h-8 w-8 animate-spin text-primary" />
          <p className="text-muted-foreground">Loading job details...</p>
        </div>
      </div>
    )
  }

  // Error state
  if (error && !job) {
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

  if (!job) {
    return null
  }

  return (
    <div className="space-y-6 pb-8">
      {/* Error banner */}
      {error && (
        <Card className="border-red-200 bg-red-50">
          <CardContent className="pt-6">
            <p className="text-red-800 text-sm">{error}</p>
          </CardContent>
        </Card>
      )}

      {/* Header Section */}
      <div className="flex items-start justify-between">
        <div className="flex-1">
          <h1 className="text-3xl font-bold">
            {job.title || (job.status === 'extracting' ? 'Extracting job details...' : 'Untitled')}
          </h1>
          <div className="flex items-center gap-4 mt-2 text-muted-foreground flex-wrap">
            <div className="flex items-center gap-1">
              <Briefcase className="h-4 w-4 shrink-0" />
              {job.company || 'Unknown company'}
            </div>
            {job.location && (
              <div className="flex items-center gap-1">
                <MapPin className="h-4 w-4 shrink-0" />
                {job.location}
              </div>
            )}
            {job.salary_min && job.salary_max && (
              <div className="flex items-center gap-1">
                <DollarSign className="h-4 w-4 shrink-0" />
                ${(job.salary_min / 1000).toFixed(0)}k - ${(job.salary_max / 1000).toFixed(0)}k
              </div>
            )}
          </div>
        </div>

        {/* Primary Actions */}
        {typeof job.extracted_data?.url === 'string' && (
          <div className="flex gap-2">
            <Button variant="outline" asChild>
              <a href={job.extracted_data.url} target="_blank" rel="noopener noreferrer">
                <ExternalLink className="mr-2 h-4 w-4" />
                View Original
              </a>
            </Button>
          </div>
        )}
      </div>

      {/* Enhanced Action Buttons Row */}
      <div className="flex gap-3 flex-wrap">
        <Button
          variant="outline"
          onClick={handleRecalculateMatch}
          disabled={recalculating}
        >
          {recalculating ? (
            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
          ) : (
            <RefreshCw className="mr-2 h-4 w-4" />
          )}
          Re-calculate Match
        </Button>

        <div className="flex-1" />
        
        <Button
          size="lg"
          onClick={handlePrepareApplication}
          className="bg-primary hover:bg-primary/90 shadow-md"
        >
          <Send className="mr-2 h-5 w-5" />
          Prepare Application
        </Button>
      </div>

      {/* Main Content Grid */}
      <div className="grid gap-6 lg:grid-cols-3">
        {/* Left Column - Job Description and Match Analysis */}
        <div className="lg:col-span-2 space-y-6">
          {/* Original Job Description - Collapsible */}
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <CardTitle>Original Job Description</CardTitle>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setDescriptionExpanded(!descriptionExpanded)}
                >
                  {descriptionExpanded ? (
                    <ChevronUp className="h-4 w-4" />
                  ) : (
                    <ChevronDown className="h-4 w-4" />
                  )}
                </Button>
              </div>
            </CardHeader>
            {descriptionExpanded && (
              <CardContent>
                {job.description ? (
                  <p className="text-sm text-muted-foreground whitespace-pre-wrap">{job.description}</p>
                ) : (
                  <p className="text-sm text-muted-foreground">
                    {job.status === 'extracting'
                      ? 'Still extracting the job description...'
                      : 'No description available for this job.'}
                  </p>
                )}
              </CardContent>
            )}
          </Card>

          {/* Match Analysis Section */}
          {loadingMatch ? (
            <Card>
              <CardContent className="pt-6">
                <div className="flex items-center justify-center py-8">
                  <div className="flex flex-col items-center gap-4">
                    <Loader2 className="h-8 w-8 animate-spin text-primary" />
                    <p className="text-sm text-muted-foreground">Loading match analysis...</p>
                  </div>
                </div>
              </CardContent>
            </Card>
          ) : matchScore ? (
            <MatchAnalysis matchScore={matchScore} />
          ) : (
            <Card>
              <CardHeader>
                <CardTitle>Match Analysis</CardTitle>
                <CardDescription>No match score calculated yet</CardDescription>
              </CardHeader>
              <CardContent>
                <Button onClick={handleRecalculateMatch} disabled={recalculating}>
                  {recalculating ? (
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  ) : (
                    <RefreshCw className="mr-2 h-4 w-4" />
                  )}
                  Calculate Match Score
                </Button>
              </CardContent>
            </Card>
          )}
        </div>

        {/* Right Column - Resume Recommendation */}
        <div className="space-y-6">
          {loadingResumes ? (
            <Card>
              <CardContent className="pt-6">
                <div className="flex items-center justify-center py-8">
                  <div className="flex flex-col items-center gap-4">
                    <Loader2 className="h-8 w-8 animate-spin text-primary" />
                    <p className="text-sm text-muted-foreground">Loading resume data...</p>
                  </div>
                </div>
              </CardContent>
            </Card>
          ) : resumeSelection && resumes.length > 0 ? (
            <ResumeRecommendation
              selection={resumeSelection}
              resumes={resumes}
              onViewResume={handleViewResume}
              onPrepareApplication={handlePrepareApplication}
            />
          ) : (
            <Card>
              <CardHeader>
                <CardTitle>Resume Recommendation</CardTitle>
                <CardDescription>No resume selected yet</CardDescription>
              </CardHeader>
              <CardContent className="space-y-3">
                <p className="text-sm text-muted-foreground">
                  {resumes.length === 0
                    ? 'Upload a resume first, then select the best match for this job.'
                    : 'Pick the best resume on file for this job.'}
                </p>
                <Button onClick={handleSelectResume} disabled={selectingResume || resumes.length === 0}>
                  {selectingResume ? (
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  ) : (
                    <Sparkles className="mr-2 h-4 w-4" />
                  )}
                  Select Best Resume
                </Button>
                {resumes.length > 0 && (
                  <div>
                    <Button variant="ghost" size="sm" onClick={handlePrepareApplication}>
                      Or prepare application without a recommendation
                    </Button>
                  </div>
                )}
              </CardContent>
            </Card>
          )}
        </div>
      </div>
    </div>
  )
}
