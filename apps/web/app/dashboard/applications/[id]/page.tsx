import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { CheckCircle, Edit, AlertTriangle, FileText, Briefcase } from 'lucide-react'

export default function ApplicationDetailPage({ params }: { params: { id: string } }) {
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Application Review</h1>
          <p className="text-muted-foreground">Google - Senior Software Engineer</p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline">
            <Edit className="mr-2 h-4 w-4" />
            Edit Answers
          </Button>
          <Button>
            <CheckCircle className="mr-2 h-4 w-4" />
            Approve & Submit
          </Button>
        </div>
      </div>

      <div className="grid gap-6 md:grid-cols-3">
        <div className="md:col-span-2 space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Job Details</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              <div className="flex items-center gap-2">
                <Briefcase className="h-4 w-4 text-muted-foreground" />
                <span className="font-medium">Google</span>
                <span className="text-muted-foreground">•</span>
                <span>Senior Software Engineer</span>
              </div>
              <div className="flex gap-2">
                <Badge>92% Match</Badge>
                <Badge variant="outline">Remote</Badge>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Application Questions</CardTitle>
              <CardDescription>AI-generated responses based on your profile</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <div className="flex items-start justify-between">
                  <div className="font-medium text-sm">Why do you want to work at Google?</div>
                  <Badge variant="outline" className="text-xs">low risk</Badge>
                </div>
                <p className="text-sm text-muted-foreground">
                  I&apos;m excited about the opportunity to work on Google Search infrastructure because
                  it aligns perfectly with my experience in building large-scale distributed systems.
                  During my time at [Previous Company], I led similar initiatives that improved system
                  reliability by 40%, and I&apos;m eager to apply those learnings at Google&apos;s scale.
                </p>
              </div>

              <div className="space-y-2">
                <div className="flex items-start justify-between">
                  <div className="font-medium text-sm">Describe your experience with distributed systems</div>
                  <Badge variant="outline" className="text-xs">low risk</Badge>
                </div>
                <p className="text-sm text-muted-foreground">
                  I have 6+ years of hands-on experience designing and implementing distributed systems.
                  Most recently, I architected a microservices platform handling 100K+ RPS, implementing
                  service mesh patterns, distributed tracing, and circuit breakers for fault tolerance.
                </p>
              </div>

              <div className="space-y-2">
                <div className="flex items-start justify-between">
                  <div className="font-medium text-sm">What&apos;s your salary expectation?</div>
                  <Badge variant="secondary" className="text-xs">
                    <AlertTriangle className="mr-1 h-3 w-3" />
                    medium risk
                  </Badge>
                </div>
                <p className="text-sm text-muted-foreground">
                  Based on my experience and the role&apos;s requirements, I&apos;m targeting $200-230K base salary.
                  I&apos;m flexible and open to discussing the complete compensation package.
                </p>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Cover Letter</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-sm text-muted-foreground">
                Dear Hiring Manager,
                <br /><br />
                I&apos;m writing to express my interest in the Senior Software Engineer position at Google.
                With over 6 years of experience building large-scale distributed systems, I&apos;m excited
                about the opportunity to contribute to Google Search infrastructure...
                <br /><br />
                [Full letter would continue here]
              </p>
            </CardContent>
          </Card>
        </div>

        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Status</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <Badge variant="secondary" className="w-full justify-center py-2">
                Needs Review
              </Badge>
              <div className="text-sm text-muted-foreground">
                Review AI-generated responses before submission
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Risk Assessment</CardTitle>
            </CardHeader>
            <CardContent>
              <Badge variant="secondary" className="w-full justify-center py-2">
                <AlertTriangle className="mr-1 h-4 w-4" />
                Medium Risk
              </Badge>
              <div className="mt-3 space-y-2">
                <div className="text-sm">
                  <span className="font-medium">Findings:</span>
                  <ul className="list-disc list-inside text-muted-foreground mt-1 space-y-1">
                    <li>Salary expectation may be high</li>
                    <li>Review work authorization answer</li>
                  </ul>
                </div>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Selected Resume</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="flex items-center gap-2">
                <FileText className="h-4 w-4" />
                <span className="text-sm font-medium">Software Engineering</span>
              </div>
              <Badge variant="outline" className="text-xs">Tailored Variant</Badge>
              <Button variant="outline" size="sm" className="w-full">
                View Resume
              </Button>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  )
}
