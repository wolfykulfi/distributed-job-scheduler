import { Link, useParams } from 'react-router-dom'
import { jobs } from '../api/client'
import { usePolling } from '../hooks/usePolling'
import StatusBadge from '../components/StatusBadge'
import SectionLabel from '../components/ui/SectionLabel'

export default function JobDetail() {
  const { jobId } = useParams<{ jobId: string }>()

  const { data: job } = usePolling(() => jobs.get(jobId!), 3000, [jobId])
  const { data: executions } = usePolling(() => jobs.executions(jobId!), 3000, [jobId])
  const { data: logs } = usePolling(() => jobs.logs(jobId!), 3000, [jobId])

  if (!job) return <p className="text-xs font-bold tracking-widest uppercase">Loading...</p>

  return (
    <div className="flex flex-col gap-10">
      <div className="border-b-4 border-black pb-6">
        <Link
          to={`/queues/${job.queue_id}`}
          className="swiss-focusable text-xs font-bold tracking-widest text-black/50 uppercase hover:text-swiss-accent"
        >
          &larr; Queue
        </Link>
        <div className="mt-1 flex flex-wrap items-center gap-4">
          <h1 className="text-4xl font-black tracking-tighter uppercase md:text-6xl">{job.name}</h1>
          <StatusBadge status={job.status} />
        </div>
      </div>

      <section>
        <SectionLabel index={1}>Details</SectionLabel>
        <dl className="grid grid-cols-2 gap-x-6 gap-y-3 text-sm md:grid-cols-4">
          {[
            ['Type', job.job_type],
            ['Attempts', job.attempt_count],
            ['Priority', job.priority],
            ['Scheduled for', job.scheduled_for ? new Date(job.scheduled_for).toLocaleString() : '—'],
            ['Claimed at', job.claimed_at ? new Date(job.claimed_at).toLocaleString() : '—'],
            ['Started at', job.started_at ? new Date(job.started_at).toLocaleString() : '—'],
            ['Completed at', job.completed_at ? new Date(job.completed_at).toLocaleString() : '—'],
          ].map(([label, value]) => (
            <div key={label}>
              <dt className="text-[10px] font-bold tracking-widest text-black/40 uppercase">{label}</dt>
              <dd className="mt-0.5">{value}</dd>
            </div>
          ))}
        </dl>
        <h3 className="mt-6 mb-2 text-[10px] font-bold tracking-widest text-black/40 uppercase">Payload</h3>
        <pre className="overflow-x-auto border-2 border-black bg-swiss-muted p-3 font-mono text-xs">
          {JSON.stringify(job.payload, null, 2)}
        </pre>
      </section>

      <section>
        <SectionLabel index={2}>Execution History</SectionLabel>
        <table className="w-full text-left text-sm">
          <thead>
            <tr className="border-b-2 border-black text-xs tracking-widest uppercase">
              <th className="pb-2 font-bold">Attempt</th>
              <th className="pb-2 font-bold">Status</th>
              <th className="pb-2 font-bold">Started</th>
              <th className="pb-2 font-bold">Duration</th>
              <th className="pb-2 font-bold">Error</th>
            </tr>
          </thead>
          <tbody>
            {(executions ?? []).map((ex) => (
              <tr key={ex.id} className="border-b border-black/10 align-top">
                <td className="py-2">{ex.attempt_number}</td>
                <td className="py-2">
                  <StatusBadge status={ex.status} />
                </td>
                <td className="py-2 text-black/50">{new Date(ex.started_at).toLocaleString()}</td>
                <td className="py-2">{ex.duration_ms != null ? `${ex.duration_ms}ms` : '—'}</td>
                <td className="max-w-xs truncate py-2 text-swiss-accent">{ex.error_message ?? '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {(executions ?? []).length === 0 && <p className="mt-2 text-sm text-black/40 uppercase">No executions yet.</p>}
      </section>

      <section>
        <SectionLabel index={3}>Logs</SectionLabel>
        <div className="flex flex-col gap-1 border-2 border-black bg-black p-4 font-mono text-xs text-white">
          {(logs ?? []).map((l) => (
            <div key={l.id} className="flex gap-3">
              <span className="text-white/40">{new Date(l.created_at).toLocaleTimeString()}</span>
              <span className="text-swiss-accent uppercase">{l.level}</span>
              <span>{l.message}</span>
            </div>
          ))}
          {(logs ?? []).length === 0 && <span className="text-white/40 uppercase">No logs yet.</span>}
        </div>
      </section>
    </div>
  )
}
