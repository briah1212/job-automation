'use client'

import { useEffect, useRef, useState } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Upload, FileText, CheckCircle, Clock, Loader2 } from 'lucide-react'
import Link from 'next/link'
import { apiClient } from '@/lib/api-client'
import type { ResumeFamily, ResumeVersion } from '@/lib/types'

const STATUS_VARIANT: Record<string, 'default' | 'secondary' | 'outline'> = {
  approved: 'default',
  ready: 'default',
  parsed: 'secondary',
  tailoring: 'secondary',
  parsing: 'outline',
  draft: 'outline',
  archived: 'outline',
}

export default function ResumesPage() {
  const [versions, setVersions] = useState<ResumeVersion[]>([])
  const [families, setFamilies] = useState<Record<string, ResumeFamily>>({})
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [uploading, setUploading] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const fetchResumes = async () => {
    try {
      setLoading(true)
      setError(null)
      const [versionsData, familiesData] = await Promise.all([
        apiClient.getResumeVersions(),
        apiClient.getResumes(),
      ])
      setVersions(versionsData)
      setFamilies(
        familiesData.reduce<Record<string, ResumeFamily>>((acc, family) => {
          acc[family.id] = family
          return acc
        }, {})
      )
    } catch (err) {
      setError('Failed to load resumes')
      console.error(err)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchResumes()
  }, [])

  const handleFileSelected = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    e.target.value = ''
    if (!file) return
    try {
      setUploading(true)
      setError(null)
      await apiClient.uploadResume(file)
      await fetchResumes()
    } catch (err) {
      setError('Failed to upload resume')
      console.error(err)
    } finally {
      setUploading(false)
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-bold">Resumes</h1>
        <input
          ref={fileInputRef}
          type="file"
          accept=".pdf,.doc,.docx"
          className="hidden"
          onChange={handleFileSelected}
        />
        <Button onClick={() => fileInputRef.current?.click()} disabled={uploading}>
          {uploading ? (
            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
          ) : (
            <Upload className="mr-2 h-4 w-4" />
          )}
          Upload Resume
        </Button>
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-16">
          <div className="flex flex-col items-center gap-4">
            <Loader2 className="h-8 w-8 animate-spin text-primary" />
            <p className="text-muted-foreground">Loading resumes...</p>
          </div>
        </div>
      ) : error ? (
        <Card className="border-red-200 bg-red-50">
          <CardContent className="pt-6">
            <p className="text-red-800 text-sm">{error}</p>
          </CardContent>
        </Card>
      ) : versions.length === 0 ? (
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-16 text-center gap-2">
            <FileText className="h-10 w-10 text-muted-foreground" />
            <p className="font-medium">No resumes yet</p>
            <p className="text-sm text-muted-foreground max-w-sm">
              Upload a resume to get started. Once uploaded, it will appear here for review and
              tailoring.
            </p>
          </CardContent>
        </Card>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {versions.map((version) => {
            const family = families[version.family_id]
            return (
              <Card key={version.id} className="hover:border-primary transition-colors">
                <CardHeader>
                  <div className="flex items-start justify-between">
                    <FileText className="h-8 w-8 text-primary" />
                    <Badge variant={STATUS_VARIANT[version.status] || 'outline'}>
                      {(version.status === 'approved' || version.status === 'ready') && (
                        <CheckCircle className="mr-1 h-3 w-3" />
                      )}
                      {(version.status === 'parsing' || version.status === 'tailoring') && (
                        <Clock className="mr-1 h-3 w-3" />
                      )}
                      {version.status}
                    </Badge>
                  </div>
                  <CardTitle className="mt-4">
                    {family?.name || (version.parent_id ? 'Tailored Variant' : 'Base Resume')}
                  </CardTitle>
                  <CardDescription>{family?.target_category || 'Uncategorized'}</CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="space-y-2">
                    <p className="text-sm text-muted-foreground">
                      Uploaded {new Date(version.created_at).toLocaleDateString()}
                    </p>
                    <Button asChild variant="outline" className="w-full">
                      <Link href={`/dashboard/resumes/${version.id}`}>View Details</Link>
                    </Button>
                  </div>
                </CardContent>
              </Card>
            )
          })}
        </div>
      )}
    </div>
  )
}
