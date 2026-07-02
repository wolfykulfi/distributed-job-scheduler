import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { projects, queues } from '../api/client'
import { usePolling } from '../hooks/usePolling'
import StatusBadge from '../components/StatusBadge'
import Button from '../components/ui/Button'
import { Input } from '../components/ui/Input'
import Panel from '../components/ui/Panel'
import SectionLabel from '../components/ui/SectionLabel'

export default function ProjectDetail() {
  const { projectId } = useParams<{ projectId: string }>()
  const [newQueueName, setNewQueueName] = useState('')
  const [newKeyName, setNewKeyName] = useState('')
  const [revealedKey, setRevealedKey] = useState<string | null>(null)
  const [tick, setTick] = useState(0)

  const { data: queueList } = usePolling(() => queues.list(projectId!), 4000, [projectId, tick])
  const { data: workers } = usePolling(() => projects.listWorkers(projectId!), 4000, [projectId, tick])

  const createQueue = async () => {
    if (!newQueueName.trim()) return
    await queues.create(projectId!, { name: newQueueName.trim(), priority: 0, max_concurrency: 4 })
    setNewQueueName('')
    setTick((t) => t + 1)
  }

  const createApiKey = async () => {
    if (!newKeyName.trim()) return
    const res = await projects.createApiKey(projectId!, newKeyName.trim())
    setRevealedKey(res.api_key)
    setNewKeyName('')
  }

  return (
    <div className="flex flex-col gap-12">
      <div>
        <Link to="/projects" className="swiss-focusable text-xs font-bold tracking-widest text-black/50 uppercase hover:text-swiss-accent">
          &larr; Projects
        </Link>
      </div>

      <section className="border-t-4 border-black pt-6">
        <SectionLabel index={1}>Queues</SectionLabel>
        <div className="mb-4 flex flex-col gap-2">
          {(queueList ?? []).map((q) => (
            <Link
              key={q.id}
              to={`/queues/${q.id}`}
              className="flex items-center justify-between border-2 border-black bg-white px-4 py-3 transition-colors duration-150 ease-linear hover:bg-swiss-muted"
            >
              <span>
                <span className="font-bold tracking-tight uppercase">{q.name}</span>
                <span className="ml-3 text-xs tracking-wide text-black/50 uppercase">
                  priority {q.priority} / concurrency {q.max_concurrency}
                </span>
              </span>
              {q.is_paused && <StatusBadge status="cancelled" />}
            </Link>
          ))}
          {(queueList ?? []).length === 0 && <p className="text-sm text-black/40 uppercase">No queues yet.</p>}
        </div>
        <div className="flex max-w-md gap-2">
          <Input placeholder="New queue name" value={newQueueName} onChange={(e) => setNewQueueName(e.target.value)} />
          <Button variant="secondary" onClick={createQueue} className="whitespace-nowrap">
            Create
          </Button>
        </div>
      </section>

      <section className="border-t-4 border-black pt-6">
        <SectionLabel index={2}>Workers</SectionLabel>
        <table className="w-full text-left text-sm">
          <thead>
            <tr className="border-b-2 border-black text-xs tracking-widest uppercase">
              <th className="pb-2 font-bold">Hostname</th>
              <th className="pb-2 font-bold">Status</th>
              <th className="pb-2 font-bold">Concurrency</th>
              <th className="pb-2 font-bold">Last heartbeat</th>
            </tr>
          </thead>
          <tbody>
            {(workers ?? []).map((w) => (
              <tr key={w.id} className="border-b border-black/10">
                <td className="py-2">{w.hostname}</td>
                <td className="py-2">
                  <StatusBadge status={w.status} />
                </td>
                <td className="py-2">{w.concurrency}</td>
                <td className="py-2 text-black/50">
                  {w.last_heartbeat_at ? new Date(w.last_heartbeat_at).toLocaleTimeString() : '—'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {(workers ?? []).length === 0 && <p className="mt-3 text-sm text-black/40 uppercase">No workers registered.</p>}
      </section>

      <section className="border-t-4 border-black pt-6">
        <SectionLabel index={3}>Worker Access</SectionLabel>
        <p className="mb-3 max-w-lg text-sm text-black/60">
          Issue a key for <code className="border border-black/20 bg-swiss-muted px-1">PROJECT_API_KEY</code> so a
          worker process can register itself.
        </p>
        <div className="flex max-w-md gap-2">
          <Input
            placeholder="Key name (e.g. worker-fleet-1)"
            value={newKeyName}
            onChange={(e) => setNewKeyName(e.target.value)}
          />
          <Button variant="secondary" onClick={createApiKey} className="whitespace-nowrap">
            Create key
          </Button>
        </div>
        {revealedKey && (
          <Panel className="mt-4 max-w-lg border-swiss-accent">
            <p className="mb-2 text-xs font-bold tracking-widest text-swiss-accent uppercase">
              Copy now — shown once
            </p>
            <code className="text-sm break-all">{revealedKey}</code>
          </Panel>
        )}
      </section>
    </div>
  )
}
