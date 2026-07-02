import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { organizations } from '../api/client'
import type { Organization, Project } from '../api/types'
import Button from '../components/ui/Button'
import { Input } from '../components/ui/Input'
import SectionLabel from '../components/ui/SectionLabel'

export default function Projects() {
  const [orgs, setOrgs] = useState<Organization[]>([])
  const [projectsByOrg, setProjectsByOrg] = useState<Record<string, Project[]>>({})
  const [newProjectName, setNewProjectName] = useState<Record<string, string>>({})
  const [error, setError] = useState<string | null>(null)

  const reload = async () => {
    const list = await organizations.list()
    setOrgs(list)
    const entries = await Promise.all(list.map(async (o) => [o.id, await organizations.listProjects(o.id)] as const))
    setProjectsByOrg(Object.fromEntries(entries))
  }

  useEffect(() => {
    reload().catch((e) => setError(String(e)))
  }, [])

  const createProject = async (orgId: string) => {
    const name = newProjectName[orgId]?.trim()
    if (!name) return
    await organizations.createProject(orgId, { name })
    setNewProjectName((prev) => ({ ...prev, [orgId]: '' }))
    await reload()
  }

  return (
    <div>
      <SectionLabel index={1}>Organizations</SectionLabel>
      <h1 className="mb-10 text-5xl font-black tracking-tighter uppercase md:text-7xl">
        Projects<span className="text-swiss-accent">.</span>
      </h1>
      {error && <p className="border-2 border-swiss-accent px-3 py-2 text-swiss-accent">{error}</p>}

      <div className="flex flex-col gap-12">
        {orgs.map((org) => (
          <div key={org.id} className="border-t-4 border-black pt-6">
            <h2 className="mb-4 text-xl font-bold tracking-tight uppercase">{org.name}</h2>

            <div className="mb-4 grid grid-cols-1 gap-4 md:grid-cols-3">
              {(projectsByOrg[org.id] ?? []).map((p) => (
                <Link
                  key={p.id}
                  to={`/projects/${p.id}`}
                  className="group border-2 border-black bg-white p-5 transition-colors duration-150 ease-linear hover:bg-black"
                >
                  <span className="block font-bold tracking-tight uppercase group-hover:text-white">{p.name}</span>
                  {p.description && (
                    <span className="mt-1 block text-sm text-black/50 group-hover:text-white/60">
                      {p.description}
                    </span>
                  )}
                </Link>
              ))}
              {(projectsByOrg[org.id] ?? []).length === 0 && (
                <p className="text-sm text-black/40 uppercase">No projects yet.</p>
              )}
            </div>

            <div className="flex max-w-md gap-2">
              <Input
                placeholder="New project name"
                value={newProjectName[org.id] ?? ''}
                onChange={(e) => setNewProjectName((prev) => ({ ...prev, [org.id]: e.target.value }))}
              />
              <Button variant="secondary" onClick={() => createProject(org.id)} className="whitespace-nowrap">
                Create
              </Button>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
