import React from 'react'
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { AlertTriangle, CheckCircle2, FileText, Sparkles } from 'lucide-react'
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
  const selectedResume = resumes.find(r => r.id === selection.selected_resume_id)

  return (
    <div className="space-y-6">
      {/* Selected Resume Card */}
      <Card className="border-2 border-primary shadow-md">
        <CardHeader>
          <div className="flex items-start justify-between">
            <div className="flex items-center gap-2">
              <CheckCircle2 className="h-5 w-5 text-primary" />
              <CardTitle className="text-xl">Recommended Resume</CardTitle>
            </div>
            {selection.tailoring_recommended && (
              <Badge variant="secondary" className="bg-amber-100 text-amber-800 border-amber-200">
                <Sparkles className="mr-1 h-3 w-3" />
                Tailoring Recommended
              </Badge>
            )}
          </div>
          <CardDescription className="text-base font-medium">
            {selection.selected_resume_name}
          </CardDescription>
        </CardHeader>
        
        <CardContent className="space-y-4">
          {/* Selection Rationale */}
          <div>
            <h4 className="text-sm font-semibold mb-2">Why this resume?</h4>
            <p className="text-sm text-muted-foreground">
              {selection.selection_rationale}
            </p>
          </div>

          {/* Missing Coverage Items */}
          {selection.missing_coverage && selection.missing_coverage.length > 0 && (
            <div className="space-y-2">
              <h4 className="text-sm font-semibold flex items-center gap-2">
                <AlertTriangle className="h-4 w-4 text-amber-500" />
                Missing Coverage
              </h4>
              <div className="flex flex-wrap gap-2">
                {selection.missing_coverage.map((item, index) => (
                  <Badge key={index} variant="outline" className="bg-amber-50 text-amber-700 border-amber-200">
                    {item}
                  </Badge>
                ))}
              </div>
            </div>
          )}

          {/* Tailoring Suggestions */}
          {selection.tailoring_recommended && selection.tailoring_suggestions && selection.tailoring_suggestions.length > 0 && (
            <div className="space-y-2">
              <h4 className="text-sm font-semibold">Tailoring Suggestions</h4>
              <ul className="list-disc list-inside space-y-1 text-sm text-muted-foreground">
                {selection.tailoring_suggestions.map((suggestion, index) => (
                  <li key={index}>{suggestion}</li>
                ))}
              </ul>
            </div>
          )}
        </CardContent>

        <CardFooter className="gap-3">
          <Button 
            variant="outline" 
            onClick={() => onViewResume(selection.selected_resume_id)}
          >
            <FileText className="mr-2 h-4 w-4" />
            View Resume
          </Button>
          <Button 
            onClick={onPrepareApplication}
            className="flex-1"
          >
            Prepare Application
          </Button>
        </CardFooter>
      </Card>

      {/* Alternative Resumes */}
      {selection.alternatives && selection.alternatives.length > 0 && (
        <div className="space-y-3">
          <h3 className="text-sm font-semibold text-muted-foreground">Alternative Resumes</h3>
          <div className="space-y-3">
            {selection.alternatives.map((alt) => {
              const altResume = resumes.find(r => r.id === alt.resume_id)
              return (
                <Card key={alt.resume_id} className="opacity-60 hover:opacity-80 transition-opacity">
                  <CardHeader className="pb-3">
                    <div className="flex items-center justify-between">
                      <CardTitle className="text-base font-medium text-muted-foreground">
                        {alt.resume_name}
                      </CardTitle>
                      <Badge variant="outline" className="text-muted-foreground">
                        {alt.score}% match
                      </Badge>
                    </div>
                  </CardHeader>
                  <CardContent className="pt-0">
                    <p className="text-sm text-muted-foreground">{alt.reason}</p>
                  </CardContent>
                  <CardFooter>
                    <Button 
                      variant="ghost" 
                      size="sm"
                      onClick={() => onViewResume(alt.resume_id)}
                      className="text-muted-foreground"
                    >
                      <FileText className="mr-2 h-3 w-3" />
                      View
                    </Button>
                  </CardFooter>
                </Card>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}
