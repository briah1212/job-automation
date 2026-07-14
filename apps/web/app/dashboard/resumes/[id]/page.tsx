import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { CheckCircle, XCircle, Download, Wand2 } from 'lucide-react'

export default function ResumeDetailPage({ params }: { params: { id: string } }) {
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Software Engineering Resume</h1>
          <p className="text-muted-foreground">Backend focused</p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline">
            <Download className="mr-2 h-4 w-4" />
            Download
          </Button>
          <Button variant="outline">
            <Wand2 className="mr-2 h-4 w-4" />
            Generate Variant
          </Button>
          <Button variant="destructive">
            <XCircle className="mr-2 h-4 w-4" />
            Reject
          </Button>
          <Button>
            <CheckCircle className="mr-2 h-4 w-4" />
            Approve
          </Button>
        </div>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Parsed Resume Data</CardTitle>
          <CardDescription>Extracted information from your resume</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div>
            <h3 className="font-medium mb-2">Work Experience</h3>
            <div className="space-y-3">
              <div className="border-l-2 border-primary pl-4">
                <div className="font-medium">Senior Software Engineer</div>
                <div className="text-sm text-muted-foreground">Google • 2020-2024</div>
                <p className="text-sm mt-1">Led backend infrastructure for search systems...</p>
              </div>
              <div className="border-l-2 border-muted pl-4">
                <div className="font-medium">Software Engineer</div>
                <div className="text-sm text-muted-foreground">Meta • 2018-2020</div>
                <p className="text-sm mt-1">Developed scalable APIs for social features...</p>
              </div>
            </div>
          </div>

          <div>
            <h3 className="font-medium mb-2">Skills</h3>
            <div className="flex flex-wrap gap-2">
              <Badge>Python</Badge>
              <Badge>Go</Badge>
              <Badge>Kubernetes</Badge>
              <Badge>PostgreSQL</Badge>
              <Badge>System Design</Badge>
              <Badge>Distributed Systems</Badge>
            </div>
          </div>

          <div>
            <h3 className="font-medium mb-2">Education</h3>
            <div>
              <div className="font-medium">BS Computer Science</div>
              <div className="text-sm text-muted-foreground">Stanford University • 2018</div>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
