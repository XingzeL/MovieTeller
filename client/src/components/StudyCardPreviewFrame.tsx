import { isClerkEnabled } from '../auth/clerkConfig'

/** Clipped study-card preview: shows only the top of the HTML, no in-frame scrolling. */

const DEFAULT_VIEWPORT_PX = 1020
/** Tall enough to render the header/first cards; outer box clips the rest. */
const IFRAME_RENDER_PX = 720

type Props = {
  /** Legacy: direct URL (dev cookie session). Prefer htmlContent with Bearer auth. */
  src?: string
  htmlContent?: string | null
  title?: string
  /** Visible preview height in pixels. */
  viewportHeight?: number
}

export function StudyCardPreviewFrame({
  src,
  htmlContent,
  title = '学习卡预览',
  viewportHeight = DEFAULT_VIEWPORT_PX,
}: Props) {
  const bearerMode = isClerkEnabled()
  const useDirectSrc = !bearerMode && Boolean(src)
  const ready = Boolean(htmlContent) || useDirectSrc

  return (
    <div
      className="relative overflow-hidden rounded-xl border border-[#d1fae5] bg-white"
      style={{ height: viewportHeight }}
      aria-label={title}
    >
      {!ready && (
        <div className="flex h-full items-center justify-center text-sm text-[#64748b]">
          加载预览中…
        </div>
      )}
      {ready && (
      <iframe
        src={useDirectSrc ? src : undefined}
        srcDoc={htmlContent ?? undefined}
        title={title}
        className="pointer-events-none absolute left-0 top-0 w-full max-w-none border-0"
        style={{ height: IFRAME_RENDER_PX }}
        sandbox="allow-scripts allow-same-origin"
        scrolling="no"
        tabIndex={-1}
      />
      )}
      <div
        className="pointer-events-none absolute inset-x-0 bottom-0 h-16 bg-gradient-to-t from-white via-white/90 to-transparent"
        aria-hidden
      />
    </div>
  )
}
