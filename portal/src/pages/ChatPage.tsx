import { useState, useRef, useEffect } from 'react'
import {
  Text,
  Textarea,
  Button,
  Spinner,
  makeStyles,
  tokens,
} from '@fluentui/react-components'
import { SendRegular } from '@fluentui/react-icons'
import { useApiToken } from '../auth/useApiToken'

interface Message {
  role: 'user' | 'assistant'
  content: string
}

const useStyles = makeStyles({
  root: { display: 'flex', flexDirection: 'column', height: '100%', padding: '24px' },
  heading: { fontSize: '22px', fontWeight: '700', marginBottom: '16px', display: 'block' },
  messages: {
    flex: 1,
    overflow: 'auto',
    display: 'flex',
    flexDirection: 'column',
    gap: '12px',
    marginBottom: '16px',
    padding: '4px',
  },
  userMsg: {
    alignSelf: 'flex-end',
    backgroundColor: tokens.colorBrandBackground,
    color: tokens.colorNeutralForegroundOnBrand,
    borderRadius: '12px 12px 2px 12px',
    padding: '10px 16px',
    maxWidth: '70%',
  },
  assistantMsg: {
    alignSelf: 'flex-start',
    backgroundColor: tokens.colorNeutralBackground3,
    borderRadius: '2px 12px 12px 12px',
    padding: '10px 16px',
    maxWidth: '80%',
    whiteSpace: 'pre-wrap',
  },
  inputRow: { display: 'flex', gap: '8px', alignItems: 'flex-end' },
  textarea: { flex: 1 },
})

export function ChatPage() {
  const styles = useStyles()
  const { getToken } = useApiToken()
  const [messages, setMessages] = useState<Message[]>([
    { role: 'assistant', content: '👋 Hi! I\'m your Wintel Ops assistant. Ask me about server health, compliance status, recent runs, or create memories like "Ignore disk warnings on SRV-A for 10 days".' }
  ])
  const [input, setInput] = useState('')
  const [streaming, setStreaming] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const sendMessage = async () => {
    if (!input.trim() || streaming) return
    const userMessage = input.trim()
    setInput('')
    setMessages((prev) => [...prev, { role: 'user', content: userMessage }])
    setStreaming(true)
    setMessages((prev) => [...prev, { role: 'assistant', content: '' }])

    try {
      const token = await getToken()
      const resp = await fetch('/api/chat', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ message: userMessage }),
      })

      if (!resp.ok || !resp.body) {
        setMessages((prev) => {
          const updated = [...prev]
          updated[updated.length - 1] = {
            ...updated[updated.length - 1],
            content: `Error: ${resp.status} ${resp.statusText}`,
          }
          return updated
        })
        return
      }

      const reader = resp.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() ?? ''
        for (const line of lines) {
          if (line.startsWith('data: ') && line !== 'data: [DONE]') {
            try {
              const data = JSON.parse(line.slice(6))
              const delta = data.delta ?? data.choices?.[0]?.delta?.content ?? ''
              if (delta) {
                setMessages((prev) => {
                  const updated = [...prev]
                  updated[updated.length - 1] = {
                    ...updated[updated.length - 1],
                    content: updated[updated.length - 1].content + delta,
                  }
                  return updated
                })
              }
            } catch { /* ignore malformed SSE lines */ }
          }
        }
      }
    } finally {
      setStreaming(false)
    }
  }

  return (
    <div className={styles.root}>
      <Text className={styles.heading}>AI Assistant</Text>
      <div className={styles.messages}>
        {messages.map((msg, i) => (
          <div
            key={i}
            className={msg.role === 'user' ? styles.userMsg : styles.assistantMsg}
          >
            <Text>{msg.content || (streaming && i === messages.length - 1 ? <Spinner size="tiny" /> : '')}</Text>
          </div>
        ))}
        <div ref={messagesEndRef} />
      </div>
      <div className={styles.inputRow}>
        <Textarea
          className={styles.textarea}
          placeholder="Ask about server health, compliance, runs, or create memories..."
          value={input}
          onChange={(_, d) => setInput(d.value)}
          onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage() } }}
          rows={2}
        />
        <Button
          appearance="primary"
          icon={<SendRegular />}
          onClick={sendMessage}
          disabled={streaming || !input.trim()}
        >
          Send
        </Button>
      </div>
    </div>
  )
}
