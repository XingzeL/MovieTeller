import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { apiFetch } from '../api/apiClient'
import type { UsageResponse } from '../types/usage'

function formatDate(value: string) {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function formatDurationSeconds(seconds: number | null | undefined) {
  if (seconds == null || seconds <= 0) return '—'
  const minutes = Math.floor(seconds / 60)
  const secs = seconds % 60
  return `${minutes}分 ${secs}秒`
}

export function UsageHistoryPage() {
  const navigate = useNavigate()
  const [data, setData] = useState<UsageResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    void (async () => {
      try {
        const res = await apiFetch('/api/usage')
        if (!res.ok) {
          const body = await res.json().catch(() => ({}))
          throw new Error(
            typeof body.error === 'string' ? body.error : `请求失败 (${res.status})`,
          )
        }
        const payload = (await res.json()) as UsageResponse
        if (!cancelled) {
          setData(payload)
          setError(null)
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : '加载失败')
        }
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [])

  const records = data?.records ?? []
  const summary = data?.summary
  const processingRemaining = summary?.processingRemainingMinutes ?? summary?.remainingMinutes ?? 0
  const narrationRemaining = summary?.narrationRemainingMinutes ?? 0
  const processingConsumed =
    summary?.processingConsumedInPeriod ?? summary?.consumedInPeriod ?? 0
  const narrationConsumed = summary?.narrationConsumedInPeriod ?? 0
  const succeededCount = summary?.succeededCount ?? 0

  return (
    <div className="min-h-dvh bg-[#f0fdf4] text-[#4a5568]">
      <div className="border-b border-[#d1fae5] bg-white px-6 py-4">
        <div className="mx-auto flex max-w-6xl items-center justify-between">
          <div className="flex items-center gap-3">
            <div
              onClick={() => navigate('/dashboard')}
              className="flex cursor-pointer items-center gap-2"
            >
              <div className="bg-gradient-to-r from-[#86efac] to-[#4ade80] bg-clip-text text-2xl font-extrabold tracking-tighter text-transparent">
                NarraLingo
              </div>
              <span className="rounded bg-[#d1fae5] px-1.5 py-0.5 text-[10px] font-medium text-[#166534]">
                Beta
              </span>
            </div>
          </div>

          <button
            type="button"
            onClick={() => navigate('/dashboard')}
            className="rounded-full border border-[#d1fae5] bg-white px-4 py-1.5 text-sm font-medium text-[#166534] transition hover:bg-[#f0fdf4]"
          >
            返回 Dashboard
          </button>
        </div>
      </div>

      <div className="mx-auto max-w-6xl px-6 pb-16 pt-8">
        <div className="mb-8">
          <h1 className="text-3xl font-bold tracking-tight text-[#166534]">Usage &amp; History</h1>
          <p className="mt-1 text-[#718096]">查看当前计费周期额度与近 3 天使用记录</p>
        </div>

        {error && (
          <div className="mb-6 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            {error}
          </div>
        )}

        <div className="mb-8 grid grid-cols-1 gap-4 md:grid-cols-3">
          <div className="rounded-2xl border border-[#d1fae5] bg-white p-5">
            <div className="text-sm text-[#718096]">基础处理剩余额度</div>
            <div className="mt-1 text-4xl font-bold tracking-tighter text-[#166534]">
              {loading ? '…' : processingRemaining}{' '}
              <span className="text-2xl font-medium">分钟</span>
            </div>
            <div className="mt-2 text-xs text-[#718096]">
              本周期已用 {loading ? '…' : processingConsumed} 分钟
            </div>
          </div>

          <div className="rounded-2xl border border-[#d1fae5] bg-white p-5">
            <div className="text-sm text-[#718096]">解说声道剩余额度</div>
            <div className="mt-1 text-4xl font-bold tracking-tighter text-[#166534]">
              {loading ? '…' : narrationRemaining}{' '}
              <span className="text-2xl font-medium">分钟</span>
            </div>
            <div className="mt-2 text-xs text-[#718096]">
              本周期已用 {loading ? '…' : narrationConsumed} 分钟
            </div>
          </div>

          <div className="rounded-2xl border border-[#d1fae5] bg-white p-5">
            <div className="text-sm text-[#718096]">本周期成功任务</div>
            <div className="mt-1 text-4xl font-bold tracking-tighter text-[#166534]">
              {loading ? '…' : succeededCount}{' '}
              <span className="text-2xl font-medium">个</span>
            </div>
          </div>
        </div>

        <div className="rounded-3xl border border-[#d1fae5] bg-white p-1 shadow-sm">
          <div className="overflow-x-auto">
            <table className="w-full table-auto text-sm">
              <thead>
                <tr className="border-b border-[#e5f5e9] text-left text-[#718096]">
                  <th className="px-6 py-4 font-medium">时间</th>
                  <th className="px-6 py-4 font-medium">视频名称</th>
                  <th className="px-6 py-4 font-medium">基础消耗</th>
                  <th className="px-6 py-4 font-medium">解说消耗</th>
                  <th className="px-6 py-4 font-medium">基础剩余</th>
                  <th className="px-6 py-4 font-medium">解说剩余</th>
                  <th className="px-6 py-4 font-medium">处理时长</th>
                  <th className="px-6 py-4 font-medium">状态</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#f0fdf4]">
                {records.map((record) => (
                  <tr key={record.id} className="hover:bg-[#f8fdf9]">
                    <td className="px-6 py-4 font-mono text-xs text-[#718096]">
                      {formatDate(record.createdAt)}
                    </td>
                    <td className="px-6 py-4 font-medium text-[#166534]">
                      {record.videoName || record.jobId}
                    </td>
                    <td className="px-6 py-4">
                      <span className="font-medium text-red-600">
                        -{record.processingConsumedMinutes ?? record.consumedMinutes} 分钟
                      </span>
                    </td>
                    <td className="px-6 py-4">
                      <span className="font-medium text-red-600">
                        -{record.narrationConsumedMinutes ?? 0} 分钟
                      </span>
                    </td>
                    <td className="px-6 py-4 font-medium text-[#166534]">
                      {record.remainingAfter ?? '—'} 分钟
                    </td>
                    <td className="px-6 py-4 font-medium text-[#166534]">
                      {record.narrationRemainingAfter ?? '—'} 分钟
                    </td>
                    <td className="px-6 py-4 text-[#718096]">
                      {formatDurationSeconds(
                        record.processedDurationSeconds ?? record.sourceDurationSeconds,
                      )}
                    </td>
                    <td className="px-6 py-4">
                      {record.status === 'succeeded' && (
                        <span className="rounded-full bg-[#d1fae5] px-3 py-0.5 text-xs font-medium text-[#166534]">
                          已完成
                        </span>
                      )}
                      {record.status === 'failed' && (
                        <span className="rounded-full bg-red-100 px-3 py-0.5 text-xs font-medium text-red-600">
                          失败
                        </span>
                      )}
                      {record.status === 'canceled' && (
                        <span className="rounded-full bg-amber-100 px-3 py-0.5 text-xs font-medium text-amber-600">
                          已取消
                        </span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {!loading && records.length === 0 && (
            <div className="py-12 text-center text-[#718096]">暂无近 3 天使用记录</div>
          )}
          {loading && (
            <div className="py-12 text-center text-[#718096]">加载中…</div>
          )}
        </div>

        <div className="mt-6 text-center text-xs text-[#9ca3af]">
          列表展示近 3 天记录；摘要为当前计费周期。未生成解说声道的任务不消耗解说额度，失败或取消的任务不扣除额度。
        </div>
      </div>
    </div>
  )
}
