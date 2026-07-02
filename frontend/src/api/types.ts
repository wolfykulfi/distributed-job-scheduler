export interface User {
  id: string
  email: string
  full_name: string
  is_active: boolean
}

export interface Organization {
  id: string
  name: string
}

export interface Project {
  id: string
  organization_id: string
  name: string
  description: string | null
  owner_id: string | null
}

export interface ApiKeyCreateResponse {
  id: string
  name: string
  api_key: string
}

export interface Queue {
  id: string
  project_id: string
  name: string
  description: string | null
  priority: number
  max_concurrency: number
  is_paused: boolean
  default_retry_policy_id: string | null
}

export interface QueueStats {
  queued: number
  scheduled: number
  claimed: number
  running: number
  completed: number
  failed: number
  dead_letter: number
  cancelled: number
}

export interface ThroughputBucket {
  bucket_start: string
  completed: number
  failed: number
}

export interface Throughput {
  buckets: ThroughputBucket[]
  total_completed: number
  total_failed: number
  error_rate: number
  health: 'idle' | 'healthy' | 'degraded' | 'unhealthy'
}

export interface Job {
  id: string
  queue_id: string
  batch_id: string | null
  scheduled_job_id: string | null
  name: string
  job_type: 'immediate' | 'delayed' | 'scheduled' | 'recurring_instance' | 'batch'
  status: 'queued' | 'scheduled' | 'claimed' | 'running' | 'completed' | 'failed' | 'dead_letter' | 'cancelled'
  payload: Record<string, unknown>
  priority: number
  idempotency_key: string | null
  scheduled_for: string | null
  next_retry_at: string | null
  attempt_count: number
  claimed_by: string | null
  claimed_at: string | null
  started_at: string | null
  completed_at: string | null
  created_at: string
}

export interface JobExecution {
  id: string
  attempt_number: number
  status: 'running' | 'succeeded' | 'failed'
  worker_id: string | null
  started_at: string
  finished_at: string | null
  duration_ms: number | null
  error_message: string | null
  result: Record<string, unknown> | null
  ai_summary: string | null
}

export interface JobDependency {
  job_id: string
  name: string
  status: string
}

export interface JobLog {
  id: string
  level: string
  message: string
  created_at: string
}

export interface Page<T> {
  items: T[]
  total: number
  limit: number
  offset: number
}

export interface ScheduledJob {
  id: string
  queue_id: string
  name: string
  payload: Record<string, unknown>
  cron_expression: string
  timezone: string
  is_active: boolean
  next_run_at: string
  last_run_at: string | null
}

export interface Worker {
  id: string
  project_id: string
  hostname: string
  pid: number | null
  status: 'online' | 'draining' | 'offline'
  concurrency: number
  started_at: string
  last_heartbeat_at: string | null
  stopped_at: string | null
}

export interface DeadLetterEntry {
  id: string
  job_id: string
  queue_id: string
  failure_reason: string
  attempt_count: number
  last_error: string | null
  moved_at: string
  resolved: boolean
}
