import { useEffect, useState } from 'react'
import {
  Text,
  Card,
  Badge,
  Spinner,
  makeStyles,
  tokens,
} from '@fluentui/react-components'
import { useApiToken } from '../auth/useApiToken'

interface RunSummary {
  id: string
  taskName: string
  taskType: string
  status: string
  startedAt: string
  summary: string
  durationSeconds: number
}

const useStyles = makeStyles({
  root: { padding: '24px' },
  heading: { fontSize: '22px', fontWeight: '700', marginBottom: '24px', display: 'block' },
  grid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))',
    gap: '16px',
    marginBottom: '32px',
  },
  card: { padding: '20px' },
  taskName: { fontWeight: '600', display: 'block', marginBottom: '4px' },
  summary: { color: tokens.colorNeutralForeground2, fontSize: '13px', marginTop: '8px', display: 'block' },
  meta: { color: tokens.colorNeutralForeground3, fontSize: '12px', marginTop: '4px', display: 'block' },
})

const statusBadge: Record<string, 'success' | 'warning' | 'danger' | 'informative'> = {
  completed: 'success',
  completed_with_warnings: 'warning',
  failed: 'danger',
  running: 'informative',
  scheduled: 'informative',
}

export function DashboardPage() {
  const styles = useStyles()
  const { getToken } = useApiToken()
  const [runs, setRuns] = useState<RunSummary[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const load = async () => {
      const token = await getToken()
      const today = new Date().toISOString().slice(0, 10)
      const resp = await fetch(`/api/runs?date=${today}&limit=20`, {
        headers: { Authorization: `Bearer ${token}` },
      })
      if (resp.ok) setRuns(await resp.json())
      setLoading(false)
    }
    load()
  }, [])

  if (loading) return <Spinner style={{ margin: '80px auto', display: 'block' }} />

  return (
    <div className={styles.root}>
      <Text className={styles.heading}>Today's Runs — {new Date().toLocaleDateString()}</Text>
      <div className={styles.grid}>
        {runs.map((run) => (
          <Card key={run.id} className={styles.card}>
            <Text className={styles.taskName}>{run.taskName}</Text>
            <Badge
              color={statusBadge[run.status] ?? 'informative'}
              appearance="tint"
            >
              {run.status.replace(/_/g, ' ')}
            </Badge>
            <Text className={styles.summary}>{run.summary}</Text>
            <Text className={styles.meta}>
              {new Date(run.startedAt).toLocaleTimeString()} · {run.durationSeconds}s
            </Text>
          </Card>
        ))}
        {runs.length === 0 && (
          <Text style={{ color: tokens.colorNeutralForeground3 }}>No runs today yet.</Text>
        )}
      </div>
    </div>
  )
}
