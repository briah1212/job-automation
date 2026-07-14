import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Briefcase, Send, Calendar, Plus, Upload } from 'lucide-react'
import Link from 'next/link'

export default function DashboardPage() {
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-bold">Dashboard</h1>
        <div className="flex gap-2">
          <Button asChild>
            <Link href="/dashboard/jobs">
              <Plus className="mr-2 h-4 w-4" />
              Import Job
            </Link>
          </Button>
          <Button variant="outline" asChild>
            <Link href="/dashboard/profile">
              <Upload className="mr-2 h-4 w-4" />
              Update Profile
            </Link>
          </Button>
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Jobs Discovered</CardTitle>
            <Briefcase className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">24</div>
            <p className="text-xs text-muted-foreground">+3 this week</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Applications Pending</CardTitle>
            <Send className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">8</div>
            <p className="text-xs text-muted-foreground">4 need review</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Interviews Scheduled</CardTitle>
            <Calendar className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">2</div>
            <p className="text-xs text-muted-foreground">Next: Tomorrow</p>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Recent Jobs</CardTitle>
          <CardDescription>High-match opportunities discovered</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            <div className="flex items-center justify-between border-b pb-4">
              <div>
                <div className="font-medium">Senior Software Engineer</div>
                <div className="text-sm text-muted-foreground">Google • Mountain View, CA</div>
              </div>
              <div className="flex items-center gap-4">
                <div className="text-right">
                  <div className="text-sm font-medium text-green-600">92% Match</div>
                  <div className="text-xs text-muted-foreground">2 hours ago</div>
                </div>
                <Button size="sm">View</Button>
              </div>
            </div>
            <div className="flex items-center justify-between border-b pb-4">
              <div>
                <div className="font-medium">Staff Backend Engineer</div>
                <div className="text-sm text-muted-foreground">Meta • Remote</div>
              </div>
              <div className="flex items-center gap-4">
                <div className="text-right">
                  <div className="text-sm font-medium text-green-600">88% Match</div>
                  <div className="text-xs text-muted-foreground">5 hours ago</div>
                </div>
                <Button size="sm">View</Button>
              </div>
            </div>
            <div className="flex items-center justify-between">
              <div>
                <div className="font-medium">Full Stack Engineer</div>
                <div className="text-sm text-muted-foreground">Stripe • San Francisco, CA</div>
              </div>
              <div className="flex items-center gap-4">
                <div className="text-right">
                  <div className="text-sm font-medium text-yellow-600">75% Match</div>
                  <div className="text-xs text-muted-foreground">1 day ago</div>
                </div>
                <Button size="sm">View</Button>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Application Pipeline</CardTitle>
          <CardDescription>Current status of your applications</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-5 gap-4">
            <div className="text-center">
              <div className="text-2xl font-bold">3</div>
              <div className="text-xs text-muted-foreground">Preparing</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold">4</div>
              <div className="text-xs text-muted-foreground">Needs Review</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold">1</div>
              <div className="text-xs text-muted-foreground">Ready</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold">12</div>
              <div className="text-xs text-muted-foreground">Applied</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold">2</div>
              <div className="text-xs text-muted-foreground">Interview</div>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
