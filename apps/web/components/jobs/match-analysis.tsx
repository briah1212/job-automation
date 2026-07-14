import { JobMatchScore } from '@/lib/types'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'

interface MatchAnalysisProps {
  matchScore: JobMatchScore
}

interface DimensionScore {
  label: string
  score: number
  key: 'skill_score' | 'experience_score' | 'seniority_score' | 'location_score' | 'salary_score'
}

export function MatchAnalysis({ matchScore }: MatchAnalysisProps) {
  const getScoreColor = (score: number): string => {
    if (score >= 80) return 'text-green-600'
    if (score >= 60) return 'text-yellow-600'
    if (score >= 40) return 'text-orange-600'
    return 'text-red-600'
  }

  const getProgressBarColor = (score: number): string => {
    if (score >= 80) return 'bg-green-500'
    if (score >= 60) return 'bg-yellow-500'
    if (score >= 40) return 'bg-orange-500'
    return 'bg-red-500'
  }

  const getActionBadgeVariant = (action: string) => {
    switch (action) {
      case 'apply':
        return 'default'
      case 'pass':
        return 'destructive'
      case 'maybe':
      case 'needs_tailoring':
        return 'secondary'
      default:
        return 'outline'
    }
  }

  const dimensions: DimensionScore[] = [
    { label: 'Skills', score: matchScore.skill_score, key: 'skill_score' },
    { label: 'Experience', score: matchScore.experience_score, key: 'experience_score' },
    { label: 'Seniority', score: matchScore.seniority_score, key: 'seniority_score' },
    { label: 'Location', score: matchScore.location_score, key: 'location_score' },
    { label: 'Salary', score: matchScore.salary_score, key: 'salary_score' },
  ]

  return (
    <Card>
      <CardHeader>
        <CardTitle>Match Analysis</CardTitle>
      </CardHeader>
      <CardContent className="space-y-6">
        {/* Overall Score */}
        <div className="flex flex-col items-center justify-center py-6 border-b">
          <div className="text-sm text-muted-foreground mb-2">Overall Match Score</div>
          <div className={`text-6xl font-bold ${getScoreColor(matchScore.overall_score)}`}>
            {matchScore.overall_score}
          </div>
          <div className="text-sm text-muted-foreground mt-2">out of 100</div>
        </div>

        {/* Dimension Scores */}
        <div className="space-y-4">
          <h3 className="font-semibold text-sm text-muted-foreground">Score Breakdown</h3>
          {dimensions.map((dimension) => (
            <div key={dimension.key} className="space-y-2">
              <div className="flex items-center justify-between text-sm">
                <span className="font-medium">{dimension.label}</span>
                <span className={`font-semibold ${getScoreColor(dimension.score)}`}>
                  {dimension.score}%
                </span>
              </div>
              <div className="w-full bg-gray-200 rounded-full h-2 overflow-hidden">
                <div
                  className={`h-full ${getProgressBarColor(dimension.score)} transition-all duration-300`}
                  style={{ width: `${dimension.score}%` }}
                />
              </div>
            </div>
          ))}
        </div>

        {/* Hard Blockers */}
        {matchScore.hard_blockers && matchScore.hard_blockers.length > 0 && (
          <div className="space-y-3">
            <h3 className="font-semibold text-sm text-muted-foreground">Hard Blockers</h3>
            <div className="flex flex-wrap gap-2">
              {matchScore.hard_blockers.map((blocker, index) => (
                <Badge
                  key={index}
                  className="bg-red-100 text-red-800 border-red-300 hover:bg-red-100"
                >
                  {blocker}
                </Badge>
              ))}
            </div>
          </div>
        )}

        {/* Strong Matches */}
        {matchScore.strong_matches && matchScore.strong_matches.length > 0 && (
          <div className="space-y-3">
            <h3 className="font-semibold text-sm text-muted-foreground">Strong Matches</h3>
            <div className="flex flex-wrap gap-2">
              {matchScore.strong_matches.map((match, index) => (
                <Badge
                  key={index}
                  className="bg-green-100 text-green-800 border-green-300 hover:bg-green-100"
                >
                  {match}
                </Badge>
              ))}
            </div>
          </div>
        )}

        {/* Soft Gaps */}
        {matchScore.soft_gaps && matchScore.soft_gaps.length > 0 && (
          <div className="space-y-3">
            <h3 className="font-semibold text-sm text-muted-foreground">Soft Gaps</h3>
            <div className="flex flex-wrap gap-2">
              {matchScore.soft_gaps.map((gap, index) => (
                <Badge
                  key={index}
                  className="bg-yellow-100 text-yellow-800 border-yellow-300 hover:bg-yellow-100"
                >
                  {gap}
                </Badge>
              ))}
            </div>
          </div>
        )}

        {/* Missing Info */}
        {matchScore.missing_info && matchScore.missing_info.length > 0 && (
          <div className="space-y-3">
            <h3 className="font-semibold text-sm text-muted-foreground">Missing Information</h3>
            <div className="flex flex-wrap gap-2">
              {matchScore.missing_info.map((info, index) => (
                <Badge
                  key={index}
                  className="bg-gray-100 text-gray-800 border-gray-300 hover:bg-gray-100"
                >
                  {info}
                </Badge>
              ))}
            </div>
          </div>
        )}

        {/* AI Explanation */}
        {matchScore.explanation && (
          <div className="space-y-3 border-t pt-4">
            <h3 className="font-semibold text-sm text-muted-foreground">Analysis</h3>
            <p className="text-sm text-foreground leading-relaxed">
              {matchScore.explanation}
            </p>
          </div>
        )}

        {/* Recommended Action */}
        <div className="flex items-center justify-between border-t pt-4">
          <span className="text-sm font-semibold text-muted-foreground">Recommended Action</span>
          <Badge variant={getActionBadgeVariant(matchScore.recommended_action)}>
            {matchScore.recommended_action.replace('_', ' ').toUpperCase()}
          </Badge>
        </div>
      </CardContent>
    </Card>
  )
}
