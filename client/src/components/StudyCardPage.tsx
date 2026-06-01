import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'

import { apiFetch, ensureDevSession } from '../api/apiClient'
import { downloadStudyCardsHtml } from '../api/downloadArtifact'

type LoadState = 'loading' | 'ready' | 'forbidden' | 'not_found' | 'error'

export function StudyCardPage() {
  const navigate = useNavigate()
  const { jobId } = useParams<{ jobId: string }>()
  const safeJobId = jobId?.trim()

  const [loadState, setLoadState] = useState<LoadState>('loading')
  const [message, setMessage] = useState<string | null>(null)
  const [inlineHtml, setInlineHtml] = useState<string | null>(null)

  useEffect(() => {
    if (!safeJobId) {
      setLoadState('not_found')
      setMessage('学习卡不存在')
      return
    }

    let cancelled = false

    const run = async () => {
      setLoadState('loading')
      setMessage(null)
      try {
        await ensureDevSession()
        const res = await apiFetch(`/api/jobs/${encodeURIComponent(safeJobId)}`)
        const data = (await res.json()) as { error?: string }
        if (cancelled) return

        if (res.status === 404) {
          setLoadState('not_found')
          setMessage('任务不存在或您无权访问该学习卡')
          return
        }
        if (res.status === 401) {
          setLoadState('forbidden')
          setMessage('请先登录')
          return
        }
        if (res.status === 403) {
          setLoadState('forbidden')
          setMessage(data.error ?? '无法打开该学习卡')
          return
        }
        if (!res.ok) {
          setLoadState('error')
          setMessage(data.error ?? `无法加载学习卡 (${res.status})`)
          return
        }

        const inlineRes = await apiFetch(
          `/api/jobs/${encodeURIComponent(safeJobId)}/artifacts/studyCardsHtml?inline=1`,
        )
        if (cancelled) return
        if (!inlineRes.ok) {
          setLoadState('error')
          setMessage(`无法加载学习卡内容 (${inlineRes.status})`)
          return
        }
        const html = await inlineRes.text()
        if (cancelled) return
        setInlineHtml(html)
        setLoadState('ready')
      } catch (err) {
        if (cancelled) return
        setLoadState('error')
        setMessage(err instanceof Error ? err.message : '无法加载学习卡')
      }
    }

    void run()
    return () => {
      cancelled = true
    }
  }, [safeJobId])

  if (!safeJobId) {
    return (
      <div className="flex min-h-dvh items-center justify-center bg-[#f0fdf4] px-6 text-[#166534]">
        <div className="text-center">
          <div className="text-lg font-semibold">学习卡不存在</div>
          <button
            type="button"
            onClick={() => navigate('/dashboard')}
            className="mt-4 rounded-full bg-[#166534] px-5 py-2 text-sm font-semibold text-white transition hover:bg-[#14532d]"
          >
            返回 Dashboard
          </button>
        </div>
      </div>
    )
  }

  const showIframe = loadState === 'ready' && inlineHtml

  const handleDownloadStudyCards = async (id: string) => {
    try {
      await downloadStudyCardsHtml(id)
    } catch {
      /* ignore */
    }
  }

  return (
    <div className="flex min-h-dvh flex-col bg-[#f0fdf4] text-[#4a5568]">
      <header className="flex items-center justify-between border-b border-[#d1fae5] bg-white px-5 py-3">
        <div className="min-w-0">
          <div className="bg-gradient-to-r from-[#86efac] to-[#4ade80] bg-clip-text text-xl font-extrabold tracking-tighter text-transparent">
            NarraLingo
          </div>
          <div className="truncate text-xs text-[#718096]">学习卡 · {safeJobId}</div>
        </div>
        <div className="flex items-center gap-2">
          {showIframe && (
            <button
              type="button"
              onClick={() => void handleDownloadStudyCards(safeJobId)}
              className="rounded-full border border-[#86efac] bg-white px-4 py-2 text-sm font-semibold text-[#166534] transition hover:bg-[#f0fdf4]"
            >
              下载学习卡
            </button>
          )}
          <button
            type="button"
            onClick={() => navigate('/dashboard')}
            className="rounded-full bg-[#166534] px-4 py-2 text-sm font-semibold text-white transition hover:bg-[#14532d]"
          >
            返回 Dashboard
          </button>
        </div>
      </header>

      <main className="min-h-0 flex-1 bg-white">
        {loadState === 'loading' && (
          <div className="flex h-full min-h-[calc(100dvh-65px)] items-center justify-center text-[#718096]">
            加载中…
          </div>
        )}

        {(loadState === 'not_found' ||
          loadState === 'forbidden' ||
          loadState === 'error') && (
          <div className="flex h-full min-h-[calc(100dvh-65px)] flex-col items-center justify-center px-6 text-center text-[#166534]">
            <div className="text-lg font-semibold">
              {loadState === 'forbidden' ? '无法访问' : loadState === 'not_found' ? '未找到' : '加载失败'}
            </div>
            {message && <p className="mt-2 max-w-md text-sm text-[#718096]">{message}</p>}
            <button
              type="button"
              onClick={() => navigate('/dashboard')}
              className="mt-6 rounded-full bg-[#166534] px-5 py-2 text-sm font-semibold text-white transition hover:bg-[#14532d]"
            >
              返回 Dashboard
            </button>
          </div>
        )}

        {showIframe && (
          <iframe
            srcDoc={inlineHtml}
            title="完整学习卡"
            className="block h-full min-h-[calc(100dvh-65px)] w-full border-0 bg-white"
            sandbox="allow-scripts allow-same-origin"
          />
        )}
      </main>
    </div>
  )
}
