/** CEFR + 国内外常见英语考试难度标签（与后端 ALLOWED_LEVELS 一致） */
export type NarrationLevel =
  | 'A1'
  | 'A2'
  | 'B1'
  | 'B2'
  | 'C1'
  | 'IELTS'
  | 'TOEFL'
  | 'CET-4'
  | 'CET-6'
  | '专四'
  | '专八'
  | '考研'

export type GenerateResponse = {
  results: Partial<Record<NarrationLevel, string>>
}
