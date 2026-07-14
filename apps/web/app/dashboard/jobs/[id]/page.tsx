import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { ExternalLink, Send, MapPin, DollarSign, Briefcase } from 'lucide-react'

export default function JobDetailPage({ params }: { params: { id: string } }) {
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Senior Software Engineer</h1>
          <div className="flex items-center gap-4 mt-2 text-muted-foreground">
            <div className="flex items-center gap-1">
              <Briefcase className="h-4 w-4" />
              Google
            </div>
            <div className="flex items-center gap-1">
              <MapPin className="h-4 w-4" />
              Mountain View, CA
            </div>
            <div className="flex items-center gap-1">
              <DollarSign className="h-4 w-4" />
              $180k - $250k
            </div>
          </div>
        </div>
        <div className="flex gap-2">
          <Button variant="outline">
            <ExternalLink className="mr-2 h-4 w-4" />
            View Original
          </Button>
          <Button>
            <Send className="mr-2 h-4 w-4" />
            Prepare Application
          </Button>
        </div>
      </div>

      <div className="grid gap-6 md:grid-cols-3">
        <Card className="md:col-span-2">
          <CardHeader>
            <CardTitle>Job Description</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <h3 className="font-medium mb-2">About the Role</h3>
              <p className="text-sm text-muted-foreground">
                We're looking for a Senior Software Engineer to join our Search Infrastructure team.
                You'll be working on building and scaling systems that power Google Search, serving
                billions of queries daily.
              </p>
            </div>
            <div>
              <h3 className="font-medium mb-2">Requirements</h3>
              <ul className="list-disc list-inside text-sm text-muted-foreground space-y-1">
                <li>5+ years of software development experience</li>
                <li>Strong understanding of distributed systems</li>
                <li>Experience with large-scale backend systems</li>
                <li>Proficiency in C++, Java, or Python</li>
              </ul>
            </div>
            <div>
              <h3 className="font-medium mb-2">Nice to Have</h3>
              <ul className="list-disc list-inside text-sm text-muted-foreground space-y-1">
                <li>Experience with search or information retrieval</li>
                <li>Knowledge of machine learning systems</li>
                <li>Open source contributions</li>
              </ul>
            </div>
          </CardContent>
        </Card>

        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Match Score</CardTitle>
              <CardDescription>Overall fit for this role</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="text-center">
                <div className="text-5xl font-bold text-green-600">92%</div>
                <p className="text-sm text-muted-foreground mt-2">Excellent Match</p>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Match Analysis</CardTitle>
              <CardDescription>Dimension scores</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              <div>
                <div className="flex justify-between text-sm mb-1">
                  <span>Technical Match</span>
                  <span className="font-medium">95%</span>
                </div>
                <div className="h-2 bg-gray-200 rounded-full">
                  <div className="h-2 bg-green-600 rounded-full" style={{ width: '95%' }} />
                </div>
              </div>
              <div>
                <div className="flex justify-between text-sm mb-1">
                  <span>Seniority Match</span>
                  <span className="font-medium">90%</span>
                </div>
                <div className="h-2 bg-gray-200 rounded-full">
                  <div className="h-2 bg-green-600 rounded-full" style={{ width: '90%' }} />
                </div>
              </div>
              <div>
                <div className="flex justify-between text-sm mb-1">
                  <span>Career Trajectory</span>
                  <span className="font-medium">88%</span>
                </div>
                <div className="h-2 bg-gray-200 rounded-full">
                  <div className="h-2 bg-green-600 rounded-full" style={{ width: '88%' }} />
                </div>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Recommended Resume</CardTitle>
            </CardHeader>
            <CardContent>
              <Badge>Software Engineering</Badge>
              <p className="text-sm text-muted-foreground mt-2">
                Best match for this role's requirements
              </p>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  )
}
