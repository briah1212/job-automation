'use client'

import { useState, useEffect } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { ExternalLink, Send, MapPin, DollarSign, Briefcase, ChevronDown, ChevronUp, RefreshCw, Bookmark, X, Loader2 } from 'lucide-react'
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
  const [saving, setSaving] = useState(false)
  const [rejecting, setRejecting] = useState(false)
  
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

  // Fetch resume selection and resumes
  useEffect(() => {
    const fetchResumesData = async () => {
      try {
        setLoadingResumes(true)
        const [selectionData, resumesData] = await Promise.all([
          apiClient.getResumeSelection(params.id),
          apiClient.getResumeVersions()
        ])
        setResumeSelection(selectionData)
        setResumes(resumesData)
      } catch (err) {
        console.error('Failed to load resume data:', err)
        // Don't set error, selection might not exist yet
      } finally {
        setLoadingResumes(false)
      }
    }

    fetchResumesData()
  }, [params.id])

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

  const handleSaveForLater = async () => {
    try {
      setSaving(true)
      setError(null)
      // TODO: Implement save for later API call
      await new Promise(resolve => setTimeout(resolve, 500)) // Placeholder
      alert('Job saved for later!')
    } catch (err) {
      setError('Failed to save job')
      console.error(err)
    } finally {
      setSaving(false)
    }
  }

  const handleReject = async () => {
    try {
      setRejecting(true)
      setError(null)
      // TODO: Implement reject API call
      await new Promise(resolve => setTimeout(resolve, 500)) // Placeholder
      alert('Job rejected')
      router.push('/dashboard/jobs')
    } catch (err) {
      setError('Failed to reject job')
      console.error(err)
    } finally {
      setRejecting(false)
    }
  }

  const handlePrepareApplication = () => {
    router.push(`/dashboard/applications/prepare?jobId=${params.id}`)
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
          <h1 className="text-3xl font-bold">{job.title || 'Senior Software Engineer'}</h1>
          <div className="flex items-center gap-4 mt-2 text-muted-foreground">
            <div className="flex items-center gap-1">
              <Briefcase className="h-4 w-4" />
              {job.company || 'Google'}
            </div>
            <div className="flex items-center gap-1">
              <MapPin className="h-4 w-4" />
              {job.location || 'Mountain View, CA'}
            </div>
            {job.salary_range && (
              <div className="flex items-center gap-1">
                <DollarSign className="h-4 w-4" />
                {job.salary_range}
              </div>
            )}
          </div>
        </div>
        
        {/* Primary Actions */}
        <div className="flex gap-2">
          <Button variant="outline" asChild>
            <a href={job.url || '#'} target="_blank" rel="noopener noreferrer">
              <ExternalLink className="mr-2 h-4 w-4" />
              View Original
            </a>
          </Button>
        </div>
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
        
        <Button
          variant="outline"
          onClick={handleSaveForLater}
          disabled={saving}
        >
          {saving ? (
            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
          ) : (
            <Bookmark className="mr-2 h-4 w-4" />
          )}
          Save for Later
        </Button>
        
        <Button
          variant="outline"
          onClick={handleReject}
          disabled={rejecting}
          className="text-red-600 hover:text-red-700 hover:bg-red-50"
        >
          {rejecting ? (
            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
          ) : (
            <X className="mr-2 h-4 w-4" />
          )}
          Reject
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
              <CardContent className="space-y-4">
                <div>
                  <h3 className="font-medium mb-2">About the Role</h3>
                  <p className="text-sm text-muted-foreground">
                    {job.description || `We're looking for a Senior Software Engineer to join our Search Infrastructure team.
                    You'll be working on building and scaling systems that power Google Search, serving
                    billions of queries daily.`}
                  </p>
                </div>
                <div>
                  <h3 className="font-medium mb-2">Requirements</h3>
                  <ul className="list-disc list-inside text-sm text-muted-foreground space-y-1">
                    <li>5+ years of software development experience</li>
                    <li>Strong understanding of distributed systems</li>
                    <li>Experience with large-scale backend systems</li>
                    <li>Proficiency in C++, Java, or Python</li>
                  </ul>
                </div>
                <div>
                  <h3 className="font-medium mb-2">Nice to Have</h3>
                  <ul className="list-disc list-inside text-sm text-muted-foreground space-y-1">
                    <li>Experience with search or information retrieval</li>
                    <li>Knowledge of machine learning systems</li>
                    <li>Open source contributions</li>
                  </ul>
                </div>
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
              <CardContent>
                <p className="text-sm text-muted-foreground">
                  Calculate a match score first to get resume recommendations.
                </p>
              </CardContent>
            </Card>
          )}
        </div>
      </div>
    </div>
  )
}
