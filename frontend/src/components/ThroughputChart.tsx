import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import type { Throughput } from '../api/types'

const HEALTH_STYLE: Record<Throughput['health'], string> = {
  idle: 'border-black/30 bg-swiss-muted text-black/50',
  healthy: 'border-black bg-black text-white',
  degraded: 'border-swiss-accent bg-white text-swiss-accent',
  unhealthy: 'border-swiss-accent bg-swiss-accent text-white',
}

export default function ThroughputChart({ data }: { data: Throughput | null }) {
  if (!data) return null

  const chartData = data.buckets.map((b) => ({
    time: new Date(b.bucket_start).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    completed: b.completed,
    failed: b.failed,
  }))

  return (
    <div className="border-2 border-black p-6">
      <div className="mb-4 flex items-center justify-between">
        <div>
          <p className="text-xs font-bold tracking-widest uppercase">Throughput (last hour)</p>
          <p className="text-xs text-black/50">
            {data.total_completed} completed / {data.total_failed} failed &middot; error rate{' '}
            {(data.error_rate * 100).toFixed(0)}%
          </p>
        </div>
        <span
          className={`inline-block rounded-none border-2 px-3 py-1 text-xs font-bold tracking-widest uppercase ${HEALTH_STYLE[data.health]}`}
        >
          {data.health}
        </span>
      </div>
      <ResponsiveContainer width="100%" height={180}>
        <BarChart data={chartData} margin={{ top: 4, right: 4, bottom: 0, left: -20 }}>
          <CartesianGrid strokeDasharray="2 4" stroke="#00000022" vertical={false} />
          <XAxis dataKey="time" tick={{ fontSize: 10 }} axisLine={{ stroke: '#000' }} tickLine={false} />
          <YAxis allowDecimals={false} tick={{ fontSize: 10 }} axisLine={{ stroke: '#000' }} tickLine={false} />
          <Tooltip
            contentStyle={{ border: '2px solid black', borderRadius: 0, fontSize: 12 }}
            cursor={{ fill: '#00000008' }}
          />
          <Bar dataKey="completed" stackId="a" fill="#000000" name="Completed" />
          <Bar dataKey="failed" stackId="a" fill="#ff3000" name="Failed" />
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}
