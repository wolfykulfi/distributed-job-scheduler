import { useCallback, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { deadLetter, jobs, queues, scheduledJobs } from '../api/client'
import { usePolling } from '../hooks/usePolling'
import { useJobEvents } from '../hooks/useJobEvents'
import StatusBadge from '../components/StatusBadge'
import ThroughputChart from '../components/ThroughputChart'
import Button from '../components/ui/Button'
import { Input, Select } from '../components/ui/Input'
import SectionLabel from '../components/ui/SectionLabel'

type Tab = 'jobs' | 'scheduled' | 'dead-letter'

const TAB_LABELS: Record<Tab, string> = { jobs: 'Jobs', scheduled: 'Recurring', 'dead-letter': 'Dead Letter' }

export default function QueueDetail() {
  const { queueId } = useParams<{ queueId: string }>()
  const [tab, setTab] = useState<Tab>('jobs')
  const [tick, setTick] = useState(0)
  const [statusFilter, setStatusFilter] = useState('')
  const [offset, setOffset] = useState(0)
  const limit = 20

  const [jobName, setJobName] = useState('log_message')
  const [jobType, setJobType] = useState<'immediate' | 'delayed' | 'scheduled'>('immediate')
  const [jobPayload, setJobPayload] = useState('{}')
  const [delaySeconds, setDelaySeconds] = useState(30)
  const [scheduledFor, setScheduledFor] = useState('')
  const [dependsOn, setDependsOn] = useState('')
  const [formError, setFormError] = useState<string | null>(null)

  const [cronName, setCronName] = useState('log_message')
  const [cronExpr, setCronExpr] = useState('*/5 * * * *')
  const [cronPayload, setCronPayload] = useState('{}')

  const { data: queue } = usePolling(() => queues.get(queueId!), 5000, [queueId, tick])
  const { data: stats } = usePolling(() => queues.stats(queueId!), 3000, [queueId, tick])
  const { data: throughput } = usePolling(() => queues.throughput(queueId!), 10000, [queueId, tick])
  const { data: jobPage } = usePolling(
    () => jobs.list(queueId!, { status: statusFilter || undefined, limit, offset }),
    3000,
    [queueId, statusFilter, offset, tick],
  )
  const { data: cronJobs } = usePolling(() => scheduledJobs.list(queueId!), 5000, [queueId, tick, tab])
  const { data: dlq } = usePolling(() => deadLetter.list(queueId!, false), 5000, [queueId, tick, tab])

  // Push-based refresh on top of the polling above: a job state change (claim, complete, fail,
  // etc.) bumps `tick` immediately instead of waiting for the next poll interval. If the socket
  // never connects, polling alone still keeps this page correct.
  useJobEvents(
    queueId,
    useCallback(() => setTick((t) => t + 1), []),
  )

  const createJob = async () => {
    setFormError(null)
    let payload: Record<string, unknown> = {}
    try {
      payload = JSON.parse(jobPayload || '{}')
    } catch {
      setFormError('Payload must be valid JSON')
      return
    }
    try {
      await jobs.create(queueId!, {
        name: jobName,
        job_type: jobType,
        payload,
        delay_seconds: jobType === 'delayed' ? delaySeconds : undefined,
        scheduled_for: jobType === 'scheduled' ? new Date(scheduledFor).toISOString() : undefined,
        depends_on: dependsOn
          .split(',')
          .map((s) => s.trim())
          .filter(Boolean),
      })
      setTick((t) => t + 1)
    } catch (err) {
      setFormError(err instanceof Error ? err.message : String(err))
    }
  }

  const createCron = async () => {
    let payload: Record<string, unknown> = {}
    try {
      payload = JSON.parse(cronPayload || '{}')
    } catch {
      setFormError('Cron payload must be valid JSON')
      return
    }
    await scheduledJobs.create(queueId!, { name: cronName, cron_expression: cronExpr, payload })
    setTick((t) => t + 1)
  }

  const togglePause = async () => {
    if (!queue) return
    if (queue.is_paused) await queues.resume(queue.id)
    else await queues.pause(queue.id)
    setTick((t) => t + 1)
  }

  return (
    <div className="flex flex-col gap-8">
      <div className="flex items-end justify-between border-b-4 border-black pb-6">
        <div>
          <Link
            to={`/projects/${queue?.project_id ?? ''}`}
            className="swiss-focusable text-xs font-bold tracking-widest text-black/50 uppercase hover:text-swiss-accent"
          >
            &larr; Project
          </Link>
          <h1 className="mt-1 text-4xl font-black tracking-tighter uppercase md:text-6xl">{queue?.name}</h1>
        </div>
        {queue && (
          <Button variant={queue.is_paused ? 'primary' : 'secondary'} onClick={togglePause}>
            {queue.is_paused ? 'Resume Queue' : 'Pause Queue'}
          </Button>
        )}
      </div>

      {stats && (
        <div className="grid grid-cols-4 gap-px border-2 border-black bg-black md:grid-cols-8">
          {Object.entries(stats).map(([k, v]) => (
            <div key={k} className="bg-white p-3 text-center">
              <div className="text-2xl font-black">{v}</div>
              <div className="text-[10px] font-bold tracking-widest text-black/50 uppercase">{k.replace('_', ' ')}</div>
            </div>
          ))}
        </div>
      )}

      <ThroughputChart data={throughput ?? null} />

      <div className="flex gap-6 border-b-2 border-black">
        {(['jobs', 'scheduled', 'dead-letter'] as Tab[]).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`swiss-focusable border-b-4 px-1 pb-3 text-xs font-bold tracking-widest uppercase transition-colors duration-150 ease-linear ${
              tab === t ? 'border-swiss-accent text-black' : 'border-transparent text-black/40 hover:text-black'
            }`}
          >
            {TAB_LABELS[t]}
          </button>
        ))}
      </div>

      {tab === 'jobs' && (
        <>
          <section className="border-2 border-black p-6">
            <SectionLabel index={1}>Submit A Job</SectionLabel>
            <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
              <Input placeholder="handler name" value={jobName} onChange={(e) => setJobName(e.target.value)} />
              <Select value={jobType} onChange={(e) => setJobType(e.target.value as typeof jobType)}>
                <option value="immediate">immediate</option>
                <option value="delayed">delayed</option>
                <option value="scheduled">scheduled</option>
              </Select>
              {jobType === 'delayed' && (
                <Input
                  type="number"
                  min={1}
                  value={delaySeconds}
                  onChange={(e) => setDelaySeconds(Number(e.target.value))}
                  placeholder="delay seconds"
                />
              )}
              {jobType === 'scheduled' && (
                <Input type="datetime-local" value={scheduledFor} onChange={(e) => setScheduledFor(e.target.value)} />
              )}
              <Input
                placeholder='payload JSON, e.g. {"text":"hi"}'
                value={jobPayload}
                onChange={(e) => setJobPayload(e.target.value)}
                className="col-span-2 md:col-span-1"
              />
              <Input
                placeholder="depends on (job IDs, comma-separated)"
                value={dependsOn}
                onChange={(e) => setDependsOn(e.target.value)}
                className="col-span-2 md:col-span-1"
              />
            </div>
            {formError && <p className="mt-3 text-sm text-swiss-accent">{formError}</p>}
            <Button onClick={createJob} className="mt-4">
              Submit Job
            </Button>
          </section>

          <section>
            <div className="mb-3 flex items-center justify-between">
              <SectionLabel index={2}>Jobs</SectionLabel>
              <Select
                value={statusFilter}
                onChange={(e) => {
                  setStatusFilter(e.target.value)
                  setOffset(0)
                }}
                className="w-auto"
              >
                <option value="">all statuses</option>
                {['queued', 'scheduled', 'claimed', 'running', 'completed', 'failed', 'dead_letter', 'cancelled'].map(
                  (s) => (
                    <option key={s} value={s}>
                      {s}
                    </option>
                  ),
                )}
              </Select>
            </div>
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b-2 border-black text-xs tracking-widest uppercase">
                  <th className="pb-2 font-bold">Name</th>
                  <th className="pb-2 font-bold">Type</th>
                  <th className="pb-2 font-bold">Status</th>
                  <th className="pb-2 font-bold">Attempts</th>
                  <th className="pb-2 font-bold">Created</th>
                </tr>
              </thead>
              <tbody>
                {(jobPage?.items ?? []).map((j) => (
                  <tr key={j.id} className="border-b border-black/10">
                    <td className="py-2">
                      <Link to={`/jobs/${j.id}`} className="font-medium underline decoration-black/20 hover:decoration-swiss-accent hover:text-swiss-accent">
                        {j.name}
                      </Link>
                    </td>
                    <td className="py-2 text-black/60 uppercase">{j.job_type}</td>
                    <td className="py-2">
                      <StatusBadge status={j.status} />
                    </td>
                    <td className="py-2">{j.attempt_count}</td>
                    <td className="py-2 text-black/50">{new Date(j.created_at).toLocaleString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <div className="mt-4 flex items-center justify-between text-xs font-bold tracking-widest uppercase">
              <span className="text-black/50">{jobPage?.total ?? 0} total</span>
              <div className="flex gap-2">
                <Button variant="secondary" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - limit))}>
                  Prev
                </Button>
                <Button
                  variant="secondary"
                  disabled={(jobPage?.items.length ?? 0) < limit}
                  onClick={() => setOffset(offset + limit)}
                >
                  Next
                </Button>
              </div>
            </div>
          </section>
        </>
      )}

      {tab === 'scheduled' && (
        <section>
          <SectionLabel index={1}>Create Recurring Job</SectionLabel>
          <div className="grid grid-cols-3 gap-3">
            <Input placeholder="handler name" value={cronName} onChange={(e) => setCronName(e.target.value)} />
            <Input placeholder="cron expression, e.g. */5 * * * *" value={cronExpr} onChange={(e) => setCronExpr(e.target.value)} />
            <Input placeholder="payload JSON" value={cronPayload} onChange={(e) => setCronPayload(e.target.value)} />
          </div>
          <Button onClick={createCron} className="mt-4">
            Create
          </Button>

          <table className="mt-8 w-full text-left text-sm">
            <thead>
              <tr className="border-b-2 border-black text-xs tracking-widest uppercase">
                <th className="pb-2 font-bold">Name</th>
                <th className="pb-2 font-bold">Cron</th>
                <th className="pb-2 font-bold">Active</th>
                <th className="pb-2 font-bold">Next run</th>
                <th className="pb-2 font-bold">Last run</th>
                <th className="pb-2"></th>
              </tr>
            </thead>
            <tbody>
              {(cronJobs ?? []).map((sj) => (
                <tr key={sj.id} className="border-b border-black/10">
                  <td className="py-2">{sj.name}</td>
                  <td className="py-2">
                    <code className="border border-black/20 bg-swiss-muted px-1 text-xs">{sj.cron_expression}</code>
                  </td>
                  <td className="py-2 uppercase">{sj.is_active ? 'yes' : 'paused'}</td>
                  <td className="py-2 text-black/50">{new Date(sj.next_run_at).toLocaleString()}</td>
                  <td className="py-2 text-black/50">{sj.last_run_at ? new Date(sj.last_run_at).toLocaleString() : '—'}</td>
                  <td className="py-2">
                    <button
                      className="swiss-focusable text-xs font-bold tracking-widest uppercase hover:text-swiss-accent"
                      onClick={async () => {
                        await scheduledJobs.setActive(sj.id, !sj.is_active)
                        setTick((t) => t + 1)
                      }}
                    >
                      {sj.is_active ? 'Pause' : 'Resume'}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}

      {tab === 'dead-letter' && (
        <section>
          <SectionLabel index={1}>Dead Letter Queue</SectionLabel>
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b-2 border-black text-xs tracking-widest uppercase">
                <th className="pb-2 font-bold">Job</th>
                <th className="pb-2 font-bold">Attempts</th>
                <th className="pb-2 font-bold">Last error</th>
                <th className="pb-2 font-bold">Moved</th>
                <th className="pb-2"></th>
              </tr>
            </thead>
            <tbody>
              {(dlq ?? []).map((d) => (
                <tr key={d.id} className="border-b border-black/10">
                  <td className="py-2">
                    <Link to={`/jobs/${d.job_id}`} className="underline decoration-black/20 hover:decoration-swiss-accent hover:text-swiss-accent">
                      {d.job_id.slice(0, 8)}
                    </Link>
                  </td>
                  <td className="py-2">{d.attempt_count}</td>
                  <td className="max-w-xs truncate py-2 text-swiss-accent">{d.last_error}</td>
                  <td className="py-2 text-black/50">{new Date(d.moved_at).toLocaleString()}</td>
                  <td className="py-2">
                    <button
                      className="swiss-focusable text-xs font-bold tracking-widest uppercase hover:text-swiss-accent"
                      onClick={async () => {
                        await deadLetter.retry(d.id)
                        setTick((t) => t + 1)
                      }}
                    >
                      Retry
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {(dlq ?? []).length === 0 && <p className="text-sm text-black/40 uppercase">Nothing in the dead letter queue.</p>}
        </section>
      )}
    </div>
  )
}
