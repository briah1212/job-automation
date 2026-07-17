import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { AlertTriangle } from 'lucide-react'
import type { ResumeDiff } from '@/lib/types'

interface ResumeDiffViewerProps {
  diff: ResumeDiff
}

export function ResumeDiffViewer({ diff }: ResumeDiffViewerProps) {
  const hasSummaryChange =
    diff.summary_change && (diff.summary_change.before || diff.summary_change.after)

  return (
    <Card>
      <CardHeader>
        <CardTitle>Resume Diff</CardTitle>
        <CardDescription>Changes made during tailoring</CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        {/* Warnings callout */}
        {diff.warnings && diff.warnings.length > 0 && (
          <div className="rounded-md border border-amber-300 bg-amber-50 p-3 space-y-1">
            <div className="flex items-center gap-2 text-amber-800 font-semibold text-sm">
              <AlertTriangle className="h-4 w-4" />
              Warnings
            </div>
            <ul className="list-disc list-inside text-sm text-amber-800 space-y-1">
              {diff.warnings.map((warning, index) => (
                <li key={index}>{warning}</li>
              ))}
            </ul>
          </div>
        )}

        {/* Summary change */}
        {hasSummaryChange && (
          <div className="space-y-2">
            <h3 className="font-medium text-sm">Summary Change</h3>
            <div className="grid gap-3 md:grid-cols-2">
              <div className="border rounded-md p-3 bg-red-50">
                <p className="text-xs font-semibold text-red-800 mb-1">Before</p>
                <p className="text-sm text-red-900 line-through decoration-red-400">
                  {diff.summary_change.before || '(empty)'}
                </p>
              </div>
              <div className="border rounded-md p-3 bg-green-50">
                <p className="text-xs font-semibold text-green-800 mb-1">After</p>
                <p className="text-sm text-green-900">{diff.summary_change.after || '(empty)'}</p>
              </div>
            </div>
            {diff.summary_change.diff_lines && diff.summary_change.diff_lines.length > 0 && (
              <div className="border rounded-md p-3 font-mono text-xs space-y-1 bg-muted/20">
                {diff.summary_change.diff_lines.map((line, index) => (
                  <div
                    key={index}
                    className={
                      line.startsWith('+')
                        ? 'text-green-700 bg-green-50'
                        : line.startsWith('-')
                        ? 'text-red-700 bg-red-50 line-through decoration-red-400'
                        : 'text-muted-foreground'
                    }
                  >
                    {line}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Added */}
        {diff.added && diff.added.length > 0 && (
          <div className="space-y-2">
            <h3 className="font-medium text-sm">Added</h3>
            <ul className="space-y-1">
              {diff.added.map((line, index) => (
                <li key={index} className="text-sm bg-green-50 text-green-800 rounded px-2 py-1">
                  + {line}
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Removed */}
        {diff.removed && diff.removed.length > 0 && (
          <div className="space-y-2">
            <h3 className="font-medium text-sm">Removed</h3>
            <ul className="space-y-1">
              {diff.removed.map((line, index) => (
                <li
                  key={index}
                  className="text-sm bg-red-50 text-red-800 rounded px-2 py-1 line-through decoration-red-400"
                >
                  - {line}
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Reordered */}
        {diff.reordered && diff.reordered.length > 0 && (
          <div className="space-y-2">
            <h3 className="font-medium text-sm">Reordered</h3>
            <ul className="space-y-1">
              {diff.reordered.map((line, index) => (
                <li key={index} className="text-sm bg-blue-50 text-blue-800 rounded px-2 py-1">
                  {line}
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Keyword changes */}
        {diff.keyword_changes &&
          ((diff.keyword_changes.added && diff.keyword_changes.added.length > 0) ||
            (diff.keyword_changes.removed && diff.keyword_changes.removed.length > 0)) && (
            <div className="space-y-2">
              <h3 className="font-medium text-sm">Keyword Changes</h3>
              <div className="flex flex-wrap gap-2">
                {diff.keyword_changes.added?.map((keyword, index) => (
                  <Badge
                    key={`added-${index}`}
                    className="bg-green-100 text-green-800 border-green-300 hover:bg-green-100"
                  >
                    + {keyword}
                  </Badge>
                ))}
                {diff.keyword_changes.removed?.map((keyword, index) => (
                  <Badge
                    key={`removed-${index}`}
                    className="bg-red-100 text-red-800 border-red-300 hover:bg-red-100 line-through decoration-red-400"
                  >
                    - {keyword}
                  </Badge>
                ))}
              </div>
            </div>
          )}

        {/* Skills change */}
        {diff.skills_change && (
          <div className="space-y-2">
            <h3 className="font-medium text-sm">Skills Change</h3>
            <div className="flex flex-wrap gap-2">
              {diff.skills_change.added?.map((skill, index) => (
                <Badge
                  key={`skill-added-${index}`}
                  className="bg-green-100 text-green-800 border-green-300 hover:bg-green-100"
                >
                  + {skill}
                </Badge>
              ))}
              {diff.skills_change.removed?.map((skill, index) => (
                <Badge
                  key={`skill-removed-${index}`}
                  className="bg-red-100 text-red-800 border-red-300 hover:bg-red-100 line-through decoration-red-400"
                >
                  - {skill}
                </Badge>
              ))}
            </div>
            {diff.skills_change.reordered && (
              <p className="text-xs text-muted-foreground">Skills were reordered.</p>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  )
}
