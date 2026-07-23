import { getSession, signOut } from 'next-auth/react'
import type {
  Profile,
  ProfileUpdate,
  Job,
  Application,
  ResumeFamily,
  ResumeVersion,
  JobFilters,
  SearchProfile,
  SearchProfileCreate,
  SearchProfileUpdate,
  JobMatchScore,
  ResumeSelectionResult,
  ResumeTailorResponse,
  ResumeDiff,
  DocumentRendering,
  DocumentLock,
  ApplicationQuestionWithAnswer,
  ReusableAnswer,
  ReusableAnswerCreate,
  ReusableAnswerUpdate,
  ApplicationReviewResult,
  ApplicationReviewRequest,
  ApplicationApproveRequest,
  CoverLetter,
  BrowserStatus,
  BrowserTaskResponse,
  CompanyWatch,
  CompanyWatchCreate,
  CompanyWatchUpdate,
} from './types'

// FastAPI's `detail` is a plain string for HTTPException, but a list of
// {loc, msg, type} objects for Pydantic validation errors (422s) - without
// this, those surfaced as the literal text "[object Object]".
function formatErrorDetail(detail: unknown): string {
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) {
    const messages = detail
      .map((item) => (item && typeof item === 'object' && 'msg' in item ? String((item as { msg: unknown }).msg) : null))
      .filter((msg): msg is string => Boolean(msg))
    if (messages.length > 0) return messages.join('; ')
  }
  return 'Request failed'
}

class APIClient {
  private baseURL: string

  constructor() {
    this.baseURL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
  }

  private async request<T>(
    path: string,
    options: RequestInit = {}
  ): Promise<T> {
    const url = `${this.baseURL}${path}`

    const session = await getSession()
    const authHeader: Record<string, string> = session?.accessToken
      ? { Authorization: `Bearer ${session.accessToken}` }
      : {}

    const response = await fetch(url, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...authHeader,
        ...options.headers,
      },
      credentials: 'include',
    })

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Request failed' }))
      const err = new Error(formatErrorDetail(error.detail)) as Error & { status?: number }
      err.status = response.status

      // The session cookie can still look valid (NextAuth's own JWT hasn't
      // expired) while the backend access token embedded in it has - that's
      // a 401 the user can only resolve by logging in again, not something
      // any page's own error state should try to explain.
      if (response.status === 401 && typeof window !== 'undefined') {
        signOut({ callbackUrl: '/auth/login' })
      }

      throw err
    }

    if (response.status === 204) {
      return undefined as T
    }

    const contentType = response.headers.get('content-type') || ''
    if (contentType.includes('text/html')) {
      return (await response.text()) as unknown as T
    }

    return response.json()
  }

  async get<T>(path: string): Promise<T> {
    return this.request<T>(path, { method: 'GET' })
  }

  async post<T>(path: string, data?: any): Promise<T> {
    return this.request<T>(path, {
      method: 'POST',
      body: data !== undefined ? JSON.stringify(data) : undefined,
    })
  }

  async put<T>(path: string, data: any): Promise<T> {
    return this.request<T>(path, {
      method: 'PUT',
      body: JSON.stringify(data),
    })
  }

  async patch<T>(path: string, data: any): Promise<T> {
    return this.request<T>(path, {
      method: 'PATCH',
      body: JSON.stringify(data),
    })
  }

  async delete<T>(path: string): Promise<T> {
    return this.request<T>(path, { method: 'DELETE' })
  }

  // Auth (registration goes directly through app/auth/register/page.tsx and
  // login through NextAuth's CredentialsProvider in lib/auth.ts - neither
  // uses this client, since both need the OAuth2PasswordRequestForm /
  // form-urlencoded body shape the real backend requires).

  // Profile
  async getProfile() {
    return this.get<Profile>('/api/profile')
  }

  async updateProfile(data: ProfileUpdate) {
    return this.put<Profile>('/api/profile', data)
  }

  // Resumes
  async getResumes() {
    return this.get<ResumeFamily[]>('/api/resumes')
  }

  async getResumeVersions() {
    return this.get<ResumeVersion[]>('/api/resumes/versions')
  }

  async uploadResume(file: File) {
    const formData = new FormData()
    formData.append('file', file)

    const session = await getSession()
    const authHeader: Record<string, string> = session?.accessToken
      ? { Authorization: `Bearer ${session.accessToken}` }
      : {}

    const response = await fetch(`${this.baseURL}/api/resumes`, {
      method: 'POST',
      headers: authHeader,
      body: formData,
      credentials: 'include',
    })

    if (!response.ok) {
      throw new Error('Upload failed')
    }

    return response.json() as Promise<{ family: ResumeFamily; version: ResumeVersion }>
  }

  async approveResume(id: string) {
    return this.post<ResumeFamily>(`/api/resumes/${id}/approve`)
  }

  // Jobs
  async getJobs(filters?: JobFilters) {
    const params = new URLSearchParams()
    if (filters) {
      Object.entries(filters).forEach(([key, value]) => {
        if (value !== undefined) params.append(key, String(value))
      })
    }
    return this.get<Job[]>(`/api/jobs?${params}`)
  }

  async getJob(id: string) {
    return this.get<Job>(`/api/jobs/${id}`)
  }

  async importJob(url: string) {
    return this.post<Job>('/api/jobs/import-url', { url })
  }

  async scoreJob(id: string, score?: number) {
    return this.post<Job>(`/api/jobs/${id}/score`, { score })
  }

  // Applications
  async getApplications() {
    return this.get<Application[]>('/api/applications')
  }

  async getApplication(id: string) {
    return this.get<Application>(`/api/applications/${id}`)
  }

  async createApplication(jobId: string, resumeVersionId?: string) {
    return this.post<Application>('/api/applications', {
      job_id: jobId,
      resume_version_id: resumeVersionId,
    })
  }

  async reviewApplication(id: string, data: ApplicationReviewRequest) {
    return this.post<Application>(`/api/applications/${id}/review`, data)
  }

  async approveApplication(id: string, data: ApplicationApproveRequest = { approved: true }) {
    return this.post<Application>(`/api/applications/${id}/approve`, data)
  }

  // Search Profiles
  async getSearchProfiles() {
    return this.get<SearchProfile[]>('/api/search-profiles')
  }

  async getSearchProfile(id: string) {
    return this.get<SearchProfile>(`/api/search-profiles/${id}`)
  }

  async createSearchProfile(data: SearchProfileCreate) {
    return this.post<SearchProfile>('/api/search-profiles', data)
  }

  async updateSearchProfile(id: string, data: SearchProfileUpdate) {
    return this.patch<SearchProfile>(`/api/search-profiles/${id}`, data)
  }

  async deleteSearchProfile(id: string) {
    return this.delete(`/api/search-profiles/${id}`)
  }

  async toggleSearchProfile(id: string, enabled: boolean) {
    return this.patch<SearchProfile>(`/api/search-profiles/${id}`, { enabled })
  }

  // Matching
  async calculateMatchScore(jobId: string) {
    return this.post<JobMatchScore>(`/api/jobs/${jobId}/match`, {})
  }

  async getMatchScore(jobId: string) {
    return this.get<JobMatchScore>(`/api/jobs/${jobId}/match`)
  }

  async selectResume(jobId: string) {
    return this.post<ResumeSelectionResult>(`/api/jobs/${jobId}/select-resume`, {})
  }

  // Resume Tailoring
  async tailorResume(resumeVersionId: string, jobId: string) {
    return this.post<ResumeTailorResponse>(`/api/resumes/${resumeVersionId}/tailor`, { job_id: jobId })
  }

  async getResumeDiff(resumeVersionId: string, baseVersionId: string) {
    return this.get<ResumeDiff>(`/api/resumes/${resumeVersionId}/diff?base_version_id=${baseVersionId}`)
  }

  async renderResume(resumeVersionId: string, format: "pdf" | "docx" = "pdf") {
    return this.post<DocumentRendering>(`/api/resumes/${resumeVersionId}/render`, { format })
  }

  async createResumeLock(familyId: string, lock: { lock_type: string; target_ref: string; value?: Record<string, any> }) {
    return this.post<DocumentLock>(`/api/resumes/families/${familyId}/locks`, lock)
  }

  async getResumeLocks(familyId: string) {
    return this.get<DocumentLock[]>(`/api/resumes/families/${familyId}/locks`)
  }

  // Application Q&A
  async generateApplicationQA(applicationId: string, questionTexts?: string[]) {
    return this.post<ApplicationQuestionWithAnswer[]>(`/api/applications/${applicationId}/generate`, {
      question_texts: questionTexts,
    })
  }

  async getApplicationQuestions(applicationId: string) {
    return this.get<ApplicationQuestionWithAnswer[]>(`/api/applications/${applicationId}/questions`)
  }

  async updateApplicationAnswer(applicationId: string, questionId: string, answerText: string) {
    return this.patch<ApplicationQuestionWithAnswer>(`/api/applications/${applicationId}/questions/${questionId}`, { answer_text: answerText })
  }

  // Reusable Answers
  async getReusableAnswers() {
    return this.get<ReusableAnswer[]>('/api/reusable-answers')
  }

  async createReusableAnswer(data: ReusableAnswerCreate) {
    return this.post<ReusableAnswer>('/api/reusable-answers', data)
  }

  async updateReusableAnswer(id: string, data: ReusableAnswerUpdate) {
    return this.patch<ReusableAnswer>(`/api/reusable-answers/${id}`, data)
  }

  async deleteReusableAnswer(id: string) {
    return this.delete(`/api/reusable-answers/${id}`)
  }

  // Application Review
  async autoReviewApplication(applicationId: string) {
    return this.post<ApplicationReviewResult>(`/api/applications/${applicationId}/auto-review`)
  }

  async getReviewResult(applicationId: string) {
    return this.get<ApplicationReviewResult>(`/api/applications/${applicationId}/review-result`)
  }

  // Cover Letter
  async generateCoverLetter(applicationId: string, options?: { tone?: string; word_limit?: number }) {
    return this.post<CoverLetter>(`/api/applications/${applicationId}/cover-letter`, options || {})
  }

  async getCoverLetter(applicationId: string) {
    return this.get<CoverLetter>(`/api/applications/${applicationId}/cover-letter`)
  }

  async updateCoverLetter(applicationId: string, content: string) {
    return this.patch<CoverLetter>(`/api/applications/${applicationId}/cover-letter`, { content })
  }

  // Browser Automation
  async startBrowserAutomation(applicationId: string) {
    return this.post<BrowserTaskResponse>(`/api/applications/${applicationId}/start-browser`)
  }

  async getBrowserStatus(applicationId: string) {
    return this.get<BrowserStatus>(`/api/applications/${applicationId}/browser-status`)
  }

  async approveSubmit(applicationId: string) {
    return this.post<BrowserTaskResponse>(`/api/applications/${applicationId}/approve-submit`)
  }

  async resumeManualIntervention(applicationId: string) {
    return this.post<BrowserTaskResponse>(`/api/applications/${applicationId}/resume-manual-intervention`)
  }

  async answerPendingQuestion(applicationId: string, answerText: string) {
    return this.post<BrowserTaskResponse>(`/api/applications/${applicationId}/answer-pending-question`, {
      answer_text: answerText,
    })
  }

  async cancelBrowserAutomation(applicationId: string) {
    return this.post<{ id: string; status: string }>(`/api/applications/${applicationId}/cancel-browser`)
  }

  // The replay endpoint requires the same Bearer auth as everything else, so
  // a plain <a href> can't hit it directly - fetch the HTML and hand callers
  // a blob: URL they can window.open() instead.
  async getReplayReportUrl(applicationId: string) {
    const html = await this.get<string>(`/api/applications/${applicationId}/replay`)
    const blob = new Blob([html], { type: 'text/html' })
    return URL.createObjectURL(blob)
  }

  // Company Watches
  async getCompanyWatches() {
    return this.get<CompanyWatch[]>('/api/company-watches')
  }

  async createCompanyWatch(data: CompanyWatchCreate) {
    return this.post<CompanyWatch>('/api/company-watches', data)
  }

  async updateCompanyWatch(id: string, data: CompanyWatchUpdate) {
    return this.patch<CompanyWatch>(`/api/company-watches/${id}`, data)
  }

  async deleteCompanyWatch(id: string) {
    return this.delete(`/api/company-watches/${id}`)
  }
}

export const apiClient = new APIClient()
export type { Profile, Job, Application, ResumeFamily, JobFilters, SearchProfile, SearchProfileCreate, SearchProfileUpdate, JobMatchScore, ResumeSelectionResult }
