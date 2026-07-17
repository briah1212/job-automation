'use client'

import { useEffect, useState } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Textarea } from '@/components/ui/textarea'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { AlertTriangle, Loader2, Sparkles, Save } from 'lucide-react'
import { apiClient } from '@/lib/api-client'
import type { CoverLetter } from '@/lib/types'

interface CoverLetterCardProps {
  applicationId: string
}

const TONE_OPTIONS = [
  { value: 'professional', label: 'Professional' },
  { value: 'enthusiastic', label: 'Enthusiastic' },
  { value: 'formal', label: 'Formal' },
  { value: 'conversational', label: 'Conversational' },
]

const STATUS_STYLES: Record<string, string> = {
  needs_review: 'bg-amber-100 text-amber-800 border-amber-300 hover:bg-amber-100',
  approved: 'bg-green-100 text-green-800 border-green-300 hover:bg-green-100',
}

function countWords(text: string): number {
  const trimmed = text.trim()
  return trimmed.length === 0 ? 0 : trimmed.split(/\s+/).length
}

export function CoverLetterCard({ applicationId }: CoverLetterCardProps) {
  const [coverLetter, setCoverLetter] = useState<CoverLetter | null>(null)
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState<string | null>(null)

  const [tone, setTone] = useState<string>('professional')
  const [wordLimit, setWordLimit] = useState<string>('')

  const [content, setContent] = useState<string>('')
  const [generating, setGenerating] = useState(false)
  const [saving, setSaving] = useState(false)
  const [actionError, setActionError] = useState<string | null>(null)

  useEffect(() => {
    const fetchCoverLetter = async () => {
      try {
        setLoading(true)
        setLoadError(null)
        const data = await apiClient.getCoverLetter(applicationId)
        setCoverLetter(data)
        setContent(data.content)
      } catch (err) {
        const status = (err as { status?: number } | undefined)?.status
        if (status === 404) {
          // No cover letter generated yet - expected empty state, not an error.
          setCoverLetter(null)
        } else {
          setLoadError('Failed to load cover letter')
          console.error(err)
        }
      } finally {
        setLoading(false)
      }
    }

    fetchCoverLetter()
  }, [applicationId])

  const handleGenerate = async () => {
    try {
      setGenerating(true)
      setActionError(null)
      const parsedWordLimit = wordLimit.trim() ? Number(wordLimit) : undefined
      const data = await apiClient.generateCoverLetter(applicationId, {
        tone,
        word_limit: Number.isFinite(parsedWordLimit) ? parsedWordLimit : undefined,
      })
      setCoverLetter(data)
      setContent(data.content)
    } catch (err) {
      setActionError('Failed to generate cover letter')
      console.error(err)
    } finally {
      setGenerating(false)
    }
  }

  const handleSave = async () => {
    try {
      setSaving(true)
      setActionError(null)
      const data = await apiClient.updateCoverLetter(applicationId, content)
      setCoverLetter(data)
      setContent(data.content)
    } catch (err) {
      setActionError('Failed to save cover letter')
      console.error(err)
    } finally {
      setSaving(false)
    }
  }

  const hasUnsavedChanges = coverLetter !== null && content !== coverLetter.content
  const liveWordCount = countWords(content)

  if (loading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Cover Letter</CardTitle>
        </CardHeader>
        <CardContent className="flex items-center justify-center py-8">
          <Loader2 className="h-6 w-6 animate-spin text-primary" />
        </CardContent>
      </Card>
    )
  }

  if (loadError) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Cover Letter</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-red-600">{loadError}</p>
        </CardContent>
      </Card>
    )
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between gap-2">
          <div>
            <CardTitle>Cover Letter</CardTitle>
            {!coverLetter && (
              <CardDescription>Generate a tailored cover letter for this application</CardDescription>
            )}
          </div>
          {coverLetter && (
            <Badge
              variant="outline"
              className={`text-xs shrink-0 ${STATUS_STYLES[coverLetter.status] || STATUS_STYLES.needs_review}`}
            >
              {coverLetter.status.replace(/_/g, ' ')}
            </Badge>
          )}
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex flex-wrap items-end gap-3">
          <div className="space-y-1">
            <Label htmlFor="cover-letter-tone" className="text-xs font-normal text-muted-foreground">
              Tone
            </Label>
            <Select value={tone} onValueChange={setTone}>
              <SelectTrigger id="cover-letter-tone" className="w-[180px]">
                <SelectValue placeholder="Select tone..." />
              </SelectTrigger>
              <SelectContent>
                {TONE_OPTIONS.map((option) => (
                  <SelectItem key={option.value} value={option.value}>
                    {option.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-1">
            <Label htmlFor="cover-letter-word-limit" className="text-xs font-normal text-muted-foreground">
              Word Limit
            </Label>
            <Input
              id="cover-letter-word-limit"
              type="number"
              min={1}
              placeholder="e.g. 300 (optional)"
              value={wordLimit}
              onChange={(e) => setWordLimit(e.target.value)}
              className="w-[180px]"
            />
          </div>

          <Button onClick={handleGenerate} disabled={generating}>
            {generating ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            ) : (
              <Sparkles className="mr-2 h-4 w-4" />
            )}
            {coverLetter ? 'Regenerate' : 'Generate Cover Letter'}
          </Button>
        </div>

        {actionError && <p className="text-sm text-red-600">{actionError}</p>}

        {coverLetter && (
          <>
            <Textarea
              value={content}
              onChange={(e) => setContent(e.target.value)}
              rows={12}
              className="text-sm"
              aria-label="Cover letter content"
            />

            <div className="flex items-center justify-between text-sm text-muted-foreground">
              <span>{liveWordCount} words</span>
              <Button size="sm" onClick={handleSave} disabled={saving || !hasUnsavedChanges}>
                {saving ? (
                  <Loader2 className="mr-2 h-3 w-3 animate-spin" />
                ) : (
                  <Save className="mr-2 h-3 w-3" />
                )}
                Save
              </Button>
            </div>

            {coverLetter.warnings.length > 0 && (
              <div className="space-y-2">
                <h4 className="text-sm font-semibold text-amber-700 flex items-center gap-1">
                  <AlertTriangle className="h-4 w-4" />
                  Warnings
                </h4>
                <ul className="space-y-1">
                  {coverLetter.warnings.map((warning, i) => (
                    <li
                      key={i}
                      className="text-sm bg-amber-50 text-amber-800 border border-amber-200 rounded px-2 py-1"
                    >
                      {warning}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </>
        )}
      </CardContent>
    </Card>
  )
}
