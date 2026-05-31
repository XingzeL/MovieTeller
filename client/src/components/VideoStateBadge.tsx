import type { VideoState } from '../types/job'

const LABELS: Record<VideoState, string> = {
  not_generated: '视频未生成',
  disabled: '未启用旁白',
  available: '可下载',
  downloaded: '已下载',
  purged: '已清理',
}

const STYLES: Record<VideoState, string> = {
  not_generated: 'bg-zinc-100 text-zinc-600',
  disabled: 'bg-zinc-100 text-zinc-500',
  available: 'bg-emerald-100 text-emerald-800',
  downloaded: 'bg-orange-100 text-orange-700',
  purged: 'bg-orange-100 text-orange-700',
}

export function VideoStateBadge({ state }: { state?: VideoState }) {
  if (!state || state === 'not_generated') return null
  return (
    <span
      className={`inline-flex rounded-full px-2.5 py-1 text-xs font-medium ${STYLES[state]}`}
    >
      {LABELS[state]}
    </span>
  )
}
