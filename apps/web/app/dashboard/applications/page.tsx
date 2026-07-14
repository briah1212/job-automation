import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import Link from 'next/link'
import { AlertTriangle, CheckCircle } from 'lucide-react'

const applications = [
  { id: '1', company: 'Google', title: 'Senior SWE', status: 'preparing', risk: 'low' },
  { id: '2', company: 'Meta', title: 'Staff Backend', status: 'needs_review', risk: 'medium' },
  { id: '3', company: 'Stripe', title: 'Full Stack', status: 'needs_review', risk: 'high' },
  { id: '4', company: 'Netflix', title: 'Principal Eng', status: 'ready', risk: 'low' },
  { id: '5', company: 'Amazon', title: 'SDE III', status: 'applied', risk: null },
]

export default function ApplicationsPage() {
  const groupedByStatus = {
    preparing: applications.filter(a => a.status === 'preparing'),
    needs_review: applications.filter(a => a.status === 'needs_review'),
    ready: applications.filter(a => a.status === 'ready'),
    applied: applications.filter(a => a.status === 'applied'),
    interview: applications.filter(a => a.status === 'interview'),
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-bold">Applications</h1>
      </div>

      <Tabs defaultValue="kanban">
        <TabsList>
          <TabsTrigger value="kanban">Kanban View</TabsTrigger>
          <TabsTrigger value="table">Table View</TabsTrigger>
        </TabsList>

        <TabsContent value="kanban" className="mt-6">
          <div className="grid gap-4 md:grid-cols-5">
            {Object.entries(groupedByStatus).map(([status, apps]) => (
              <div key={status}>
                <div className="mb-4">
                  <h3 className="font-medium capitalize">{status.replace('_', ' ')}</h3>
                  <p className="text-sm text-muted-foreground">{apps.length} applications</p>
                </div>
                <div className="space-y-3">
                  {apps.map(app => (
                    <Card key={app.id} className="hover:border-primary transition-colors">
                      <CardHeader className="p-4">
                        <div className="flex items-start justify-between">
                          <div>
                            <CardTitle className="text-sm">{app.company}</CardTitle>
                            <CardDescription className="text-xs">{app.title}</CardDescription>
                          </div>
                          {app.risk && (
                            <Badge variant={
                              app.risk === 'high' ? 'destructive' :
                              app.risk === 'medium' ? 'secondary' :
                              'outline'
                            } className="text-xs">
                              {app.risk === 'high' && <AlertTriangle className="mr-1 h-3 w-3" />}
                              {app.risk === 'low' && <CheckCircle className="mr-1 h-3 w-3" />}
                              {app.risk}
                            </Badge>
                          )}
                        </div>
                      </CardHeader>
                      <CardContent className="p-4 pt-0">
                        <Button asChild variant="outline" size="sm" className="w-full">
                          <Link href={`/dashboard/applications/${app.id}`}>View</Link>
                        </Button>
                      </CardContent>
                    </Card>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </TabsContent>

        <TabsContent value="table" className="mt-6">
          <Card>
            <CardContent className="p-6">
              <p className="text-center text-muted-foreground">Table view coming soon</p>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  )
}
