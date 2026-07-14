export interface Profile {
  id: string
  legal_name: string
  preferred_name?: string
  email: string
  phone?: string
  linkedin?: string
  github?: string
  career_interests: string[]
  target_seniority: string
  work_authorization: string
  work_history?: WorkHistory[]
  education?: Education[]
  skills?: string[]
}

export interface WorkHistory {
  id?: string
  company: string
  title: string
  start_date: string
  end_date?: string
  description?: string
}

export interface Education {
  id?: string
  institution: string
  degree: string
  field: string
  graduation_year: number
}

export interface ResumeFamily {
  id: string
  name: string
  target_category: string
  status: "uploaded" | "needs_review" | "approved_base" | "rejected"
  base_version_id?: string
  created_at: string
}

export interface ResumeVersion {
  id: string
  family_id: string
  variant_type: "base" | "tailored"
  status: string
  file_path?: string
  parsed_data?: any
  created_at: string
}

export interface Job {
  id: string
  company: string
  title: string
  description?: string
  location?: string
  remote_policy?: string
  salary_min?: number
  salary_max?: number
  salary_range?: string
  url?: string
  status: "new" | "analyzing" | "scored" | "blocked" | "ready"
  score?: number
  match_analysis?: MatchAnalysis
  created_at: string
  source_url?: string
}

export interface MatchAnalysis {
  overall_score: number
  dimensions: {
    technical_match: number
    seniority_match: number
    career_trajectory: number
    culture_fit: number
  }
  hard_blockers: string[]
  strong_matches: string[]
  recommended_resume_family?: string
}

export interface Application {
  id: string
  job_id: string
  resume_version_id: string
  status: "preparing" | "needs_review" | "ready" | "applied" | "interview"
  pipeline_status: string
  risk_level?: "low" | "medium" | "high"
  application_data?: ApplicationData
  review_findings?: ReviewFinding[]
  created_at: string
  job?: Job
}

export interface ApplicationData {
  questions: ApplicationQuestion[]
  cover_letter?: string
}

export interface ApplicationQuestion {
  question: string
  answer: string
  risk_level?: string
}

export interface ReviewFinding {
  type: "error" | "warning" | "info"
  message: string
  field?: string
}

export interface JobFilters {
  category?: string
  min_score?: number
  max_score?: number
  status?: string
  search?: string
}

export interface SearchProfile {
  id: string
  name: string
  enabled: boolean
  career_categories: string[]
  include_titles: string[]
  exclude_titles: string[]
  include_skills: string[]
  exclude_skills: string[]
  locations: string[]
  remote_policy: "required" | "hybrid_ok" | "no_preference" | "onsite_only"
  min_salary?: number
  max_salary?: number
  exclude_companies: string[]
  require_visa_sponsorship: boolean
  created_at: string
  updated_at: string
}

export interface SearchProfileCreate {
  name: string
  enabled?: boolean
  career_categories: string[]
  include_titles?: string[]
  exclude_titles?: string[]
  include_skills?: string[]
  exclude_skills?: string[]
  locations?: string[]
  remote_policy?: string
  min_salary?: number
  max_salary?: number
  exclude_companies?: string[]
  require_visa_sponsorship?: boolean
}

export interface SearchProfileUpdate {
  name?: string
  enabled?: boolean
  career_categories?: string[]
  include_titles?: string[]
  exclude_titles?: string[]
  include_skills?: string[]
  exclude_skills?: string[]
  locations?: string[]
  remote_policy?: string
  min_salary?: number
  max_salary?: number
  exclude_companies?: string[]
  require_visa_sponsorship?: boolean
}

export interface JobMatchScore {
  id: string
  job_id: string
  overall_score: number
  skill_score: number
  experience_score: number
  seniority_score: number
  location_score: number
  salary_score: number
  hard_blockers: string[]
  strong_matches: string[]
  soft_gaps: string[]
  missing_info: string[]
  recommended_action: "apply" | "pass" | "maybe" | "needs_tailoring"
  explanation: string
  matched_resume_id?: string
  created_at: string
}

export interface ResumeSelectionResult {
  selected_resume_id: string
  selected_resume_name: string
  selection_rationale: string
  alternatives: Array<{
    resume_id: string
    resume_name: string
    score: number
    reason: string
  }>
  missing_coverage: string[]
  tailoring_recommended: boolean
  tailoring_suggestions?: string[]
}
