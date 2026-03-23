import { useEffect, useState } from 'react'
import {
  Text,
  Table,
  TableHeader,
  TableHeaderCell,
  TableBody,
  TableRow,
  TableCell,
  Badge,
  Dropdown,
  Option,
  Button,
  Spinner,
  makeStyles,
} from '@fluentui/react-components'
import { useApiToken } from '../auth/useApiToken'

interface Run {
  id: string
  taskName: string
  taskType: string
  status: string
  startedAt: string
  durationSeconds: number
  summary: string
}

const useStyles = makeStyles({
  root: { padding: '24px' },
  heading: { fontSize: '22px', fontWeight: '700', marginBottom: '20px', display: 'block' },
  filters: { display: 'flex', gap: '12px', marginBottom: '20px', flexWrap: 'wrap', alignItems: 'flex-end' },
  summaryCell: { maxWidth: '320px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' },
})

const statusColor: Record<string, 'success' | 'warning' | 'danger' | 'informative'> = {
  completed: 'success',
  completed_with_warnings: 'warning',
  failed: 'danger',
  running: 'informative',
}

export function HistoryPage() {
  const styles = useStyles()
  const { getToken } = useApiToken()
  const [runs, setRuns] = useState<Run[]>([])
  const [loading, setLoading] = useState(true)
  const [taskTypeFilter, setTaskTypeFilter] = useState('')
  const [statusFilter, setStatusFilter] = useState('')

  const load = async () => {
    setLoading(true)
    const token = await getToken()
    const params = new URLSearchParams({ limit: '50' })
    if (taskTypeFilter) params.set('task_type', taskTypeFilter)
    if (statusFilter) params.set('status', statusFilter)
    const resp = await fetch(`/api/runs?${params}`, {
      headers: { Authorization: `Bearer ${token}` },
    })
    if (resp.ok) setRuns(await resp.json())
    setLoading(false)
  }

  useEffect(() => { load() }, [])

  return (
    <div className={styles.root}>
      <Text className={styles.heading}>Execution History</Text>
      <div className={styles.filters}>
        <Dropdown
          placeholder="Task type"
          onOptionSelect={(_, d) => setTaskTypeFilter(d.optionValue ?? '')}
        >
          <Option value="">All</Option>
          <Option value="health_check">Health Check</Option>
          <Option value="compliance_report">Compliance</Option>
          <Option value="alert_ingestion">Alerts</Option>
          <Option value="patch_assessment">Patching</Option>
          <Option value="cmdb_sync">CMDB</Option>
        </Dropdown>
        <Dropdown
          placeholder="Status"
          onOptionSelect={(_, d) => setStatusFilter(d.optionValue ?? '')}
        >
          <Option value="">All</Option>
          <Option value="completed">Completed</Option>
          <Option value="completed_with_warnings">Warnings</Option>
          <Option value="failed">Failed</Option>
        </Dropdown>
        <Button appearance="primary" onClick={load}>Apply</Button>
      </div>
      {loading ? (
        <Spinner />
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHeaderCell>Task</TableHeaderCell>
              <TableHeaderCell>Status</TableHeaderCell>
              <TableHeaderCell>Started</TableHeaderCell>
              <TableHeaderCell>Duration</TableHeaderCell>
              <TableHeaderCell>Summary</TableHeaderCell>
            </TableRow>
          </TableHeader>
          <TableBody>
            {runs.map((run) => (
              <TableRow key={run.id}>
                <TableCell>{run.taskName}</TableCell>
                <TableCell>
                  <Badge color={statusColor[run.status] ?? 'informative'} appearance="tint">
                    {run.status.replace(/_/g, ' ')}
                  </Badge>
                </TableCell>
                <TableCell>{new Date(run.startedAt).toLocaleString()}</TableCell>
                <TableCell>{run.durationSeconds}s</TableCell>
                <TableCell className={styles.summaryCell}>
                  {run.summary}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
    </div>
  )
}
