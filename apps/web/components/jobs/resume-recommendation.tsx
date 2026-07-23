import React from 'react'
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { AlertTriangle, CheckCircle2, FileText } from 'lucide-react'
import { ResumeSelectionResult, ResumeVersion } from '@/lib/types'

interface ResumeRecommendationProps {
  selection: ResumeSelectionResult
  resumes: ResumeVersion[]
  onViewResume: (resumeId: string) => void
  onPrepareApplication: () => void
}

export function ResumeRecommendation({
  selection,
  resumes,
  onViewResume,
  onPrepareApplication,
}: ResumeRecommendationProps) {
  const recommendedResume = resumes.find(r => r.id === selection.recommended_resume_id)
  const matchPct = Math.round(selection.match_score <= 1 ? selection.match_score * 100 : selection.match_score)

  return (
    <Card className="border-2 border-primary shadow-md">
      <CardHeader>
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-2">
            <CheckCircle2 className="h-5 w-5 text-primary" />
            <CardTitle className="text-xl">Recommended Resume</CardTitle>
          </div>
          <Badge variant="secondary">{matchPct}% match</Badge>
        </div>
        <CardDescription className="text-base font-medium">
          {recommendedResume
            ? `${recommendedResume.parent_id ? 'Tailored Variant' : 'Base Resume'} (v${recommendedResume.version})`
            : 'Resume'}
        </CardDescription>
      </CardHeader>

      <CardContent className="space-y-4">
        <div>
          <h4 className="text-sm font-semibold mb-2">Why this resume?</h4>
          <p className="text-sm text-muted-foreground">{selection.reasoning}</p>
        </div>

        {selection.strengths.length > 0 && (
          <div className="space-y-2">
            <h4 className="text-sm font-semibold flex items-center gap-2">
              <CheckCircle2 className="h-4 w-4 text-green-600" />
              Strengths
            </h4>
            <ul className="list-disc list-inside space-y-1 text-sm text-muted-foreground">
              {selection.strengths.map((strength, index) => (
                <li key={index}>{strength}</li>
              ))}
            </ul>
          </div>
        )}

        {selection.weaknesses.length > 0 && (
          <div className="space-y-2">
            <h4 className="text-sm font-semibold flex items-center gap-2">
              <AlertTriangle className="h-4 w-4 text-amber-500" />
              Weaknesses
            </h4>
            <ul className="list-disc list-inside space-y-1 text-sm text-muted-foreground">
              {selection.weaknesses.map((weakness, index) => (
                <li key={index}>{weakness}</li>
              ))}
            </ul>
          </div>
        )}

        {selection.customization_suggestions.length > 0 && (
          <div className="space-y-2">
            <h4 className="text-sm font-semibold">Customization Suggestions</h4>
            <ul className="list-disc list-inside space-y-1 text-sm text-muted-foreground">
              {selection.customization_suggestions.map((suggestion, index) => (
                <li key={index}>{suggestion}</li>
              ))}
            </ul>
          </div>
        )}
      </CardContent>

      <CardFooter className="gap-3">
        <Button variant="outline" onClick={() => onViewResume(selection.recommended_resume_id)}>
          <FileText className="mr-2 h-4 w-4" />
          View Resume
        </Button>
        <Button onClick={onPrepareApplication} className="flex-1">
          Prepare Application
        </Button>
      </CardFooter>
    </Card>
  )
}
