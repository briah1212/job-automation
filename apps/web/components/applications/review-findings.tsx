'use client'

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Progress } from '@/components/ui/progress'
import { CheckCircle2, XCircle, AlertTriangle, Loader2, RefreshCw } from 'lucide-react'
import type { ApplicationReviewResult } from '@/lib/types'

interface ReviewFindingsProps {
  review: ApplicationReviewResult | null
  onRunReview: () => void
  running?: boolean
}

export function ReviewFindings({ review, onRunReview, running }: ReviewFindingsProps) {
  if (!review) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Review Findings</CardTitle>
          <CardDescription>No review has been run yet</CardDescription>
        </CardHeader>
        <CardContent>
          <Button onClick={onRunReview} disabled={running}>
            {running ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            ) : (
              <RefreshCw className="mr-2 h-4 w-4" />
            )}
            Run Review
          </Button>
        </CardContent>
      </Card>
    )
  }

  // Normalize confidence to a 0-100 scale whether the API returns a 0-1 fraction or a percentage.
  const confidencePct = Math.round(review.confidence <= 1 ? review.confidence * 100 : review.confidence)

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle>Review Findings</CardTitle>
          <Button size="sm" variant="outline" onClick={onRunReview} disabled={running}>
            {running ? (
              <Loader2 className="mr-2 h-3 w-3 animate-spin" />
            ) : (
              <RefreshCw className="mr-2 h-3 w-3" />
            )}
            Re-run
          </Button>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex items-center gap-2">
          {review.passed ? (
            <CheckCircle2 className="h-5 w-5 text-green-600" />
          ) : (
            <XCircle className="h-5 w-5 text-red-600" />
          )}
          <span className={`font-medium ${review.passed ? 'text-green-700' : 'text-red-700'}`}>
            {review.passed ? 'Passed' : 'Failed'}
          </span>
        </div>

        <div className="space-y-2">
          <div className="flex items-center justify-between text-sm">
            <span className="font-medium">Confidence</span>
            <span className="font-semibold">{confidencePct}%</span>
          </div>
          <Progress value={confidencePct} />
        </div>

        {review.blocking_findings.length > 0 && (
          <div className="space-y-2">
            <h4 className="text-sm font-semibold text-red-700">Blocking Findings</h4>
            <ul className="space-y-1">
              {review.blocking_findings.map((finding, i) => (
                <li
                  key={i}
                  className="text-sm bg-red-50 text-red-800 border border-red-200 rounded px-2 py-1"
                >
                  {finding}
                </li>
              ))}
            </ul>
          </div>
        )}

        {review.warnings.length > 0 && (
          <div className="space-y-2">
            <h4 className="text-sm font-semibold text-amber-700 flex items-center gap-1">
              <AlertTriangle className="h-4 w-4" />
              Warnings
            </h4>
            <ul className="space-y-1">
              {review.warnings.map((warning, i) => (
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

        {review.recommended_correction && (
          <div className="space-y-1 border-t pt-3">
            <h4 className="text-sm font-semibold">Recommended Correction</h4>
            <p className="text-sm text-muted-foreground">{review.recommended_correction}</p>
          </div>
        )}
      </CardContent>
    </Card>
  )
}
