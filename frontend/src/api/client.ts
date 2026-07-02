import axios from 'axios'
import type {
  ApiKeyCreateResponse,
  DeadLetterEntry,
  Job,
  JobExecution,
  JobLog,
  Organization,
  Page,
  Project,
  Queue,
  QueueStats,
  ScheduledJob,
  User,
  Worker,
} from './types'

const api = axios.create({ baseURL: import.meta.env.VITE_API_URL })

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

export interface ApiErrorBody {
  error: { code: string; message: string }
}

export function errorMessage(err: unknown): string {
  if (axios.isAxiosError(err)) {
    const body = err.response?.data as ApiErrorBody | undefined
    return body?.error?.message ?? err.message
  }
  return String(err)
}

export const auth = {
  register: (body: { email: string; password: string; full_name: string; organization_name: string }) =>
    api.post<{ access_token: string }>('/api/v1/auth/register', body).then((r) => r.data),
  login: (body: { email: string; password: string }) =>
    api.post<{ access_token: string }>('/api/v1/auth/login', body).then((r) => r.data),
  me: () => api.get<User>('/api/v1/auth/me').then((r) => r.data),
}

export const organizations = {
  list: () => api.get<Organization[]>('/api/v1/organizations').then((r) => r.data),
  listProjects: (orgId: string) =>
    api.get<Project[]>(`/api/v1/organizations/${orgId}/projects`).then((r) => r.data),
  createProject: (orgId: string, body: { name: string; description?: string }) =>
    api.post<Project>(`/api/v1/organizations/${orgId}/projects`, body).then((r) => r.data),
}

export const projects = {
  get: (projectId: string) => api.get<Project>(`/api/v1/projects/${projectId}`).then((r) => r.data),
  createApiKey: (projectId: string, name: string) =>
    api.post<ApiKeyCreateResponse>(`/api/v1/projects/${projectId}/api-keys`, { name }).then((r) => r.data),
  listWorkers: (projectId: string) =>
    api.get<Worker[]>(`/api/v1/projects/${projectId}/workers`).then((r) => r.data),
}

export const queues = {
  list: (projectId: string) => api.get<Queue[]>(`/api/v1/projects/${projectId}/queues`).then((r) => r.data),
  create: (
    projectId: string,
    body: { name: string; description?: string; priority: number; max_concurrency: number },
  ) => api.post<Queue>(`/api/v1/projects/${projectId}/queues`, body).then((r) => r.data),
  get: (queueId: string) => api.get<Queue>(`/api/v1/queues/${queueId}`).then((r) => r.data),
  pause: (queueId: string) => api.post<Queue>(`/api/v1/queues/${queueId}/pause`).then((r) => r.data),
  resume: (queueId: string) => api.post<Queue>(`/api/v1/queues/${queueId}/resume`).then((r) => r.data),
  stats: (queueId: string) => api.get<QueueStats>(`/api/v1/queues/${queueId}/stats`).then((r) => r.data),
}

export const jobs = {
  list: (queueId: string, params: { status?: string; job_type?: string; limit?: number; offset?: number }) =>
    api.get<Page<Job>>(`/api/v1/queues/${queueId}/jobs`, { params }).then((r) => r.data),
  create: (
    queueId: string,
    body: {
      name: string
      job_type: 'immediate' | 'delayed' | 'scheduled'
      payload: Record<string, unknown>
      priority?: number
      delay_seconds?: number
      scheduled_for?: string
      idempotency_key?: string
    },
  ) => api.post<Job>(`/api/v1/queues/${queueId}/jobs`, body).then((r) => r.data),
  get: (jobId: string) => api.get<Job>(`/api/v1/jobs/${jobId}`).then((r) => r.data),
  executions: (jobId: string) => api.get<JobExecution[]>(`/api/v1/jobs/${jobId}/executions`).then((r) => r.data),
  logs: (jobId: string) => api.get<JobLog[]>(`/api/v1/jobs/${jobId}/logs`).then((r) => r.data),
  cancel: (jobId: string) => api.post<Job>(`/api/v1/jobs/${jobId}/cancel`).then((r) => r.data),
}

export const scheduledJobs = {
  list: (queueId: string) =>
    api.get<ScheduledJob[]>(`/api/v1/queues/${queueId}/scheduled-jobs`).then((r) => r.data),
  create: (queueId: string, body: { name: string; payload: Record<string, unknown>; cron_expression: string }) =>
    api.post<ScheduledJob>(`/api/v1/queues/${queueId}/scheduled-jobs`, body).then((r) => r.data),
  setActive: (id: string, is_active: boolean) =>
    api.patch<ScheduledJob>(`/api/v1/scheduled-jobs/${id}`, { is_active }).then((r) => r.data),
}

export const deadLetter = {
  list: (queueId: string, resolved = false) =>
    api
      .get<DeadLetterEntry[]>(`/api/v1/queues/${queueId}/dead-letter`, { params: { resolved } })
      .then((r) => r.data),
  retry: (dlqId: string) => api.post<Job>(`/api/v1/dead-letter/${dlqId}/retry`).then((r) => r.data),
}

export default api
