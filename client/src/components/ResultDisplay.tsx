import type { NarrationLevel } from '../types'

type ResultDisplayProps = {
  results: Partial<Record<NarrationLevel, string>> | null
  orderedLevels: NarrationLevel[]
}

export function ResultDisplay({ results, orderedLevels }: ResultDisplayProps) {
  if (!results || orderedLevels.length === 0) {
    return null
  }

  const hasAny = orderedLevels.some((l) => results[l])
  if (!hasAny) return null

  return (
    <section className="mt-8 space-y-4">
      <h2 className="text-lg font-semibold text-zinc-900 dark:text-zinc-100">
        Scene narration
      </h2>
      <div className="space-y-3">
        {orderedLevels.map((level) => {
          const text = results[level]
          if (!text) return null
          return (
            <article
              key={level}
              className="rounded-xl border border-zinc-200 bg-zinc-50/80 p-4 text-left dark:border-zinc-700 dark:bg-zinc-900/80"
            >
              <h3 className="mb-2 text-xs font-semibold tracking-wide text-violet-600 dark:text-violet-400">
                {level}
              </h3>
              <p className="text-[15px] leading-relaxed text-zinc-800 dark:text-zinc-200">{text}</p>
            </article>
          )
        })}
      </div>
    </section>
  )
}
