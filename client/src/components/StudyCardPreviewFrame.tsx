/** Clipped study-card preview: shows only the top of the HTML, no in-frame scrolling. */

const DEFAULT_VIEWPORT_PX = 1020
/** Tall enough to render the header/first cards; outer box clips the rest. */
const IFRAME_RENDER_PX = 720

type Props = {
  src: string
  title?: string
  /** Visible preview height in pixels. */
  viewportHeight?: number
}

export function StudyCardPreviewFrame({
  src,
  title = '学习卡预览',
  viewportHeight = DEFAULT_VIEWPORT_PX,
}: Props) {
  return (
    <div
      className="relative overflow-hidden rounded-xl border border-[#d1fae5] bg-white"
      style={{ height: viewportHeight }}
      aria-label={title}
    >
      <iframe
        src={src}
        title={title}
        className="pointer-events-none absolute left-0 top-0 w-full max-w-none border-0"
        style={{ height: IFRAME_RENDER_PX }}
        sandbox="allow-scripts allow-same-origin"
        scrolling="no"
        tabIndex={-1}
      />
      <div
        className="pointer-events-none absolute inset-x-0 bottom-0 h-16 bg-gradient-to-t from-white via-white/90 to-transparent"
        aria-hidden
      />
    </div>
  )
}
