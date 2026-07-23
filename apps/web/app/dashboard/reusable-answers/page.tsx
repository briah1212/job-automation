'use client'

import { useEffect, useState } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { Badge } from '@/components/ui/badge'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Loader2, Plus, Trash2 } from 'lucide-react'
import { apiClient } from '@/lib/api-client'
import type { ReusableAnswer } from '@/lib/types'

const RISK_LEVELS = ['low', 'medium', 'high']

const RISK_STYLES: Record<string, string> = {
  low: 'border-green-300 bg-green-50 text-green-700',
  medium: 'border-amber-300 bg-amber-50 text-amber-700',
  high: 'border-red-300 bg-red-50 text-red-700',
}

export default function ReusableAnswersPage() {
  const [answers, setAnswers] = useState<ReusableAnswer[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const [canonicalQuestion, setCanonicalQuestion] = useState('')
  const [exactAnswer, setExactAnswer] = useState('')
  const [riskLevel, setRiskLevel] = useState('low')
  const [creating, setCreating] = useState(false)

  const load = async () => {
    try {
      setLoading(true)
      setError(null)
      const data = await apiClient.getReusableAnswers()
      setAnswers(data)
    } catch (err) {
      setError('Failed to load reusable answers')
      console.error(err)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
  }, [])

  const handleCreate = async () => {
    if (!canonicalQuestion.trim() || !exactAnswer.trim()) return
    try {
      setCreating(true)
      setError(null)
      const answer = await apiClient.createReusableAnswer({
        canonical_question: canonicalQuestion.trim(),
        exact_answer: exactAnswer.trim(),
        risk_level: riskLevel,
        user_approved: true,
      })
      setAnswers((prev) => [...prev, answer].sort((a, b) => a.canonical_question.localeCompare(b.canonical_question)))
      setCanonicalQuestion('')
      setExactAnswer('')
    } catch (err) {
      setError((err as Error).message || 'Failed to create reusable answer')
      console.error(err)
    } finally {
      setCreating(false)
    }
  }

  const handleDelete = async (id: string) => {
    if (!confirm('Delete this reusable answer?')) return
    try {
      await apiClient.deleteReusableAnswer(id)
      setAnswers((prev) => prev.filter((a) => a.id !== id))
    } catch (err) {
      setError('Failed to delete reusable answer')
      console.error(err)
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold">Reusable Answers</h1>
        <p className="text-muted-foreground">
          Pre-approved answers the browser worker uses automatically, without asking you again
        </p>
      </div>

      {error && (
        <Card className="border-red-200 bg-red-50">
          <CardContent className="pt-6">
            <p className="text-sm text-red-800">{error}</p>
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <CardTitle>Teach a New Answer</CardTitle>
          <CardDescription>
            Proactively answer a question before any application asks it - you&apos;re asserting this as true about yourself
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="canonical_question">Question</Label>
            <Input
              id="canonical_question"
              value={canonicalQuestion}
              onChange={(e) => setCanonicalQuestion(e.target.value)}
              placeholder="Are you legally authorized to work in this country?"
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="exact_answer">Answer</Label>
            <Textarea
              id="exact_answer"
              value={exactAnswer}
              onChange={(e) => setExactAnswer(e.target.value)}
              rows={3}
            />
          </div>
          <div className="flex items-end gap-4">
            <div className="space-y-2">
              <Label htmlFor="risk_level">Risk Level</Label>
              <Select value={riskLevel} onValueChange={setRiskLevel}>
                <SelectTrigger id="risk_level" className="w-[160px]">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {RISK_LEVELS.map((level) => (
                    <SelectItem key={level} value={level} className="capitalize">
                      {level}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <Button onClick={handleCreate} disabled={creating || !canonicalQuestion.trim() || !exactAnswer.trim()}>
              {creating ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <Plus className="mr-2 h-4 w-4" />
              )}
              Add Answer
            </Button>
          </div>
        </CardContent>
      </Card>

      {loading ? (
        <Card className="p-8">
          <div className="flex justify-center">
            <Loader2 className="h-6 w-6 animate-spin text-primary" />
          </div>
        </Card>
      ) : answers.length === 0 ? (
        <Card className="p-8">
          <p className="text-center text-muted-foreground">No reusable answers yet</p>
        </Card>
      ) : (
        <div className="space-y-3">
          {answers.map((answer) => (
            <Card key={answer.id}>
              <CardContent className="pt-6">
                <div className="flex items-start justify-between gap-4">
                  <div className="space-y-2 flex-1">
                    <div className="flex items-center gap-2">
                      <p className="font-medium">{answer.canonical_question}</p>
                      <Badge variant="outline" className={`text-xs capitalize ${RISK_STYLES[answer.risk_level] || ''}`}>
                        {answer.risk_level}
                      </Badge>
                      {!answer.user_approved && (
                        <Badge variant="outline" className="text-xs border-amber-300 bg-amber-50 text-amber-700">
                          Unapproved
                        </Badge>
                      )}
                    </div>
                    <p className="text-sm text-muted-foreground whitespace-pre-wrap">{answer.exact_answer}</p>
                    {answer.categories.length > 0 && (
                      <div className="flex flex-wrap gap-1">
                        {answer.categories.map((category, i) => (
                          <Badge key={i} variant="secondary" className="text-xs">
                            {category}
                          </Badge>
                        ))}
                      </div>
                    )}
                  </div>
                  <Button variant="outline" size="sm" onClick={() => handleDelete(answer.id)}>
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  )
}
