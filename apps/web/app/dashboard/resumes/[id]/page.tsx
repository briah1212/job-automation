'use client'

import { useState, useEffect } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  CheckCircle,
  XCircle,
  Download,
  Wand2,
  Loader2,
  GitCompare,
  Lock,
  Plus,
  AlertTriangle,
} from 'lucide-react'
import { RequirementEvidenceMatrix } from '@/components/resumes/requirement-evidence-matrix'
import { ResumeDiffViewer } from '@/components/resumes/resume-diff-viewer'
import { apiClient } from '@/lib/api-client'
import type {
  ResumeVersion,
  ResumeFamily,
  ResumeTailorResponse,
  ResumeDiff,
  DocumentRendering,
  DocumentLock,
} from '@/lib/types'

const LOCK_TYPES = ['exact_title', 'exact_dates', 'protect_accomplishment']

export default function ResumeDetailPage({ params }: { params: { id: string } }) {
  const [version, setVersion] = useState<ResumeVersion | null>(null)
  const [family, setFamily] = useState<ResumeFamily | null>(null)
  const [loading, setLoading] = useState(true)
  const [notFound, setNotFound] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Tailoring state
  const [jobId, setJobId] = useState('')
  const [tailoring, setTailoring] = useState(false)
  const [tailorResult, setTailorResult] = useState<ResumeTailorResponse | null>(null)
  const [tailorError, setTailorError] = useState<string | null>(null)

  // Diff state
  const [diff, setDiff] = useState<ResumeDiff | null>(null)
  const [loadingDiff, setLoadingDiff] = useState(false)
  const [diffError, setDiffError] = useState<string | null>(null)

  // Download/render state
  const [rendering, setRendering] = useState(false)
  const [renderResult, setRenderResult] = useState<DocumentRendering | null>(null)
  const [renderError, setRenderError] = useState<string | null>(null)

  // Approve/reject state
  const [approving, setApproving] = useState(false)

  // Locks state
  const [locks, setLocks] = useState<DocumentLock[]>([])
  const [loadingLocks, setLoadingLocks] = useState(false)
  const [addingLock, setAddingLock] = useState(false)
  const [lockType, setLockType] = useState(LOCK_TYPES[0])
  const [targetRef, setTargetRef] = useState('')
  const [lockValue, setLockValue] = useState('')
  const [lockError, setLockError] = useState<string | null>(null)

  // Fetch resume version + family
  useEffect(() => {
    const fetchVersion = async () => {
      try {
        setLoading(true)
        setError(null)
        const versions = await apiClient.getResumeVersions()
        const found = versions.find((v) => v.id === params.id)
        if (!found) {
          setNotFound(true)
          return
        }
        setVersion(found)

        if (found.family_id) {
          try {
            const families = await apiClient.getResumes()
            setFamily(families.find((f) => f.id === found.family_id) ?? null)
          } catch (err) {
            console.error('Failed to load resume family:', err)
          }
        }
      } catch (err) {
        setError('Failed to load resume version')
        console.error(err)
      } finally {
        setLoading(false)
      }
    }

    fetchVersion()
  }, [params.id])

  // Fetch locks once we know the family id
  useEffect(() => {
    if (!version?.family_id) return

    const fetchLocks = async () => {
      try {
        setLoadingLocks(true)
        const lockData = await apiClient.getResumeLocks(version.family_id)
        setLocks(lockData)
      } catch (err) {
        console.error('Failed to load locks:', err)
      } finally {
        setLoadingLocks(false)
      }
    }

    fetchLocks()
  }, [version?.family_id])

  const handleTailor = async () => {
    if (!version || !jobId.trim()) return
    try {
      setTailoring(true)
      setTailorError(null)
      setDiff(null)
      setDiffError(null)
      const result = await apiClient.tailorResume(version.id, jobId.trim())
      setTailorResult(result)
    } catch (err) {
      setTailorError('Failed to tailor resume')
      console.error(err)
    } finally {
      setTailoring(false)
    }
  }

  const handleViewDiff = async () => {
    if (!tailorResult || !version) return
    try {
      setLoadingDiff(true)
      setDiffError(null)
      const diffResult = await apiClient.getResumeDiff(tailorResult.resume_version_id, version.id)
      setDiff(diffResult)
    } catch (err) {
      setDiffError('Failed to load diff')
      console.error(err)
    } finally {
      setLoadingDiff(false)
    }
  }

  const handleDownload = async () => {
    if (!version) return
    try {
      setRendering(true)
      setRenderError(null)
      const rendering = await apiClient.renderResume(version.id, 'pdf')
      setRenderResult(rendering)
    } catch (err) {
      setRenderError('Failed to render resume')
      console.error(err)
    } finally {
      setRendering(false)
    }
  }

  const handleApprove = async () => {
    if (!version?.family_id) return
    try {
      setApproving(true)
      const updatedFamily = await apiClient.approveResume(version.family_id)
      setFamily(updatedFamily)
    } catch (err) {
      console.error('Failed to approve resume:', err)
    } finally {
      setApproving(false)
    }
  }

  const handleAddLock = async () => {
    if (!version?.family_id || !targetRef.trim()) return
    try {
      setAddingLock(true)
      setLockError(null)
      const newLock = await apiClient.createResumeLock(version.family_id, {
        lock_type: lockType,
        target_ref: targetRef.trim(),
        value: lockValue.trim() ? { note: lockValue.trim() } : undefined,
      })
      setLocks((prev) => [...prev, newLock])
      setTargetRef('')
      setLockValue('')
    } catch (err) {
      setLockError('Failed to create lock')
      console.error(err)
    } finally {
      setAddingLock(false)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="flex flex-col items-center gap-4">
          <Loader2 className="h-8 w-8 animate-spin text-primary" />
          <p className="text-muted-foreground">Loading resume...</p>
        </div>
      </div>
    )
  }

  if (notFound) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <Card className="w-full max-w-md">
          <CardHeader>
            <CardTitle>Resume Not Found</CardTitle>
            <CardDescription>
              No resume version matching this id could be found.
            </CardDescription>
          </CardHeader>
        </Card>
      </div>
    )
  }

  if (error && !version) {
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

  if (!version) {
    return null
  }

  const parsedData = version.parsed_data

  return (
    <div className="space-y-6 pb-8">
      {error && (
        <Card className="border-red-200 bg-red-50">
          <CardContent className="pt-6">
            <p className="text-red-800 text-sm">{error}</p>
          </CardContent>
        </Card>
      )}

      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">{family?.name || 'Resume'}</h1>
          <p className="text-muted-foreground">
            {family?.target_category || (version.parent_id ? 'Tailored Variant' : 'Base Resume')} •{' '}
            {family?.status ?? version.status}
          </p>
        </div>
        <div className="flex gap-2 flex-wrap">
          <Button variant="outline" onClick={handleDownload} disabled={rendering}>
            {rendering ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            ) : (
              <Download className="mr-2 h-4 w-4" />
            )}
            Download
          </Button>
          <Button variant="destructive" disabled title="Reject endpoint not available yet">
            <XCircle className="mr-2 h-4 w-4" />
            Reject
          </Button>
          <Button onClick={handleApprove} disabled={approving}>
            {approving ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            ) : (
              <CheckCircle className="mr-2 h-4 w-4" />
            )}
            Approve
          </Button>
        </div>
      </div>

      {renderResult && (
        <Card className="border-green-200 bg-green-50">
          <CardContent className="pt-6 text-sm text-green-800">
            Rendered {renderResult.format.toUpperCase()} ({renderResult.page_count ?? '?'} pages) at{' '}
            <code className="bg-green-100 px-1 rounded">{renderResult.file_path}</code>
            <p className="text-xs text-green-700 mt-1">
              File serving is not wired up yet, so this path cannot be opened directly from the browser.
            </p>
          </CardContent>
        </Card>
      )}
      {renderError && (
        <Card className="border-red-200 bg-red-50">
          <CardContent className="pt-6 text-sm text-red-800">{renderError}</CardContent>
        </Card>
      )}

      {/* Parsed Resume Data */}
      <Card>
        <CardHeader>
          <CardTitle>Parsed Resume Data</CardTitle>
          <CardDescription>Extracted information from your resume</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {!parsedData || Object.keys(parsedData).length === 0 ? (
            <p className="text-sm text-muted-foreground">Not yet parsed</p>
          ) : (
            <>
              {parsedData.summary && (
                <div>
                  <h3 className="font-medium mb-2">Summary</h3>
                  <p className="text-sm text-muted-foreground">{parsedData.summary}</p>
                </div>
              )}

              {parsedData.experience && parsedData.experience.length > 0 && (
                <div>
                  <h3 className="font-medium mb-2">Work Experience</h3>
                  <div className="space-y-3">
                    {parsedData.experience.map((exp: any, index: number) => (
                      <div key={index} className="border-l-2 border-primary pl-4">
                        <div className="font-medium">{exp.title}</div>
                        <div className="text-sm text-muted-foreground">
                          {exp.company} • {exp.start_date}
                          {exp.end_date ? ` - ${exp.end_date}` : ''}
                        </div>
                        {exp.description && <p className="text-sm mt-1">{exp.description}</p>}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {parsedData.skills && parsedData.skills.length > 0 && (
                <div>
                  <h3 className="font-medium mb-2">Skills</h3>
                  <div className="flex flex-wrap gap-2">
                    {parsedData.skills.map((skill: string, index: number) => (
                      <Badge key={index}>{skill}</Badge>
                    ))}
                  </div>
                </div>
              )}

              {parsedData.education && parsedData.education.length > 0 && (
                <div>
                  <h3 className="font-medium mb-2">Education</h3>
                  <div className="space-y-2">
                    {parsedData.education.map((edu: any, index: number) => (
                      <div key={index}>
                        <div className="font-medium">{edu.degree}</div>
                        <div className="text-sm text-muted-foreground">
                          {edu.institution} • {edu.graduation_year}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </>
          )}
        </CardContent>
      </Card>

      {/* Tailor for Job */}
      <Card>
        <CardHeader>
          <CardTitle>Tailor for Job</CardTitle>
          <CardDescription>
            Generate a tailored resume variant for a specific job posting
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex gap-2 items-end">
            <div className="flex-1 space-y-1">
              <Label htmlFor="job-id">Job ID</Label>
              <Input
                id="job-id"
                placeholder="Enter job id to tailor for"
                value={jobId}
                onChange={(e) => setJobId(e.target.value)}
              />
            </div>
            <Button onClick={handleTailor} disabled={tailoring || !jobId.trim()}>
              {tailoring ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <Wand2 className="mr-2 h-4 w-4" />
              )}
              Tailor
            </Button>
          </div>

          {tailorError && <p className="text-sm text-red-600">{tailorError}</p>}

          {tailorResult && (
            <div className="space-y-4">
              <div className="flex items-center justify-between border-t pt-4">
                <div className="text-sm text-muted-foreground">
                  Quality score: <span className="font-semibold">{tailorResult.quality_score}</span>{' '}
                  • Page count: <span className="font-semibold">{tailorResult.page_count}</span>
                </div>
                <Button variant="outline" onClick={handleViewDiff} disabled={loadingDiff}>
                  {loadingDiff ? (
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  ) : (
                    <GitCompare className="mr-2 h-4 w-4" />
                  )}
                  View Diff
                </Button>
              </div>

              {tailorResult.warnings && tailorResult.warnings.length > 0 && (
                <div className="rounded-md border border-amber-300 bg-amber-50 p-3 space-y-1">
                  <div className="flex items-center gap-2 text-amber-800 font-semibold text-sm">
                    <AlertTriangle className="h-4 w-4" />
                    Warnings
                  </div>
                  <ul className="list-disc list-inside text-sm text-amber-800 space-y-1">
                    {tailorResult.warnings.map((warning, index) => (
                      <li key={index}>{warning}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}
        </CardContent>
      </Card>

      {tailorResult && (
        <RequirementEvidenceMatrix items={tailorResult.requirement_evidence_matrix} />
      )}

      {diffError && (
        <Card className="border-red-200 bg-red-50">
          <CardContent className="pt-6 text-sm text-red-800">{diffError}</CardContent>
        </Card>
      )}

      {diff && <ResumeDiffViewer diff={diff} />}

      {/* Lock Management */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Lock className="h-5 w-5" />
            Content Locks
          </CardTitle>
          <CardDescription>
            Protect specific content from being modified during tailoring
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {loadingLocks ? (
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" />
              Loading locks...
            </div>
          ) : locks.length === 0 ? (
            <p className="text-sm text-muted-foreground">No locks configured</p>
          ) : (
            <div className="space-y-2">
              {locks.map((lock) => (
                <div
                  key={lock.id}
                  className="flex items-center justify-between border rounded-md p-3 text-sm"
                >
                  <div>
                    <span className="font-medium">{lock.lock_type}</span>
                    <span className="text-muted-foreground"> → {lock.target_ref}</span>
                  </div>
                  {lock.value && (
                    <Badge variant="outline">{JSON.stringify(lock.value)}</Badge>
                  )}
                </div>
              ))}
            </div>
          )}

          <div className="border-t pt-4 space-y-3">
            <h3 className="font-medium text-sm">Add Lock</h3>
            <div className="grid gap-3 md:grid-cols-3">
              <div className="space-y-1">
                <Label>Lock Type</Label>
                <Select value={lockType} onValueChange={setLockType}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {LOCK_TYPES.map((type) => (
                      <SelectItem key={type} value={type}>
                        {type}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-1">
                <Label htmlFor="target-ref">Target Ref</Label>
                <Input
                  id="target-ref"
                  placeholder="e.g. experience[0].title"
                  value={targetRef}
                  onChange={(e) => setTargetRef(e.target.value)}
                />
              </div>
              <div className="space-y-1">
                <Label htmlFor="lock-value">Value (optional)</Label>
                <Input
                  id="lock-value"
                  placeholder="optional note"
                  value={lockValue}
                  onChange={(e) => setLockValue(e.target.value)}
                />
              </div>
            </div>
            {lockError && <p className="text-sm text-red-600">{lockError}</p>}
            <Button
              variant="outline"
              onClick={handleAddLock}
              disabled={addingLock || !targetRef.trim() || !version?.family_id}
            >
              {addingLock ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <Plus className="mr-2 h-4 w-4" />
              )}
              Add Lock
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
