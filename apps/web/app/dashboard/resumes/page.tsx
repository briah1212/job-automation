import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Upload, FileText, CheckCircle, XCircle, Clock } from 'lucide-react'
import Link from 'next/link'

const resumes = [
  { id: '1', name: 'Software Engineering', category: 'Backend', status: 'approved_base', created_at: '2024-01-15' },
  { id: '2', name: 'Data Engineering', category: 'Data', status: 'needs_review', created_at: '2024-01-20' },
  { id: '3', name: 'Full Stack', category: 'Web', status: 'uploaded', created_at: '2024-01-22' },
]

export default function ResumesPage() {
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-bold">Resumes</h1>
        <Button>
          <Upload className="mr-2 h-4 w-4" />
          Upload Resume
        </Button>
      </div>

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {resumes.map((resume) => (
          <Card key={resume.id} className="hover:border-primary transition-colors">
            <CardHeader>
              <div className="flex items-start justify-between">
                <FileText className="h-8 w-8 text-primary" />
                <Badge variant={
                  resume.status === 'approved_base' ? 'default' :
                  resume.status === 'needs_review' ? 'secondary' :
                  'outline'
                }>
                  {resume.status === 'approved_base' && <CheckCircle className="mr-1 h-3 w-3" />}
                  {resume.status === 'needs_review' && <Clock className="mr-1 h-3 w-3" />}
                  {resume.status === 'uploaded' && <XCircle className="mr-1 h-3 w-3" />}
                  {resume.status.replace('_', ' ')}
                </Badge>
              </div>
              <CardTitle className="mt-4">{resume.name}</CardTitle>
              <CardDescription>{resume.category}</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-2">
                <p className="text-sm text-muted-foreground">
                  Uploaded {new Date(resume.created_at).toLocaleDateString()}
                </p>
                <Button asChild variant="outline" className="w-full">
                  <Link href={`/dashboard/resumes/${resume.id}`}>View Details</Link>
                </Button>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  )
}
