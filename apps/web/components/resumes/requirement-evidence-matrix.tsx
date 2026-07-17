'use client'

import { useState } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { ChevronDown, ChevronUp } from 'lucide-react'
import type { RequirementEvidenceItem } from '@/lib/types'

interface RequirementEvidenceMatrixProps {
  items: RequirementEvidenceItem[]
}

export function RequirementEvidenceMatrix({ items }: RequirementEvidenceMatrixProps) {
  const [expanded, setExpanded] = useState<Set<number>>(new Set())

  const toggleExpanded = (index: number) => {
    setExpanded((prev) => {
      const next = new Set(prev)
      if (next.has(index)) {
        next.delete(index)
      } else {
        next.add(index)
      }
      return next
    })
  }

  const getCoverageBadgeClass = (coverage: RequirementEvidenceItem['coverage']): string => {
    switch (coverage) {
      case 'strong':
        return 'bg-green-100 text-green-800 border-green-300 hover:bg-green-100'
      case 'partial':
        return 'bg-yellow-100 text-yellow-800 border-yellow-300 hover:bg-yellow-100'
      case 'none':
      default:
        return 'bg-gray-100 text-gray-800 border-gray-300 hover:bg-gray-100'
    }
  }

  if (!items || items.length === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Requirement Evidence Matrix</CardTitle>
          <CardDescription>No requirement evidence available</CardDescription>
        </CardHeader>
      </Card>
    )
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Requirement Evidence Matrix</CardTitle>
        <CardDescription>
          How each job requirement is supported by evidence from your profile
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        {items.map((item, index) => {
          const isExpanded = expanded.has(index)
          return (
            <div key={index} className="border rounded-md">
              <button
                type="button"
                onClick={() => toggleExpanded(index)}
                className="w-full flex items-center justify-between gap-3 p-3 text-left hover:bg-muted/50 transition-colors"
                aria-expanded={isExpanded}
              >
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium truncate">{item.requirement}</p>
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  <Badge variant={item.importance === 'required' ? 'default' : 'outline'}>
                    {item.importance}
                  </Badge>
                  <Badge className={getCoverageBadgeClass(item.coverage)}>
                    {item.coverage}
                  </Badge>
                  {isExpanded ? (
                    <ChevronUp className="h-4 w-4 text-muted-foreground" />
                  ) : (
                    <ChevronDown className="h-4 w-4 text-muted-foreground" />
                  )}
                </div>
              </button>
              {isExpanded && (
                <div className="border-t p-3 space-y-2 bg-muted/20">
                  {item.evidence && item.evidence.length > 0 ? (
                    item.evidence.map((evidence, evidenceIndex) => (
                      <div
                        key={evidenceIndex}
                        className="flex items-start justify-between gap-3 text-sm border-l-2 border-primary/50 pl-3"
                      >
                        <div className="flex-1">
                          <p className="text-muted-foreground">{evidence.explanation}</p>
                          <p className="text-xs text-muted-foreground/70 mt-1">
                            Profile fact: {evidence.profile_fact_id}
                          </p>
                        </div>
                        <Badge variant="outline" className="shrink-0">
                          strength {Math.round(evidence.strength * 100)}%
                        </Badge>
                      </div>
                    ))
                  ) : (
                    <p className="text-sm text-muted-foreground">No supporting evidence found</p>
                  )}
                </div>
              )}
            </div>
          )
        })}
      </CardContent>
    </Card>
  )
}
