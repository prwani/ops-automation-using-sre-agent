import { useCallback, useEffect, useState } from 'react'
import {
  Text,
  Card,
  Badge,
  Button,
  Dialog,
  DialogTrigger,
  DialogSurface,
  DialogTitle,
  DialogBody,
  DialogActions,
  DialogContent,
  Input,
  Dropdown,
  Option,
  Field,
  Spinner,
  makeStyles,
  tokens,
} from '@fluentui/react-components'
import { AddRegular, DeleteRegular } from '@fluentui/react-icons'
import { useApiToken } from '../auth/useApiToken'

interface Memory {
  id: string
  type: string
  instruction: string
  scope: { serverFilter: string; taskType?: string; checkFilter?: string }
  effectiveFrom: string
  expiresAt: string
  status: string
  appliedToRuns: string[]
}

const useStyles = makeStyles({
  root: { padding: '24px' },
  header: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' },
  heading: { fontSize: '22px', fontWeight: '700' },
  grid: { display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', gap: '16px' },
  card: { padding: '16px' },
  instruction: { fontWeight: '600', display: 'block', marginBottom: '8px' },
  meta: { color: tokens.colorNeutralForeground3, fontSize: '12px', display: 'block' },
  actions: { display: 'flex', gap: '8px', marginTop: '12px' },
})

const typeColor: Record<string, 'success' | 'warning' | 'danger' | 'informative' | 'severe'> = {
  suppression: 'warning',
  escalation: 'danger',
  knowledge: 'informative',
  threshold_override: 'severe',
  preference: 'success',
  approval_standing: 'informative',
}

export function MemoriesPage() {
  const styles = useStyles()
  const { getToken } = useApiToken()
  const [memories, setMemories] = useState<Memory[]>([])
  const [loading, setLoading] = useState(true)
  const [createOpen, setCreateOpen] = useState(false)
  const [newInstruction, setNewInstruction] = useState('')
  const [newType, setNewType] = useState('suppression')
  const [newServer, setNewServer] = useState('*')
  const [newDays, setNewDays] = useState('30')

  const load = useCallback(async () => {
    setLoading(true)
    const token = await getToken()
    const resp = await fetch('/api/memories?status=all', {
      headers: { Authorization: `Bearer ${token}` },
    })
    if (resp.ok) setMemories(await resp.json())
    setLoading(false)
  }, [getToken])

  useEffect(() => { load() }, [load])

  const createMemory = async () => {
    const token = await getToken()
    await fetch('/api/memories', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
      body: JSON.stringify({
        type: newType,
        instruction: newInstruction,
        server_filter: newServer,
        duration_days: parseInt(newDays),
      }),
    })
    setCreateOpen(false)
    setNewInstruction('')
    load()
  }

  const deleteMemory = async (id: string) => {
    const token = await getToken()
    await fetch(`/api/memories/${id}`, {
      method: 'DELETE',
      headers: { Authorization: `Bearer ${token}` },
    })
    load()
  }

  const active = memories.filter((m) => m.status === 'active')
  const expired = memories.filter((m) => m.status !== 'active')

  return (
    <div className={styles.root}>
      <div className={styles.header}>
        <Text className={styles.heading}>Memories</Text>
        <Dialog open={createOpen} onOpenChange={(_, d) => setCreateOpen(d.open)}>
          <DialogTrigger disableButtonEnhancement>
            <Button appearance="primary" icon={<AddRegular />}>New Memory</Button>
          </DialogTrigger>
          <DialogSurface>
            <DialogTitle>Create Memory</DialogTitle>
            <DialogBody>
              <DialogContent>
                <Field label="Instruction">
                  <Input value={newInstruction} onChange={(_, d) => setNewInstruction(d.value)} placeholder='e.g., "Ignore disk warnings on SRV-A for 10 days"' />
                </Field>
                <Field label="Type">
                  <Dropdown value={newType} onOptionSelect={(_, d) => setNewType(d.optionValue ?? 'suppression')}>
                    <Option value="suppression">Suppression</Option>
                    <Option value="escalation">Escalation</Option>
                    <Option value="knowledge">Knowledge</Option>
                    <Option value="threshold_override">Threshold Override</Option>
                    <Option value="preference">Preference</Option>
                    <Option value="approval_standing">Approval Standing</Option>
                  </Dropdown>
                </Field>
                <Field label="Server Filter">
                  <Input value={newServer} onChange={(_, d) => setNewServer(d.value)} placeholder="Server name or * for all" />
                </Field>
                <Field label="Duration (days)">
                  <Input type="number" value={newDays} onChange={(_, d) => setNewDays(d.value)} />
                </Field>
              </DialogContent>
              <DialogActions>
                <Button appearance="primary" onClick={createMemory} disabled={!newInstruction.trim()}>Create</Button>
                <DialogTrigger disableButtonEnhancement>
                  <Button>Cancel</Button>
                </DialogTrigger>
              </DialogActions>
            </DialogBody>
          </DialogSurface>
        </Dialog>
      </div>

      {loading ? <Spinner /> : (
        <>
          <Text style={{ fontWeight: '600', display: 'block', marginBottom: '12px' }}>
            Active ({active.length})
          </Text>
          <div className={styles.grid} style={{ marginBottom: '32px' }}>
            {active.map((m) => (
              <Card key={m.id} className={styles.card}>
                <Badge color={typeColor[m.type] ?? 'informative'} appearance="tint" style={{ marginBottom: '8px' }}>
                  {m.type.replace(/_/g, ' ')}
                </Badge>
                <Text className={styles.instruction}>{m.instruction}</Text>
                <Text className={styles.meta}>Server: {m.scope.serverFilter}</Text>
                <Text className={styles.meta}>Expires: {new Date(m.expiresAt).toLocaleDateString()}</Text>
                <Text className={styles.meta}>Applied to {m.appliedToRuns.length} runs</Text>
                <div className={styles.actions}>
                  <Button size="small" icon={<DeleteRegular />} appearance="subtle" onClick={() => deleteMemory(m.id)}>Delete</Button>
                </div>
              </Card>
            ))}
          </div>
          {expired.length > 0 && (
            <>
              <Text style={{ fontWeight: '600', color: tokens.colorNeutralForeground3, display: 'block', marginBottom: '12px' }}>
                Expired ({expired.length})
              </Text>
              <div className={styles.grid}>
                {expired.map((m) => (
                  <Card key={m.id} className={styles.card} style={{ opacity: 0.6 }}>
                    <Badge color="subtle" appearance="tint" style={{ marginBottom: '8px' }}>
                      {m.type.replace(/_/g, ' ')} · expired
                    </Badge>
                    <Text className={styles.instruction}>{m.instruction}</Text>
                    <Text className={styles.meta}>Expired: {new Date(m.expiresAt).toLocaleDateString()}</Text>
                  </Card>
                ))}
              </div>
            </>
          )}
        </>
      )}
    </div>
  )
}
