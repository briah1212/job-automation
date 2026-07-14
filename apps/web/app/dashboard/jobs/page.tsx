import { Card } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Plus, Search } from 'lucide-react'
import Link from 'next/link'

const jobs = [
  { id: '1', company: 'Google', title: 'Senior Software Engineer', location: 'Mountain View, CA', score: 92, status: 'scored' },
  { id: '2', company: 'Meta', title: 'Staff Backend Engineer', location: 'Remote', score: 88, status: 'scored' },
  { id: '3', company: 'Stripe', title: 'Full Stack Engineer', location: 'San Francisco, CA', score: 75, status: 'scored' },
  { id: '4', company: 'Netflix', title: 'Principal Engineer', location: 'Los Gatos, CA', score: 85, status: 'scored' },
  { id: '5', company: 'Amazon', title: 'Software Development Engineer III', location: 'Seattle, WA', score: 70, status: 'new' },
]

export default function JobsPage() {
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-bold">Jobs</h1>
        <Button>
          <Plus className="mr-2 h-4 w-4" />
          Import Job URL
        </Button>
      </div>

      <Card className="p-4">
        <div className="flex gap-4">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input placeholder="Search jobs..." className="pl-9" />
          </div>
          <Button variant="outline">Filters</Button>
        </div>
      </Card>

      <Card>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Company</TableHead>
              <TableHead>Title</TableHead>
              <TableHead>Location</TableHead>
              <TableHead>Match Score</TableHead>
              <TableHead>Status</TableHead>
              <TableHead className="text-right">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {jobs.map((job) => (
              <TableRow key={job.id}>
                <TableCell className="font-medium">{job.company}</TableCell>
                <TableCell>{job.title}</TableCell>
                <TableCell>{job.location}</TableCell>
                <TableCell>
                  {job.score ? (
                    <Badge variant={
                      job.score >= 85 ? 'default' :
                      job.score >= 70 ? 'secondary' :
                      'outline'
                    }>
                      {job.score}%
                    </Badge>
                  ) : (
                    <span className="text-muted-foreground">—</span>
                  )}
                </TableCell>
                <TableCell>
                  <Badge variant="outline">{job.status}</Badge>
                </TableCell>
                <TableCell className="text-right">
                  <Button asChild variant="outline" size="sm">
                    <Link href={`/dashboard/jobs/${job.id}`}>View</Link>
                  </Button>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </Card>
    </div>
  )
}
