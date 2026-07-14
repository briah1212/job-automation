'use client'

import { useState, useEffect } from 'react'
import { Card } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Checkbox } from '@/components/ui/checkbox'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Plus, Edit, Trash2 } from 'lucide-react'
import Link from 'next/link'
import { apiClient } from '@/lib/api-client'
import type { SearchProfile } from '@/lib/types'

export default function SearchProfilesPage() {
  const [profiles, setProfiles] = useState<SearchProfile[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    loadProfiles()
  }, [])

  const loadProfiles = async () => {
    try {
      setLoading(true)
      setError(null)
      const data = await apiClient.getSearchProfiles()
      setProfiles(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load search profiles')
    } finally {
      setLoading(false)
    }
  }

  const handleToggleEnabled = async (id: string, currentEnabled: boolean) => {
    try {
      await apiClient.toggleSearchProfile(id, !currentEnabled)
      setProfiles(profiles.map(p => 
        p.id === id ? { ...p, enabled: !currentEnabled } : p
      ))
    } catch (err) {
      alert('Failed to toggle profile')
    }
  }

  const handleDelete = async (id: string) => {
    if (!confirm('Are you sure you want to delete this search profile?')) {
      return
    }

    try {
      await apiClient.deleteSearchProfile(id)
      setProfiles(profiles.filter(p => p.id !== id))
    } catch (err) {
      alert('Failed to delete profile')
    }
  }

  if (loading) {
    return (
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <h1 className="text-3xl font-bold">Search Profiles</h1>
        </div>
        <Card className="p-8">
          <p className="text-center text-muted-foreground">Loading search profiles...</p>
        </Card>
      </div>
    )
  }

  if (error) {
    return (
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <h1 className="text-3xl font-bold">Search Profiles</h1>
        </div>
        <Card className="p-8">
          <p className="text-center text-red-500">Error: {error}</p>
          <div className="flex justify-center mt-4">
            <Button onClick={loadProfiles}>Retry</Button>
          </div>
        </Card>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-bold">Search Profiles</h1>
        <Button asChild>
          <Link href="/dashboard/search-profiles/new">
            <Plus className="mr-2 h-4 w-4" />
            Create New Profile
          </Link>
        </Button>
      </div>

      {profiles.length === 0 ? (
        <Card className="p-8">
          <div className="text-center">
            <p className="text-muted-foreground mb-4">No search profiles yet</p>
            <Button asChild>
              <Link href="/dashboard/search-profiles/new">
                <Plus className="mr-2 h-4 w-4" />
                Create Your First Profile
              </Link>
            </Button>
          </div>
        </Card>
      ) : (
        <Card>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Enabled</TableHead>
                <TableHead>Name</TableHead>
                <TableHead>Categories</TableHead>
                <TableHead>Skills</TableHead>
                <TableHead>Locations</TableHead>
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {profiles.map((profile) => (
                <TableRow key={profile.id}>
                  <TableCell>
                    <Checkbox
                      checked={profile.enabled}
                      onCheckedChange={() => handleToggleEnabled(profile.id, profile.enabled)}
                    />
                  </TableCell>
                  <TableCell className="font-medium">{profile.name}</TableCell>
                  <TableCell>
                    <div className="flex flex-wrap gap-1">
                      {profile.career_categories.slice(0, 3).map((category, idx) => (
                        <Badge key={idx} variant="secondary">
                          {category}
                        </Badge>
                      ))}
                      {profile.career_categories.length > 3 && (
                        <Badge variant="outline">
                          +{profile.career_categories.length - 3}
                        </Badge>
                      )}
                    </div>
                  </TableCell>
                  <TableCell>
                    <span className="text-muted-foreground">
                      {profile.include_skills.length} skill{profile.include_skills.length !== 1 ? 's' : ''}
                    </span>
                  </TableCell>
                  <TableCell>
                    <span className="text-muted-foreground">
                      {profile.locations.length} location{profile.locations.length !== 1 ? 's' : ''}
                    </span>
                  </TableCell>
                  <TableCell className="text-right">
                    <div className="flex justify-end gap-2">
                      <Button asChild variant="outline" size="sm">
                        <Link href={`/dashboard/search-profiles/${profile.id}/edit`}>
                          <Edit className="h-4 w-4" />
                        </Link>
                      </Button>
                      <Button 
                        variant="outline" 
                        size="sm"
                        onClick={() => handleDelete(profile.id)}
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </div>
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
