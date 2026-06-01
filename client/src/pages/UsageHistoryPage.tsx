import { useNavigate } from 'react-router-dom'

type UsageRecord = {
  id: string
  createdAt: string
  videoName: string
  consumedMinutes: number
  remainingAfter: number
  durationSeconds: number
  status: 'succeeded' | 'failed' | 'canceled'
}

const mockRecords: UsageRecord[] = [
  {
    id: '1',
    createdAt: '2026-05-31 14:22',
    videoName: 'harrypotter.mp4',
    consumedMinutes: 18,
    remainingAfter: 282,
    durationSeconds: 1240,
    status: 'succeeded',
  },
  {
    id: '2',
    createdAt: '2026-05-30 09:15',
    videoName: 'interview_with_prof.mp4',
    consumedMinutes: 27,
    remainingAfter: 300,
    durationSeconds: 1650,
    status: 'succeeded',
  },
  {
    id: '3',
    createdAt: '2026-05-28 21:03',
    videoName: 'news_clip_20260528.mp4',
    consumedMinutes: 9,
    remainingAfter: 327,
    durationSeconds: 540,
    status: 'succeeded',
  },
  {
    id: '4',
    createdAt: '2026-05-25 11:47',
    videoName: 'ted_talk_ai_future.mp4',
    consumedMinutes: 41,
    remainingAfter: 336,
    durationSeconds: 2490,
    status: 'succeeded',
  },
  {
    id: '5',
    createdAt: '2026-05-22 16:30',
    videoName: 'failed_test_upload.mp4',
    consumedMinutes: 0,
    remainingAfter: 377,
    durationSeconds: 120,
    status: 'failed',
  },
]

export function UsageHistoryPage() {
  const navigate = useNavigate()

  const totalConsumed = mockRecords
    .filter(r => r.status === 'succeeded')
    .reduce((sum, r) => sum + r.consumedMinutes, 0)

  const currentRemaining = mockRecords.length > 0 
    ? mockRecords[0].remainingAfter 
    : 300

  return (
    <div className="min-h-dvh bg-[#f0fdf4] text-[#4a5568]">
      {/* Header */}
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
          <p className="mt-1 text-[#718096]">查看您的额度使用记录与处理历史</p>
        </div>

        {/* Summary Cards */}
        <div className="mb-8 grid grid-cols-1 gap-4 md:grid-cols-3">
          <div className="rounded-2xl border border-[#d1fae5] bg-white p-5">
            <div className="text-sm text-[#718096]">当前剩余额度</div>
            <div className="mt-1 text-4xl font-bold tracking-tighter text-[#166534]">
              {currentRemaining} <span className="text-2xl font-medium">分钟</span>
            </div>
          </div>

          <div className="rounded-2xl border border-[#d1fae5] bg-white p-5">
            <div className="text-sm text-[#718096]">本月已消耗</div>
            <div className="mt-1 text-4xl font-bold tracking-tighter text-[#166534]">
              {totalConsumed} <span className="text-2xl font-medium">分钟</span>
            </div>
          </div>

          <div className="rounded-2xl border border-[#d1fae5] bg-white p-5">
            <div className="text-sm text-[#718096]">本月处理视频</div>
            <div className="mt-1 text-4xl font-bold tracking-tighter text-[#166534]">
              {mockRecords.filter(r => r.status === 'succeeded').length} <span className="text-2xl font-medium">个</span>
            </div>
          </div>
        </div>

        {/* History Table */}
        <div className="rounded-3xl border border-[#d1fae5] bg-white p-1 shadow-sm">
          <div className="overflow-x-auto">
            <table className="w-full table-auto text-sm">
              <thead>
                <tr className="border-b border-[#e5f5e9] text-left text-[#718096]">
                  <th className="px-6 py-4 font-medium">时间</th>
                  <th className="px-6 py-4 font-medium">视频名称</th>
                  <th className="px-6 py-4 font-medium">消耗额度</th>
                  <th className="px-6 py-4 font-medium">剩余额度</th>
                  <th className="px-6 py-4 font-medium">处理时长</th>
                  <th className="px-6 py-4 font-medium">状态</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#f0fdf4]">
                {mockRecords.map((record) => (
                  <tr key={record.id} className="hover:bg-[#f8fdf9]">
                    <td className="px-6 py-4 font-mono text-xs text-[#718096]">
                      {record.createdAt}
                    </td>
                    <td className="px-6 py-4 font-medium text-[#166534]">
                      {record.videoName}
                    </td>
                    <td className="px-6 py-4">
                      <span className="font-medium text-red-600">
                        -{record.consumedMinutes} 分钟
                      </span>
                    </td>
                    <td className="px-6 py-4 font-medium text-[#166534]">
                      {record.remainingAfter} 分钟
                    </td>
                    <td className="px-6 py-4 text-[#718096]">
                      {Math.floor(record.durationSeconds / 60)}分 {record.durationSeconds % 60}秒
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

          {mockRecords.length === 0 && (
            <div className="py-12 text-center text-[#718096]">
              暂无使用记录
            </div>
          )}
        </div>

        <div className="mt-6 text-center text-xs text-[#9ca3af]">
          额度消耗仅统计成功完成的任务。失败或取消的任务不扣除额度。
        </div>
      </div>
    </div>
  )
}
