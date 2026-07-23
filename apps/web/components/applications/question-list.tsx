'use client'

import { useState } from 'react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { Checkbox } from '@/components/ui/checkbox'
import { Label } from '@/components/ui/label'
import { AlertTriangle, Loader2, Save, Check } from 'lucide-react'
import { apiClient } from '@/lib/api-client'
import type { ApplicationQuestionWithAnswer } from '@/lib/types'

interface QuestionListProps {
  applicationId: string
  questions: ApplicationQuestionWithAnswer[]
  onAnswerUpdate: (questionId: string, newText: string) => void
}

const RISK_STYLES: Record<string, string> = {
  low: 'bg-green-100 text-green-800 border-green-300 hover:bg-green-100',
  medium: 'bg-amber-100 text-amber-800 border-amber-300 hover:bg-amber-100',
  high: 'bg-red-100 text-red-800 border-red-300 hover:bg-red-100',
}

const SOURCE_LABELS: Record<string, string> = {
  exact_approved: 'Exact approved answer',
  canonical_approved: 'Canonical approved answer (paraphrased)',
  deterministic: 'Deterministic answer',
  ai_generated: 'AI-generated - needs review',
  user_input: 'Your edit',
}

function RiskBadge({ level }: { level: string }) {
  return (
    <Badge variant="outline" className={`text-xs shrink-0 ${RISK_STYLES[level] || RISK_STYLES.low}`}>
      {level === 'high' && <AlertTriangle className="mr-1 h-3 w-3" />}
      {level} risk
    </Badge>
  )
}

function QuestionItem({
  applicationId,
  question,
  onAnswerUpdate,
}: {
  applicationId: string
  question: ApplicationQuestionWithAnswer
  onAnswerUpdate: (questionId: string, newText: string) => void
}) {
  const originalText = question.answer?.answer_text ?? ''
  const [text, setText] = useState(originalText)
  const [saving, setSaving] = useState(false)
  const [saveAsReusable, setSaveAsReusable] = useState(false)
  const [savingReusable, setSavingReusable] = useState(false)
  const [reusableSaved, setReusableSaved] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleBlur = async () => {
    if (text === originalText) return
    try {
      setSaving(true)
      setError(null)
      await apiClient.updateApplicationAnswer(applicationId, question.id, text)
      onAnswerUpdate(question.id, text)
    } catch (err) {
      setError('Failed to save answer')
      console.error(err)
    } finally {
      setSaving(false)
    }
  }

  const handleSaveReusable = async () => {
    try {
      setSavingReusable(true)
      setError(null)
      await apiClient.createReusableAnswer({
        canonical_question: question.question_text,
        exact_answer: text,
        risk_level: question.risk_level,
        allowed_paraphrasing: false,
      })
      setReusableSaved(true)
    } catch (err) {
      setError('Failed to save reusable answer')
      console.error(err)
    } finally {
      setSavingReusable(false)
    }
  }

  return (
    <div className="space-y-2 border-b pb-4 last:border-b-0 last:pb-0">
      <div className="flex items-start justify-between gap-2">
        <div className="font-medium text-sm">{question.question_text}</div>
        <RiskBadge level={question.risk_level} />
      </div>

      {question.answer && (
        <div className={`text-xs ${!question.answer.answer_text.trim() ? 'text-amber-700 font-medium' : 'text-muted-foreground'}`}>
          {!question.answer.answer_text.trim()
            ? "Needs your input - won't be auto-answered"
            : SOURCE_LABELS[question.answer.source] || question.answer.source}
          {question.answer.approved && ' (approved)'}
        </div>
      )}

      <Textarea
        value={text}
        onChange={(e) => setText(e.target.value)}
        onBlur={handleBlur}
        rows={3}
        className="text-sm"
        aria-label={`Answer for: ${question.question_text}`}
      />

      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <Checkbox
            id={`reusable-${question.id}`}
            checked={saveAsReusable}
            onCheckedChange={(checked) => setSaveAsReusable(checked === true)}
          />
          <Label htmlFor={`reusable-${question.id}`} className="text-xs font-normal text-muted-foreground">
            Save as reusable answer
          </Label>
          {saveAsReusable && (
            <Button
              type="button"
              size="sm"
              variant="outline"
              onClick={handleSaveReusable}
              disabled={savingReusable || reusableSaved}
            >
              {savingReusable ? (
                <Loader2 className="mr-1 h-3 w-3 animate-spin" />
              ) : reusableSaved ? (
                <Check className="mr-1 h-3 w-3" />
              ) : (
                <Save className="mr-1 h-3 w-3" />
              )}
              {reusableSaved ? 'Saved' : 'Save'}
            </Button>
          )}
        </div>
        {saving && <span className="text-xs text-muted-foreground">Saving...</span>}
      </div>

      {error && <p className="text-xs text-red-600">{error}</p>}
    </div>
  )
}

export function QuestionList({ applicationId, questions, onAnswerUpdate }: QuestionListProps) {
  if (questions.length === 0) {
    return <p className="text-sm text-muted-foreground">No questions available.</p>
  }

  return (
    <div className="space-y-4">
      {questions.map((question) => (
        <QuestionItem
          key={question.id}
          applicationId={applicationId}
          question={question}
          onAnswerUpdate={onAnswerUpdate}
        />
      ))}
    </div>
  )
}
