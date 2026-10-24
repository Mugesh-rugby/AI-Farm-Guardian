import { useEffect, useRef, useState } from 'react'
import client from '../api/client'
import ConnectApiState from '../components/ConnectApiState'
import { Leaf, LoaderCircle, Send, Trash2, Tractor } from 'lucide-react'

function messageTime(value) {
  const date = new Date(value)
  return Number.isNaN(date.getTime())
    ? ''
    : date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

export default function AiAssistant() {
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [sending, setSending] = useState(false)
  const [connected, setConnected] = useState(true)
  const [reason, setReason] = useState('')
  const [error, setError] = useState('')
  const [fields, setFields] = useState([])
  const [fieldId, setFieldId] = useState('')
  const [historyLoading, setHistoryLoading] = useState(true)
  const bottomRef = useRef(null)

  useEffect(() => {
    let cancelled = false
    Promise.all([
      client.get('/chat/history'),
      client.get('/fields'),
    ]).then(([historyResponse, fieldsResponse]) => {
      if (cancelled) return
      setMessages(historyResponse.data)
      setFields(fieldsResponse.data)
      if (fieldsResponse.data.length > 0) {
        setFieldId(String(fieldsResponse.data[0].id))
      }
    }).catch((requestError) => {
      if (!cancelled) {
        setError(requestError.response?.data?.detail || 'Could not load your assistant. Please refresh and try again.')
      }
    }).finally(() => {
      if (!cancelled) setHistoryLoading(false)
    })
    return () => { cancelled = true }
  }, [])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, sending])

  const send = async (event) => {
    event.preventDefault()
    const userText = input.trim()
    if (!userText || sending) return

    setInput('')
    setError('')
    setConnected(true)
    setMessages((current) => [
      ...current,
      { id: `temp-${Date.now()}`, role: 'user', content: userText, created_at: new Date().toISOString() },
    ])
    setSending(true)
    try {
      const response = await client.post(
        '/chat',
        { message: userText, field_id: fieldId ? Number(fieldId) : null },
        { timeout: 65_000 },
      )
      setConnected(response.data.connected)
      setReason(response.data.reason || '')
      if (response.data.connected && response.data.reply) {
        setMessages((current) => [
          ...current,
          { id: `reply-${Date.now()}`, role: 'assistant', content: response.data.reply, created_at: new Date().toISOString() },
        ])
      }
    } catch (requestError) {
      const detail = requestError.response?.data?.detail
        || (requestError.code === 'ECONNABORTED'
          ? 'The assistant took too long to respond. Please try again.'
          : 'Could not reach the agricultural assistant. Check your connection and try again.')
      setError(detail)
    } finally {
      setSending(false)
    }
  }

  const clearChat = async () => {
    setError('')
    try {
      await client.delete('/chat/history')
      setMessages([])
    } catch (requestError) {
      setError(requestError.response?.data?.detail || 'Could not clear chat history. Please try again.')
    }
  }

  return (
    <section className="mx-auto flex h-[calc(100dvh-11rem)] max-w-7xl flex-col overflow-hidden rounded-3xl border border-gray-200 bg-white shadow-sm sm:h-[calc(100dvh-12rem)] lg:h-[calc(100dvh-8rem)]">
      <header className="flex flex-wrap items-center justify-between gap-3 border-b border-gray-100 px-5 py-4 sm:px-7">
        <div className="flex items-center gap-3">
          <span className="flex h-10 w-10 items-center justify-center rounded-full bg-emerald-50 text-emerald-700">
            <Leaf size={20} />
          </span>
          <div>
            <h1 className="text-lg font-bold text-gray-900 sm:text-xl">AI Farm Assistant</h1>
            <p className="text-xs text-gray-500">Ask agricultural questions about crops, pests, soil, and weather</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {fields.length > 0 && (
            <label className="sr-only" htmlFor="assistant-field">Farm field context</label>
          )}
          {fields.length > 0 && (
            <select
              id="assistant-field"
              className="farm-input max-w-48 text-xs sm:text-sm"
              value={fieldId}
              onChange={(event) => setFieldId(event.target.value)}
            >
              <option value="">No field context</option>
              {fields.map((field) => (
                <option key={field.id} value={field.id}>{field.name} · {field.crop}</option>
              ))}
            </select>
          )}
          <button
            type="button"
            onClick={clearChat}
            disabled={messages.length === 0}
            aria-label="Clear chat history"
            title="Clear chat history"
            className="flex h-10 w-10 items-center justify-center rounded-xl border border-gray-200 text-gray-500 transition hover:bg-red-50 hover:text-red-600 disabled:cursor-not-allowed disabled:opacity-40"
          >
            <Trash2 size={17} />
          </button>
        </div>
      </header>

      <div className="flex-1 space-y-5 overflow-y-auto bg-[#fbfdfb] px-4 py-5 sm:px-8 sm:py-7" aria-live="polite">
        {historyLoading && (
          <div className="flex items-center justify-center gap-2 py-12 text-sm text-gray-500" role="status">
            <LoaderCircle size={17} className="animate-spin" />
            Loading your conversation…
          </div>
        )}
        {!historyLoading && messages.length === 0 && (
          <div className="flex min-h-64 flex-col items-center justify-center text-center">
            <span className="mb-4 flex h-14 w-14 items-center justify-center rounded-full bg-emerald-50 text-emerald-700">
              <Tractor size={27} />
            </span>
            <h2 className="text-base font-semibold text-gray-800">How can I help with your farm?</h2>
            <p className="mt-2 max-w-sm text-sm leading-6 text-gray-500">
              Ask about crop diseases, pest management, irrigation, soil health, or interpreting your farm’s weather.
            </p>
          </div>
        )}
        {messages.map((message) => (
          <div key={message.id} className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            {message.role !== 'user' && (
              <span className="mr-2 mt-1 flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-emerald-50 text-emerald-700">
                <Leaf size={16} />
              </span>
            )}
            <article className={`max-w-[88%] rounded-2xl px-4 py-3 text-sm leading-6 shadow-sm sm:max-w-[78%] ${
              message.role === 'user'
                ? 'rounded-tr-md bg-[#edf6e9] text-gray-800'
                : 'rounded-tl-md border border-gray-100 bg-white text-gray-800'
            }`}>
              <p className="whitespace-pre-wrap">{message.content}</p>
              <time className="mt-1 block text-right text-[10px] text-gray-400">{messageTime(message.created_at)}</time>
            </article>
          </div>
        ))}
        {sending && (
          <div className="flex items-center gap-2 text-sm text-gray-500" role="status">
            <span className="flex h-8 w-8 items-center justify-center rounded-full bg-emerald-50 text-emerald-700">
              <Leaf size={16} />
            </span>
            <span className="inline-flex items-center gap-2 rounded-2xl border border-gray-100 bg-white px-4 py-3">
              <LoaderCircle size={15} className="animate-spin" /> Preparing agricultural guidance…
            </span>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {error && (
        <div className="mx-4 mt-3 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900 sm:mx-7" role="alert">
          {error}
        </div>
      )}
      {!connected && (
        <div className="px-4 pt-3 sm:px-7">
          <ConnectApiState title="AI Farm Assistant needs Groq connected" reason={reason} envVar="GROQ_API_KEY" />
        </div>
      )}

      <form onSubmit={send} className="border-t border-gray-100 bg-white p-4 sm:px-7 sm:py-5">
        <div className="flex items-center gap-2 rounded-full border border-emerald-100 bg-[#fbfdfb] p-1.5 pl-4 shadow-sm focus-within:border-emerald-400 focus-within:ring-2 focus-within:ring-emerald-100">
          <input
            className="min-w-0 flex-1 border-0 bg-transparent py-2 text-sm text-gray-800 outline-none placeholder:text-gray-400 focus:ring-0"
            placeholder="Ask about crops, disease, irrigation, or soil…"
            value={input}
            onChange={(event) => setInput(event.target.value)}
            aria-label="Ask an agricultural question"
            maxLength={2000}
            disabled={sending}
          />
          <button
            type="submit"
            disabled={sending || !input.trim()}
            aria-label="Send message"
            className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-emerald-700 text-white transition hover:bg-emerald-800 disabled:cursor-not-allowed disabled:opacity-45"
          >
            <Send size={17} />
          </button>
        </div>
        <p className="mt-2 text-center text-[11px] text-gray-400">
          AI guidance can be inaccurate. Confirm diagnoses and treatment decisions with a local agricultural expert.
        </p>
      </form>
    </section>
  )
}
