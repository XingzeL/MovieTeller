import { useNavigate, useParams } from 'react-router-dom'

export function StudyCardPage() {
  const navigate = useNavigate()
  const { jobId } = useParams<{ jobId: string }>()
  const safeJobId = jobId?.trim()

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

  const artifactUrl = `/api/jobs/${encodeURIComponent(safeJobId)}/artifacts/studyCardsHtml`

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
          <a
            href={artifactUrl}
            download
            className="rounded-full border border-[#86efac] bg-white px-4 py-2 text-sm font-semibold text-[#166534] no-underline transition hover:bg-[#f0fdf4]"
          >
            下载学习卡
          </a>
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
        <iframe
          src={`${artifactUrl}?inline=true`}
          title="完整学习卡"
          className="block h-full min-h-[calc(100dvh-65px)] w-full border-0 bg-white"
          sandbox="allow-scripts allow-same-origin"
        />
      </main>
    </div>
  )
}
