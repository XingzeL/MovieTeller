import UploadPage from './UploadPage'

export default function App() {
  return (
    <div className="min-h-dvh bg-zinc-100 text-zinc-900 dark:bg-zinc-950 dark:text-zinc-100">
      <div className="mx-auto max-w-2xl px-4 py-12 sm:px-6">
        <header className="mb-10 text-center">
          <h1 className="text-3xl font-semibold tracking-tight text-zinc-900 dark:text-white sm:text-4xl">
            AI English Scene Narrator
          </h1>
          <p className="mt-2 text-sm text-zinc-600 dark:text-zinc-400">
            Mock scene narration by CEFR or Chinese exam levels (MVP — no real AI yet)
          </p>
        </header>

        <UploadPage />
      </div>
    </div>
  )
}
