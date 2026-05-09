import type { NarrationLevel } from '../types'

const CEFR_LEVELS: { id: NarrationLevel; label: string }[] = [
  { id: 'A1', label: 'A1 — beginner' },
  { id: 'A2', label: 'A2' },
  { id: 'B1', label: 'B1' },
  { id: 'B2', label: 'B2' },
  { id: 'C1', label: 'C1 — advanced' },
]

const INT_LEVELS: { id: NarrationLevel; label: string }[] = [
  { id: 'IELTS', label: '雅思（IELTS，难度参考）' },
  { id: 'TOEFL', label: '托福（TOEFL，难度参考）' },
]

const CN_LEVELS: { id: NarrationLevel; label: string }[] = [
  { id: 'CET-4', label: 'CET-4（大学英语四级）' },
  { id: 'CET-6', label: 'CET-6（大学英语六级）' },
  { id: '专四', label: '专四（英语专业四级 / TEM-4）' },
  { id: '专八', label: '专八（英语专业八级 / TEM-8）' },
  { id: '考研', label: '考研英语（难度参考）' },
]

type LevelSelectorProps = {
  selected: NarrationLevel[]
  onChange: (levels: NarrationLevel[]) => void
}

export function LevelSelector({ selected, onChange }: LevelSelectorProps) {
  const toggle = (id: NarrationLevel) => {
    if (selected.includes(id)) {
      onChange(selected.filter((l) => l !== id))
    } else {
      onChange([...selected, id])
    }
  }

  const renderGroup = (title: string, items: { id: NarrationLevel; label: string }[]) => (
    <div className="space-y-2">
      <p className="text-xs font-medium text-zinc-500 dark:text-zinc-400">{title}</p>
      <div className="flex flex-wrap gap-2">
        {items.map(({ id, label }) => {
          const isOn = selected.includes(id)
          return (
            <label
              key={id}
              className={`inline-flex cursor-pointer items-center gap-2 rounded-lg border px-3 py-2 text-sm transition ${
                isOn
                  ? 'border-violet-500 bg-violet-50 text-violet-900 dark:border-violet-400 dark:bg-violet-950/50 dark:text-violet-100'
                  : 'border-zinc-200 bg-white text-zinc-700 hover:border-zinc-300 dark:border-zinc-600 dark:bg-zinc-900 dark:text-zinc-300'
              }`}
            >
              <input
                type="checkbox"
                checked={isOn}
                onChange={() => toggle(id)}
                className="size-4 shrink-0 rounded border-zinc-300 text-violet-600 focus:ring-violet-500"
              />
              <span className="text-left">{label}</span>
            </label>
          )
        })}
      </div>
    </div>
  )

  return (
    <fieldset className="space-y-4">
      <legend className="mb-1 text-sm font-medium text-zinc-700 dark:text-zinc-300">
        难度等级（可多选）：CEFR、雅思/托福与中国常见考试参考
      </legend>
      {renderGroup('CEFR（欧洲语言共同参考框架）', CEFR_LEVELS)}
      {renderGroup('雅思 / 托福（国际考试难度参考）', INT_LEVELS)}
      {renderGroup('中国英语考试难度参考', CN_LEVELS)}
    </fieldset>
  )
}
