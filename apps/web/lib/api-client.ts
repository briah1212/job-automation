import type {
  Profile,
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
  ApplicationReviewResult
} from './types'

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
    
    const response = await fetch(url, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...options.headers,
      },
      credentials: 'include',
    })

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Request failed' }))
      throw new Error(error.detail || 'Request failed')
    }

    return response.json()
  }

  async get<T>(path: string): Promise<T> {
    return this.request<T>(path, { method: 'GET' })
  }

  async post<T>(path: string, data?: any): Promise<T> {
    return this.request<T>(path, {
      method: 'POST',
      body: data ? JSON.stringify(data) : undefined,
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

  // Auth
  async login(email: string, password: string) {
    return this.post('/api/auth/login', { email, password })
  }

  async register(email: string, password: string, name: string) {
    return this.post('/api/auth/register', { email, password, name })
  }

  // Profile
  async getProfile() {
    return this.get<Profile>('/api/profile')
  }

  async updateProfile(data: Partial<Profile>) {
    return this.put<Profile>('/api/profile', data)
  }

  // Resumes
  async getResumes() {
    return this.get<ResumeFamily[]>('/api/resumes')
  }

  async getResumeVersions() {
    return this.get<ResumeVersion[]>('/api/resumes/versions')
  }

  async getResume(id: string) {
    return this.get<ResumeFamily>(`/api/resumes/${id}`)
  }

  async uploadResume(file: File, family: string) {
    const formData = new FormData()
    formData.append('file', file)
    formData.append('family', family)

    const response = await fetch(`${this.baseURL}/api/resumes/upload`, {
      method: 'POST',
      body: formData,
      credentials: 'include',
    })

    if (!response.ok) {
      throw new Error('Upload failed')
    }

    return response.json()
  }

  async approveResume(id: string) {
    return this.post(`/api/resumes/${id}/approve`)
  }

  async generateVariant(baseId: string, jobId: string) {
    return this.post(`/api/resumes/${baseId}/generate-variant`, { job_id: jobId })
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
    return this.post<Job>('/api/jobs/import', { url })
  }

  async scoreJob(id: string) {
    return this.post(`/api/jobs/${id}/score`)
  }

  // Applications
  async getApplications() {
    return this.get<Application[]>('/api/applications')
  }

  async getApplication(id: string) {
    return this.get<Application>(`/api/applications/${id}`)
  }

  async createApplication(jobId: string) {
    return this.post<Application>('/api/applications', { job_id: jobId })
  }

  async approveApplication(id: string) {
    return this.post(`/api/applications/${id}/approve`)
  }

  async submitApplication(id: string) {
    return this.post(`/api/applications/${id}/submit`)
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
    return this.put<SearchProfile>(`/api/search-profiles/${id}`, data)
  }

  async deleteSearchProfile(id: string) {
    return this.delete(`/api/search-profiles/${id}`)
  }

  async toggleSearchProfile(id: string, enabled: boolean) {
    return this.put<SearchProfile>(`/api/search-profiles/${id}`, { enabled })
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

  async getResumeSelection(jobId: string) {
    return this.get<ResumeSelectionResult>(`/api/jobs/${jobId}/resume-selection`)
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
  async generateApplicationQA(applicationId: string) {
    return this.post<ApplicationQuestionWithAnswer[]>(`/api/applications/${applicationId}/generate`)
  }

  async getApplicationQuestions(applicationId: string) {
    return this.get<ApplicationQuestionWithAnswer[]>(`/api/applications/${applicationId}/questions`)
  }

  async updateApplicationAnswer(applicationId: string, questionId: string, answerText: string) {
    return this.patch<ApplicationQuestionWithAnswer>(`/api/applications/${applicationId}/questions/${questionId}`, { answer_text: answerText })
  }

  // Reusable Answers
  async createReusableAnswer(data: { canonical_question: string; semantic_variants?: string[]; exact_answer: string; allowed_paraphrasing?: boolean; risk_level: string; categories?: string[] }) {
    return this.post<ReusableAnswer>('/api/answers', data)
  }

  async approveReusableAnswer(answerId: string) {
    return this.post<ReusableAnswer>(`/api/answers/${answerId}/approve`)
  }

  // Application Review
  async autoReviewApplication(applicationId: string) {
    return this.post<ApplicationReviewResult>(`/api/applications/${applicationId}/auto-review`)
  }

  async getReviewResult(applicationId: string) {
    return this.get<ApplicationReviewResult>(`/api/applications/${applicationId}/review-result`)
  }
}

export const apiClient = new APIClient()
export type { Profile, Job, Application, ResumeFamily, JobFilters, SearchProfile, SearchProfileCreate, SearchProfileUpdate, JobMatchScore, ResumeSelectionResult }
