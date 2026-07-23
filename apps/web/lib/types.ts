export interface Profile {
  id: string
  user_id: string
  legal_name?: string
  preferred_name?: string
  email?: string
  phone?: string
  linkedin?: string
  github?: string
  career_interests?: string
  target_seniority?: string
  work_authorization?: string
  date_of_birth?: string
  address_line1?: string
  address_line2?: string
  city?: string
  state?: string
  postal_code?: string
  country?: string
  graduation_year?: number
  relocation_willingness?: string
  salary_expectation_min?: number
  salary_expectation_max?: number
  citizenship?: string
  clearance_eligible?: boolean
  profile_metadata: Record<string, any>
  created_at: string
  updated_at: string
}

export type ProfileUpdate = Partial<
  Omit<Profile, 'id' | 'user_id' | 'profile_metadata' | 'created_at' | 'updated_at'>
>

export type ResumeStatus = "draft" | "parsing" | "parsed" | "tailoring" | "ready" | "approved" | "archived"

export interface ResumeFamily {
  id: string
  user_id: string
  name: string
  target_category?: string
  status: ResumeStatus
  created_at: string
  updated_at: string
}

export interface ResumeVersion {
  id: string
  family_id: string
  parent_id?: string
  version: number
  status: ResumeStatus
  file_path?: string
  file_hash?: string
  parsed_data?: any
  family_name?: string
  created_at: string
  updated_at: string
}

export interface Job {
  id: string
  user_id: string
  company: string
  title: string
  description?: string
  location?: string
  remote_policy?: string
  salary_min?: number
  salary_max?: number
  /** Arbitrary extraction payload - the original posting URL lives at extracted_data.url */
  extracted_data: Record<string, any>
  status:
    | "discovered"
    | "extracting"
    | "scored"
    | "saved"
    | "shortlisted"
    | "preparing"
    | "ready_for_review"
    | "approved"
    | "rejected_by_rule"
    | "archived"
  /** @deprecated legacy field, nothing writes to this anymore - use match_score */
  score?: number
  /** Latest calculated match score (0-100), from JobMatchScore.overall_score */
  match_score?: number | null
  created_at: string
  updated_at: string
}

export interface Application {
  id: string
  job_id: string
  resume_version_id?: string
  status: "draft" | "ready" | "submitted" | "in_review" | "rejected" | "archived"
  pipeline_status:
    | "not_started"
    | "draft"
    | "awaiting_review"
    | "approved"
    | "browser_running"
    | "paused"
    | "submitted"
    | "confirmed"
    | "failed_retryable"
    | "failed_terminal"
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
  remote_policy?: "required" | "hybrid_ok" | "no_preference" | "onsite_only"
  min_salary?: number
  employment_types: string[]
  seniority_levels: string[]
  companies: string[]
  excluded_companies: string[]
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
  employment_types?: string[]
  seniority_levels?: string[]
  companies?: string[]
  excluded_companies?: string[]
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
  employment_types?: string[]
  seniority_levels?: string[]
  companies?: string[]
  excluded_companies?: string[]
}

export interface MatchSignal {
  type?: string
  reason?: string
  detail?: string
  field?: string
  impact?: string
  [key: string]: string | undefined
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
  hard_blockers: MatchSignal[]
  strong_matches: MatchSignal[]
  soft_gaps: MatchSignal[]
  missing_info: MatchSignal[]
  recommended_action: "priority" | "prepare_application" | "save_for_later" | "reject"
  explanation?: string
  matched_resume_id?: string
  created_at: string
}

export interface ResumeSelectionResult {
  job_id: string
  recommended_resume_id: string
  match_score: number
  reasoning: string
  strengths: string[]
  weaknesses: string[]
  customization_suggestions: string[]
}

export interface ProfileFact {
  id: string
  user_id: string
  fact_type: string
  content: string
  source_type: string
  source_identifier?: string
  original_text?: string
  confidence: number
  user_verified: boolean
  permitted_uses: string[]
  created_at: string
  updated_at: string
}

export interface RequirementEvidenceItem {
  requirement: string
  importance: "required" | "preferred"
  evidence: Array<{ profile_fact_id: string; strength: number; explanation: string }>
  coverage: "strong" | "partial" | "none"
}

export interface ClaimProvenance {
  claim_id: string
  claim_text: string
  section: string
  profile_fact_ids: string[]
}

export interface ResumeTailorResponse {
  resume_version_id: string
  requirement_evidence_matrix: RequirementEvidenceItem[]
  change_log: Array<Record<string, any>>
  claim_provenance: ClaimProvenance[]
  keyword_coverage: Record<string, boolean>
  warnings: string[]
  page_count: number
  quality_score: number
}

export interface ResumeDiff {
  added: string[]
  removed: string[]
  reordered: string[]
  keyword_changes: { added: string[]; removed: string[] }
  summary_change: { before: string; after: string; diff_lines: string[] }
  skills_change: { added: string[]; removed: string[]; reordered: boolean }
  warnings: string[]
}

export interface DocumentRendering {
  id: string
  resume_version_id: string
  format: "pdf" | "docx"
  file_path: string
  page_count?: number
  created_at: string
}

export interface DocumentLock {
  id: string
  resume_family_id: string
  lock_type: string
  target_ref: string
  value?: Record<string, any>
  created_at: string
}

export interface ApplicationAnswerInfo {
  answer_text: string
  source: "exact_approved" | "canonical_approved" | "deterministic" | "ai_generated" | "user_input"
  approved: boolean
}

export interface ApplicationQuestionWithAnswer {
  id: string
  question_text: string
  question_type: string
  risk_level: "low" | "medium" | "high"
  answer?: ApplicationAnswerInfo | null
}

export interface ReusableAnswer {
  id: string
  user_id: string
  canonical_question: string
  semantic_variants: string[]
  exact_answer: string
  allowed_paraphrasing: boolean
  risk_level: "low" | "medium" | "high"
  categories: string[]
  expiration_date?: string
  user_approved: boolean
  created_at: string
  updated_at: string
}

export interface ApplicationReviewResult {
  id: string
  application_id: string
  passed: boolean
  blocking_findings: string[]
  warnings: string[]
  confidence: number
  recommended_correction?: string
  created_at: string
}

export interface CoverLetter {
  id: string
  application_id: string
  content: string
  tone?: string
  word_limit?: number
  word_count?: number
  status: "needs_review" | "approved"
  warnings: string[]
  claim_provenance: Array<{ profile_fact_id: string; explanation: string }>
  created_at: string
  updated_at: string
}

export interface ApplicationReviewRequest {
  approved: boolean
  comments?: string
}

export interface ApplicationApproveRequest {
  approved: boolean
}

export type WorkflowTaskStatus =
  | "pending"
  | "running"
  | "waiting_user_input"
  | "completed"
  | "failed"
  | "cancelled"

export interface PendingQuestion {
  label: string
  field_name?: string
  question_type?: string
  risk_level?: string
}

export interface BrowserTaskMetadata {
  step?: string
  updated_at?: string
  pending_question?: PendingQuestion | null
  last_answer?: { label: string; field_name?: string; answer_text: string }
  manual_intervention_reason?: string
  [key: string]: any
}

export interface BrowserStatus {
  id: string
  status: WorkflowTaskStatus
  current_step?: string
  retry_count: number
  error?: string
  task_metadata: BrowserTaskMetadata
  started_at?: string
  completed_at?: string
}

export interface BrowserTaskResponse {
  id: string
  status: WorkflowTaskStatus
  task_metadata: BrowserTaskMetadata
}

export interface CompanyWatch {
  id: string
  company_name: string
  ats_platform: string
  board_identifier: string
  enabled: boolean
  last_polled_at?: string
  last_poll_error?: string
}

export interface CompanyWatchCreate {
  company_name: string
  ats_platform: string
  board_identifier: string
  enabled?: boolean
}

export interface CompanyWatchUpdate {
  enabled?: boolean
}

export interface ReusableAnswerCreate {
  canonical_question: string
  semantic_variants?: string[]
  exact_answer: string
  allowed_paraphrasing?: boolean
  risk_level: string
  categories?: string[]
  user_approved?: boolean
}

export interface ReusableAnswerUpdate {
  exact_answer?: string
  semantic_variants?: string[]
  user_approved?: boolean
}
