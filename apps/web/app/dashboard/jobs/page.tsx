'use client'

import { useState, useEffect } from 'react'
import { Card } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { Slider } from '@/components/ui/slider'
import { Checkbox } from '@/components/ui/checkbox'
import { Label } from '@/components/ui/label'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Plus, Search, Filter, X, Loader2 } from 'lucide-react'
import Link from 'next/link'
import { apiClient, Job } from '@/lib/api-client'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'

// Available filter options
const CATEGORIES = [
  'Software Engineering',
  'Data Science',
  'Product Management',
  'Design',
  'DevOps',
  'Security',
  'Mobile Development',
  'Frontend',
  'Backend',
  'Full Stack',
]

const REMOTE_POLICIES = [
  { value: 'remote', label: 'Remote' },
  { value: 'hybrid', label: 'Hybrid' },
  { value: 'onsite', label: 'On-site' },
]

const JOB_STATUSES = [
  { value: 'discovered', label: 'Discovered' },
  { value: 'extracting', label: 'Extracting' },
  { value: 'scored', label: 'Scored' },
  { value: 'saved', label: 'Saved' },
  { value: 'shortlisted', label: 'Shortlisted' },
  { value: 'preparing', label: 'Preparing' },
  { value: 'ready_for_review', label: 'Ready for Review' },
  { value: 'approved', label: 'Approved' },
  { value: 'rejected_by_rule', label: 'Rejected' },
  { value: 'archived', label: 'Archived' },
]

type SortOption = 'score' | 'date' | 'salary'

interface Filters {
  categories: string[]
  scoreRange: [number, number]
  location: string
  remotePolicies: string[]
  salaryRange: [number, number]
  statuses: string[]
  hasMatchedResume?: boolean
  search: string
}

export default function JobsPage() {
  const [jobs, setJobs] = useState<Job[]>([])
  const [loading, setLoading] = useState(true)
  const [showFilters, setShowFilters] = useState(true)
  const [sortBy, setSortBy] = useState<SortOption>('score')

  const [importOpen, setImportOpen] = useState(false)
  const [importUrl, setImportUrl] = useState('')
  const [importing, setImporting] = useState(false)
  const [importError, setImportError] = useState<string | null>(null)

  const [filters, setFilters] = useState<Filters>({
    categories: [],
    scoreRange: [0, 100],
    location: '',
    remotePolicies: [],
    salaryRange: [0, 500000],
    statuses: [],
    search: '',
  })

  const fetchJobs = async () => {
    setLoading(true)
    try {
      // The backend's GET /api/jobs only supports status_filter/skip/limit -
      // category, score range, and free-text search have no server-side
      // equivalent, so every filter below is applied client-side over the
      // full job list instead.
      const data = await apiClient.getJobs()
      setJobs(data)
    } catch (error) {
      console.error('Failed to fetch jobs:', error)
    } finally {
      setLoading(false)
    }
  }

  // Fetch the full job list once - all filtering happens client-side in filteredJobs.
  useEffect(() => {
    fetchJobs()
  }, [])

  const normalizeCategory = (value: string) => value.toLowerCase().replace(/[\s_-]+/g, '_')

  const handleImport = async () => {
    if (!importUrl.trim()) return
    try {
      setImporting(true)
      setImportError(null)
      await apiClient.importJob(importUrl.trim())
      setImportUrl('')
      setImportOpen(false)
      await fetchJobs()
    } catch (err) {
      setImportError((err as Error).message || 'Failed to import job')
      console.error(err)
    } finally {
      setImporting(false)
    }
  }

  // All filtering happens client-side - see the comment in fetchJobs.
  const filteredJobs = jobs.filter((job) => {
    // Search filter (title, company, description)
    if (filters.search) {
      const q = filters.search.toLowerCase()
      const haystack = `${job.title} ${job.company} ${job.description ?? ''}`.toLowerCase()
      if (!haystack.includes(q)) {
        return false
      }
    }

    // Category filter - job categories are free-form AI-classified snake_case
    // strings (e.g. "data_engineering"), so compare normalized forms rather
    // than exact matches against the curated Title Case checkbox labels.
    if (filters.categories.length > 0) {
      const jobCategory = job.extracted_data?.category
      const secondaryCategories: string[] = job.extracted_data?.secondary_categories ?? []
      const jobCategories = [jobCategory, ...secondaryCategories].filter(Boolean).map(normalizeCategory)
      const selected = filters.categories.map(normalizeCategory)
      if (!selected.some((c) => jobCategories.includes(c))) {
        return false
      }
    }

    // Match score range filter
    if (job.score != null) {
      if (job.score < filters.scoreRange[0] || job.score > filters.scoreRange[1]) {
        return false
      }
    } else if (filters.scoreRange[0] > 0) {
      // A job with no score yet can't meet a minimum score requirement.
      return false
    }

    // Location filter
    if (filters.location && job.location && !job.location.toLowerCase().includes(filters.location.toLowerCase())) {
      return false
    }

    // Remote policy filter - job.remote_policy is free text (e.g. "Hybrid -
    // 3 days in office"), not one of the three fixed filter values, so match
    // by substring rather than exact equality.
    if (filters.remotePolicies.length > 0) {
      const policy = job.remote_policy?.toLowerCase() ?? ''
      if (!filters.remotePolicies.some((p) => policy.includes(p))) {
        return false
      }
    }

    // Status filter
    if (filters.statuses.length > 0 && !filters.statuses.includes(job.status)) {
      return false
    }

    // Salary range filter
    if (job.salary_min != null && job.salary_min < filters.salaryRange[0]) {
      return false
    }
    if (job.salary_max != null && job.salary_max > filters.salaryRange[1]) {
      return false
    }

    return true
  })

  // Sort jobs
  const sortedJobs = [...filteredJobs].sort((a, b) => {
    switch (sortBy) {
      case 'score':
        return (b.score || 0) - (a.score || 0)
      case 'date':
        return new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
      case 'salary':
        return (b.salary_max || 0) - (a.salary_max || 0)
      default:
        return 0
    }
  })

  // Toggle category filter
  const toggleCategory = (category: string) => {
    setFilters((prev) => ({
      ...prev,
      categories: prev.categories.includes(category)
        ? prev.categories.filter((c) => c !== category)
        : [...prev.categories, category],
    }))
  }

  // Toggle remote policy filter
  const toggleRemotePolicy = (policy: string) => {
    setFilters((prev) => ({
      ...prev,
      remotePolicies: prev.remotePolicies.includes(policy)
        ? prev.remotePolicies.filter((p) => p !== policy)
        : [...prev.remotePolicies, policy],
    }))
  }

  // Toggle status filter
  const toggleStatus = (status: string) => {
    setFilters((prev) => ({
      ...prev,
      statuses: prev.statuses.includes(status)
        ? prev.statuses.filter((s) => s !== status)
        : [...prev.statuses, status],
    }))
  }

  // Clear all filters
  const clearFilters = () => {
    setFilters({
      categories: [],
      scoreRange: [0, 100],
      location: '',
      remotePolicies: [],
      salaryRange: [0, 500000],
      statuses: [],
      search: '',
    })
  }

  // Get score badge variant and color
  const getScoreBadgeVariant = (score: number) => {
    if (score >= 80) return { variant: 'default' as const, color: 'bg-green-500' }
    if (score >= 60) return { variant: 'secondary' as const, color: 'bg-yellow-500' }
    if (score >= 40) return { variant: 'outline' as const, color: 'bg-orange-500' }
    return { variant: 'destructive' as const, color: 'bg-red-500' }
  }

  const hasActiveFilters = 
    filters.categories.length > 0 ||
    filters.scoreRange[0] > 0 ||
    filters.scoreRange[1] < 100 ||
    filters.location !== '' ||
    filters.remotePolicies.length > 0 ||
    filters.salaryRange[0] > 0 ||
    filters.salaryRange[1] < 500000 ||
    filters.statuses.length > 0

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Jobs</h1>
          <p className="text-muted-foreground mt-1">
            {sortedJobs.length} job{sortedJobs.length !== 1 ? 's' : ''} found
          </p>
        </div>
        <Button onClick={() => setImportOpen(true)}>
          <Plus className="mr-2 h-4 w-4" />
          Import Job URL
        </Button>
      </div>

      <Dialog open={importOpen} onOpenChange={setImportOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Import Job from URL</DialogTitle>
            <DialogDescription>
              Paste a job posting URL. It will be extracted and classified in the background.
            </DialogDescription>
          </DialogHeader>
          <Input
            placeholder="https://boards.greenhouse.io/acme/jobs/12345"
            value={importUrl}
            onChange={(e) => setImportUrl(e.target.value)}
          />
          {importError && <p className="text-sm text-red-600">{importError}</p>}
          <DialogFooter>
            <Button variant="outline" onClick={() => setImportOpen(false)} disabled={importing}>
              Cancel
            </Button>
            <Button onClick={handleImport} disabled={importing || !importUrl.trim()}>
              {importing ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
              Import
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Search and Controls */}
      <Card className="p-4">
        <div className="flex gap-4 flex-wrap">
          <div className="relative flex-1 min-w-[240px]">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              placeholder="Search jobs by company, title, or keywords..."
              className="pl-9"
              value={filters.search}
              onChange={(e) => setFilters({ ...filters, search: e.target.value })}
            />
          </div>
          <Button
            variant={showFilters ? 'default' : 'outline'}
            onClick={() => setShowFilters(!showFilters)}
          >
            <Filter className="mr-2 h-4 w-4" />
            Filters
            {hasActiveFilters && (
              <Badge variant="secondary" className="ml-2">
                {filters.categories.length + 
                 filters.remotePolicies.length + 
                 filters.statuses.length + 
                 (filters.location ? 1 : 0)}
              </Badge>
            )}
          </Button>
          <Select value={sortBy} onValueChange={(value) => setSortBy(value as SortOption)}>
            <SelectTrigger className="w-[180px]">
              <SelectValue placeholder="Sort by..." />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="score">Score (High to Low)</SelectItem>
              <SelectItem value="date">Date (Newest First)</SelectItem>
              <SelectItem value="salary">Salary (Highest First)</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </Card>

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        {/* Filters Sidebar */}
        {showFilters && (
          <Card className="p-4 h-fit space-y-6 lg:col-span-1">
            <div className="flex items-center justify-between">
              <h3 className="font-semibold text-lg">Filters</h3>
              {hasActiveFilters && (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={clearFilters}
                  className="h-8 px-2"
                >
                  <X className="h-4 w-4 mr-1" />
                  Clear
                </Button>
              )}
            </div>

            {/* Category Filter */}
            <div className="space-y-3">
              <Label className="text-sm font-semibold">Categories</Label>
              <div className="space-y-2 max-h-48 overflow-y-auto">
                {CATEGORIES.map((category) => (
                  <div key={category} className="flex items-center space-x-2">
                    <Checkbox
                      id={`category-${category}`}
                      checked={filters.categories.includes(category)}
                      onCheckedChange={() => toggleCategory(category)}
                    />
                    <label
                      htmlFor={`category-${category}`}
                      className="text-sm cursor-pointer flex-1"
                    >
                      {category}
                    </label>
                  </div>
                ))}
              </div>
            </div>

            {/* Score Range */}
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <Label className="text-sm font-semibold">Match Score</Label>
                <span className="text-sm text-muted-foreground">
                  {filters.scoreRange[0]}% - {filters.scoreRange[1]}%
                </span>
              </div>
              <Slider
                min={0}
                max={100}
                step={5}
                value={filters.scoreRange}
                onValueChange={(value) =>
                  setFilters({ ...filters, scoreRange: value as [number, number] })
                }
                className="w-full"
              />
            </div>

            {/* Location Filter */}
            <div className="space-y-3">
              <Label className="text-sm font-semibold">Location</Label>
              <Input
                placeholder="City, State, or Country"
                value={filters.location}
                onChange={(e) => setFilters({ ...filters, location: e.target.value })}
              />
            </div>

            {/* Remote Policy Filter */}
            <div className="space-y-3">
              <Label className="text-sm font-semibold">Remote Policy</Label>
              <div className="space-y-2">
                {REMOTE_POLICIES.map(({ value, label }) => (
                  <div key={value} className="flex items-center space-x-2">
                    <Checkbox
                      id={`remote-${value}`}
                      checked={filters.remotePolicies.includes(value)}
                      onCheckedChange={() => toggleRemotePolicy(value)}
                    />
                    <label
                      htmlFor={`remote-${value}`}
                      className="text-sm cursor-pointer flex-1"
                    >
                      {label}
                    </label>
                  </div>
                ))}
              </div>
            </div>

            {/* Salary Range */}
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <Label className="text-sm font-semibold">Salary Range</Label>
                <span className="text-sm text-muted-foreground">
                  ${(filters.salaryRange[0] / 1000).toFixed(0)}k - $
                  {(filters.salaryRange[1] / 1000).toFixed(0)}k
                </span>
              </div>
              <Slider
                min={0}
                max={500000}
                step={10000}
                value={filters.salaryRange}
                onValueChange={(value) =>
                  setFilters({ ...filters, salaryRange: value as [number, number] })
                }
                className="w-full"
              />
            </div>

            {/* Status Filter */}
            <div className="space-y-3">
              <Label className="text-sm font-semibold">Status</Label>
              <div className="space-y-2">
                {JOB_STATUSES.map(({ value, label }) => (
                  <div key={value} className="flex items-center space-x-2">
                    <Checkbox
                      id={`status-${value}`}
                      checked={filters.statuses.includes(value)}
                      onCheckedChange={() => toggleStatus(value)}
                    />
                    <label
                      htmlFor={`status-${value}`}
                      className="text-sm cursor-pointer flex-1"
                    >
                      {label}
                    </label>
                  </div>
                ))}
              </div>
            </div>
          </Card>
        )}

        {/* Jobs Table */}
        <Card className={showFilters ? 'lg:col-span-3' : 'lg:col-span-4'}>
          {loading ? (
            <div className="p-8 text-center text-muted-foreground">
              Loading jobs...
            </div>
          ) : sortedJobs.length === 0 ? (
            <div className="p-8 text-center text-muted-foreground">
              No jobs found. Try adjusting your filters.
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Company</TableHead>
                  <TableHead>Title</TableHead>
                  <TableHead>Location</TableHead>
                  <TableHead>Match Score</TableHead>
                  <TableHead>Details</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {sortedJobs.map((job) => {
                  const scoreBadge = job.score ? getScoreBadgeVariant(job.score) : null

                  return (
                    <TableRow key={job.id}>
                      <TableCell className="font-medium max-w-[200px] truncate">{job.company}</TableCell>
                      <TableCell className="max-w-[240px] truncate">{job.title}</TableCell>
                      <TableCell>
                        <div className="space-y-1">
                          <div className="text-sm">{job.location || 'Not specified'}</div>
                          {job.remote_policy && (
                            <Badge variant="outline" className="text-xs">
                              {job.remote_policy}
                            </Badge>
                          )}
                        </div>
                      </TableCell>
                      <TableCell>
                        {job.score && scoreBadge ? (
                          <div className="flex items-center gap-2">
                            <div
                              className={`w-2 h-2 rounded-full ${scoreBadge.color}`}
                              title={
                                job.score >= 80
                                  ? 'Excellent match'
                                  : job.score >= 60
                                  ? 'Good match'
                                  : job.score >= 40
                                  ? 'Fair match'
                                  : 'Poor match'
                              }
                            />
                            <Badge variant={scoreBadge.variant}>{job.score}%</Badge>
                          </div>
                        ) : (
                          <span className="text-muted-foreground">—</span>
                        )}
                      </TableCell>
                      <TableCell>
                        <div className="space-y-1 text-sm">
                          {job.salary_min && job.salary_max && (
                            <div className="text-muted-foreground">
                              ${(job.salary_min / 1000).toFixed(0)}k - $
                              {(job.salary_max / 1000).toFixed(0)}k
                            </div>
                          )}
                        </div>
                      </TableCell>
                      <TableCell>
                        <Badge
                          variant={
                            job.status === 'approved'
                              ? 'default'
                              : job.status === 'rejected_by_rule'
                              ? 'destructive'
                              : 'outline'
                          }
                        >
                          {job.status.replace(/_/g, ' ')}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-right">
                        <Button asChild variant="outline" size="sm">
                          <Link href={`/dashboard/jobs/${job.id}`}>View</Link>
                        </Button>
                      </TableCell>
                    </TableRow>
                  )
                })}
              </TableBody>
            </Table>
          )}
        </Card>
      </div>
    </div>
  )
}
