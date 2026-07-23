'use client'

import { useEffect, useState } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Checkbox } from '@/components/ui/checkbox'
import { Badge } from '@/components/ui/badge'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Loader2, Plus, Trash2 } from 'lucide-react'
import { apiClient } from '@/lib/api-client'
import type { CompanyWatch } from '@/lib/types'

const ATS_PLATFORMS = ['greenhouse', 'lever', 'ashby']

export default function CompanyWatchesPage() {
  const [watches, setWatches] = useState<CompanyWatch[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const [companyName, setCompanyName] = useState('')
  const [atsPlatform, setAtsPlatform] = useState(ATS_PLATFORMS[0])
  const [boardIdentifier, setBoardIdentifier] = useState('')
  const [creating, setCreating] = useState(false)

  const load = async () => {
    try {
      setLoading(true)
      setError(null)
      const data = await apiClient.getCompanyWatches()
      setWatches(data)
    } catch (err) {
      setError('Failed to load company watches')
      console.error(err)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
  }, [])

  const handleCreate = async () => {
    if (!companyName.trim() || !boardIdentifier.trim()) return
    try {
      setCreating(true)
      setError(null)
      const watch = await apiClient.createCompanyWatch({
        company_name: companyName.trim(),
        ats_platform: atsPlatform,
        board_identifier: boardIdentifier.trim(),
        enabled: true,
      })
      setWatches((prev) => [...prev, watch].sort((a, b) => a.company_name.localeCompare(b.company_name)))
      setCompanyName('')
      setBoardIdentifier('')
    } catch (err) {
      setError((err as Error).message || 'Failed to create company watch')
      console.error(err)
    } finally {
      setCreating(false)
    }
  }

  const handleToggle = async (watch: CompanyWatch) => {
    try {
      const updated = await apiClient.updateCompanyWatch(watch.id, { enabled: !watch.enabled })
      setWatches((prev) => prev.map((w) => (w.id === watch.id ? updated : w)))
    } catch (err) {
      setError('Failed to update company watch')
      console.error(err)
    }
  }

  const handleDelete = async (id: string) => {
    if (!confirm('Delete this company watch?')) return
    try {
      await apiClient.deleteCompanyWatch(id)
      setWatches((prev) => prev.filter((w) => w.id !== id))
    } catch (err) {
      setError('Failed to delete company watch')
      console.error(err)
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold">Company Watches</h1>
        <p className="text-muted-foreground">
          Companies whose job boards are automatically polled for new postings
        </p>
      </div>

      {error && (
        <Card className="border-red-200 bg-red-50">
          <CardContent className="pt-6">
            <p className="text-sm text-red-800">{error}</p>
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <CardTitle>Add a Watch</CardTitle>
          <CardDescription>
            The board identifier is the company&apos;s slug on the ATS (e.g. Greenhouse&apos;s &quot;acme&quot; in boards.greenhouse.io/acme)
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid gap-4 md:grid-cols-4 items-end">
            <div className="space-y-2">
              <Label htmlFor="company_name">Company Name</Label>
              <Input
                id="company_name"
                value={companyName}
                onChange={(e) => setCompanyName(e.target.value)}
                placeholder="Acme Corp"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="ats_platform">ATS Platform</Label>
              <Select value={atsPlatform} onValueChange={setAtsPlatform}>
                <SelectTrigger id="ats_platform">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {ATS_PLATFORMS.map((platform) => (
                    <SelectItem key={platform} value={platform}>
                      {platform}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="board_identifier">Board Identifier</Label>
              <Input
                id="board_identifier"
                value={boardIdentifier}
                onChange={(e) => setBoardIdentifier(e.target.value)}
                placeholder="acme"
              />
            </div>
            <Button onClick={handleCreate} disabled={creating || !companyName.trim() || !boardIdentifier.trim()}>
              {creating ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <Plus className="mr-2 h-4 w-4" />
              )}
              Add
            </Button>
          </div>
        </CardContent>
      </Card>

      {loading ? (
        <Card className="p-8">
          <div className="flex justify-center">
            <Loader2 className="h-6 w-6 animate-spin text-primary" />
          </div>
        </Card>
      ) : watches.length === 0 ? (
        <Card className="p-8">
          <p className="text-center text-muted-foreground">No company watches configured yet</p>
        </Card>
      ) : (
        <Card>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Enabled</TableHead>
                <TableHead>Company</TableHead>
                <TableHead>Platform</TableHead>
                <TableHead>Board</TableHead>
                <TableHead>Last Polled</TableHead>
                <TableHead>Status</TableHead>
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {watches.map((watch) => (
                <TableRow key={watch.id}>
                  <TableCell>
                    <Checkbox checked={watch.enabled} onCheckedChange={() => handleToggle(watch)} />
                  </TableCell>
                  <TableCell className="font-medium max-w-[200px] truncate">{watch.company_name}</TableCell>
                  <TableCell className="capitalize">{watch.ats_platform}</TableCell>
                  <TableCell className="text-muted-foreground">{watch.board_identifier}</TableCell>
                  <TableCell className="text-muted-foreground text-sm">
                    {watch.last_polled_at ? new Date(watch.last_polled_at).toLocaleString() : 'Never'}
                  </TableCell>
                  <TableCell>
                    {watch.last_poll_error ? (
                      <Badge variant="outline" className="border-red-300 bg-red-50 text-red-700">
                        Error
                      </Badge>
                    ) : (
                      <Badge variant="outline" className="border-green-300 bg-green-50 text-green-700">
                        OK
                      </Badge>
                    )}
                  </TableCell>
                  <TableCell className="text-right">
                    <Button variant="outline" size="sm" onClick={() => handleDelete(watch.id)}>
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Card>
      )}
    </div>
  )
}
