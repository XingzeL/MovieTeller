from __future__ import annotations

import argparse
import html
import json
import shutil
import sys
from pathlib import Path
from typing import Any

from video_frame_pool.types import FramePoolEntry

from movie_pipeline.study_cards_frames import (
    copy_selected_frames,
    data_urls_for_selected,
    load_manifest_from_pool_dir,
    select_frames_for_segment,
)
from movie_pipeline.types import StudyCardSegment, StudyCardsDocument


def _load_styles() -> str:
    p = Path(__file__).with_name("study_cards.css")
    if not p.is_file():
        raise FileNotFoundError(f"Missing stylesheet next to module: {p}")
    return p.read_text(encoding="utf-8")


def format_media_timestamp(sec: float) -> str:
    sec = max(0.0, float(sec))
    total_int = int(sec)
    frac = sec - float(total_int)
    ms = int(round(frac * 1000.0)) % 1000
    minutes, seconds = divmod(total_int, 60)
    return f"{minutes}:{seconds:02d}.{ms:03d}"


def _subtitle_display(value: str | None) -> str:
    if value is None:
        return "（无）"
    s = str(value).strip()
    return s if s else "（无）"


def _ranges_overlap(a: tuple[int, int], b: tuple[int, int]) -> bool:
    return not (a[1] <= b[0] or a[0] >= b[1])


def _vocab_tooltip_inner_html(h: dict[str, Any], phrase_plain: str) -> str:
    """Build tooltip body; *phrase_plain* is the full highlighted span as in the passage."""
    esc = lambda s: html.escape(str(s or ""), quote=False)
    title = esc(phrase_plain.strip() or str(h.get("match_text", "") or "").strip())
    parts: list[str] = [f"<strong>{title}</strong>"]
    pos = esc(h.get("pos", "") or "")
    root = esc(h.get("word_root", "") or "")
    meta_bits = [b for b in (pos, root) if b]
    if meta_bits:
        parts.append(f'<span class="vocab-tip-meta">{" · ".join(meta_bits)}</span>')
    defn = esc(h.get("definition", "") or "")
    if defn:
        parts.append(f'<span class="vocab-tip-def">{defn}</span>')
    note = esc(h.get("note", "") or "")
    if note:
        parts.append(f'<small class="vocab-tip-note">{note}</small>')
    return "<br>".join(parts)


def _annotate_narration_html(narration_plain: str, vocab: dict[str, Any] | None) -> str:
    """Wrap ``match_text`` hits from *vocab* in interactive spans; escape-safe."""
    if not vocab or not isinstance(vocab, dict):
        return html.escape(narration_plain, quote=False)
    data = vocab.get("data")
    if not isinstance(data, list) or not data:
        return html.escape(narration_plain, quote=False)
    items: list[dict[str, Any]] = []
    for h in data:
        if not isinstance(h, dict):
            continue
        mt = h.get("match_text")
        if not isinstance(mt, str) or not mt.strip():
            continue
        items.append(h)
    if not items:
        return html.escape(narration_plain, quote=False)
    items.sort(key=lambda h: -len(str(h["match_text"])))
    used: list[tuple[int, int]] = []
    placements: list[tuple[int, int, dict[str, Any]]] = []
    text = narration_plain
    for h in items:
        needle = str(h["match_text"])
        start_search = 0
        while True:
            i = text.find(needle, start_search)
            if i < 0:
                break
            end = i + len(needle)
            cand = (i, end)
            if any(_ranges_overlap(cand, u) for u in used):
                start_search = i + 1
                continue
            used.append(cand)
            placements.append((i, end, h))
            break
    placements.sort(key=lambda x: x[0])
    parts: list[str] = []
    cursor = 0
    for start_idx, end, h in placements:
        parts.append(html.escape(text[cursor:start_idx], quote=False))
        phrase_plain = text[start_idx:end]
        inner = html.escape(phrase_plain, quote=False)
        tip_inner = _vocab_tooltip_inner_html(h, phrase_plain)
        parts.append(
            '<span class="vocab-hl" role="button" tabindex="0" aria-expanded="false">'
            f"{inner}"
            f'<span class="vocab-tooltip" role="tooltip">{tip_inner}</span>'
            "</span>"
        )
        cursor = end
    parts.append(html.escape(text[cursor:], quote=False))
    return "".join(parts)


def _translation_block_html(seg: StudyCardSegment) -> str:
    vc = seg.vocab_study_card
    if not vc or not isinstance(vc, dict):
        return ""
    ft = vc.get("full_translation")
    if not isinstance(ft, str):
        return ""
    trans = ft.strip()
    if not trans:
        return ""
    inner = html.escape(trans, quote=False)
    return (
        '<details class="vocab-translation">\n'
        '  <summary class="vocab-translation-summary">参考译文</summary>\n'
        f'  <div class="vocab-translation-inner">{inner}</div>\n'
        "</details>\n"
    )


def _segment_title(segment_index: int, scene_title_zh: str | None) -> str:
    label = (scene_title_zh or "").strip() or "旁白片段"
    return f"第 {segment_index} 场景 | {html.escape(label)}"


def _render_frame_carousel(
    *,
    segment_index: int,
    selected: tuple[FramePoolEntry, ...],
    hrefs: tuple[str | None, ...],
) -> str:
    """One bordered box: multiple frames with left/right click to change slide."""
    if not selected:
        return (
            '<div class="frame-carousel frame-carousel-empty">\n'
            '  <div class="frame-slides">\n'
            '    <div class="frame-slide-placeholder">本段时间窗内无可用帧池条目</div>\n'
            "  </div>\n"
            '  <div class="frame-caption frame-caption-muted">请检查 manifest 与时间范围是否匹配</div>\n'
            "</div>\n"
        )

    pairs = list(zip(selected, hrefs))
    parts: list[str] = [
        f'<div class="frame-carousel" data-frame-carousel data-segment="{int(segment_index)}">\n',
        '  <div class="frame-slides">\n',
    ]
    for i, (ent, href) in enumerate(pairs):
        # 彻底移除帧相关信息（文件名、时间、shot），不再写入任何 data 属性
        active = " is-active" if i == 0 else ""
        parts.append(f'    <div class="frame-slide{active}">\n')
        if href:
            parts.append(
                "      "
                f'<img src="{html.escape(href, quote=True)}" '
                f'alt="{html.escape(f"电影画面 shot {ent.shot_id}", quote=True)}" '
                ">\n"
            )
        else:
            parts.append(
                "      "
                '<div class="frame-slide-missing">'
                f"未找到帧文件: {html.escape(str(ent.image_ref))}"
                "</div>\n"
            )
        parts.append("    </div>\n")
    parts.append("  </div>\n")
    parts.append(
        '  <button type="button" class="frame-nav frame-nav-prev" '
        'aria-label="上一张">&#8249;</button>\n'
        '  <button type="button" class="frame-nav frame-nav-next" '
        'aria-label="下一张">&#8250;</button>\n'
        '  <div class="frame-counter"><span class="cur">1</span> / <span class="total">'
        f"{len(pairs)}</span></div>\n"
        "</div>\n"
    )
    return "".join(parts)


def _render_segment_card(
    *,
    segment_index: int,
    seg: StudyCardSegment,
    selected: tuple[FramePoolEntry, ...],
    hrefs: tuple[str | None, ...],
) -> str:
    scene_zh = seg.scene_title_zh
    start_sec = seg.start_sec
    end_sec = seg.end_sec
    time_badge = f"{format_media_timestamp(start_sec)} – {format_media_timestamp(end_sec)}"

    # Study cards intentionally show the original vision narration, not polished/TTS text.
    narration = seg.narration_text.strip()
    narration_html = _annotate_narration_html(narration, seg.vocab_study_card)
    translation_html = _translation_block_html(seg)

    prev_line = _subtitle_display(seg.prev_subtitle_text)
    next_line = _subtitle_display(seg.next_subtitle_text)

    img_block = _render_frame_carousel(
        segment_index=segment_index,
        selected=selected,
        hrefs=hrefs,
    )

    return (
        '<div class="segment-card">\n'
        '  <div class="card-header">\n'
        f"    <div class=\"segment-title\">{_segment_title(segment_index, scene_zh)}</div>\n"
        f'    <div class="time-badge">{html.escape(time_badge)}</div>\n'
        "  </div>\n"
        '  <div class="card-body">\n'
        '    <div class="reference-box text-ref">\n'
        '      <div class="reference-title">【紧邻原片字幕 / 台词参考】</div>\n'
        '      <div class="subtitle-line"><strong>前一条台词：</strong>'
        f"{html.escape(prev_line)}</div>\n"
        '      <div class="subtitle-line"><strong>后一条台词：</strong>'
        f"{html.escape(next_line)}</div>\n"
        "    </div>\n"
        '    <div class="study-grid">\n'
        f"      {img_block}\n"
        '      <div class="text-column">\n'
        '        <div class="column-title">【画面理解生成的原始旁白】</div>\n'
        f'        <div class="content-text">{narration_html}</div>\n'
        f"{translation_html}"
        "      </div>\n"
        "    </div>\n"
        "  </div>\n"
        "</div>\n"
    )


def build_instruction_html(*, embed_images: bool, embedded_frame_count: int) -> str:
    if embed_images:
        inner = (
            "<strong>提示：</strong>帧图已以 Base64 嵌入本页，"
            f"共 <strong>{embedded_frame_count}</strong> 张引用；"
            "单文件即可离线浏览，无需 <code>assets/</code> 目录。"
            "同一段含多帧时，可在左侧画面<strong>左右边缘</strong>点击切换上一张 / 下一张。"
        )
    elif embedded_frame_count == 0:
        inner = (
            "<strong>提示：</strong>图片位于 HTML 同级的 <code>study_cards_assets/frames/</code>；"
            "若某段无图，请检查 manifest 与片段时间窗。"
        )
    else:
        inner = (
            "<strong>提示：</strong>帧图已导出到 <code>study_cards_assets/frames/</code>，"
            "请保持与 HTML 的相对路径不变以便离线浏览。"
            "同一段多帧时在左侧画面左右边缘点击可切换。"
        )
    return f'<div class="instruction-box">{inner}</div>'


def export_study_cards_html(
    *,
    document: StudyCardsDocument,
    pool_root: Path,
    output_html: Path,
    embed_images: bool = True,
) -> None:
    """Write *output_html* study cards for *document*.

    When *embed_images* is True (default), frame files are read from *pool_root* and
    embedded as ``data:image/...;base64,...`` URLs (no ``assets/`` directory).
    When False, frames are copied to ``study_cards_assets/frames/`` next to the HTML file.
    """
    styles = _load_styles()
    entries = load_manifest_from_pool_dir(pool_root)
    segs = document.segments

    out_dir = output_html.parent.resolve()
    frames_dir: Path | None = None
    if not embed_images:
        frames_dir = out_dir / "study_cards_assets" / "frames"
        if frames_dir.parent.exists():
            shutil.rmtree(frames_dir.parent)
        frames_dir.mkdir(parents=True, exist_ok=True)

    cards_parts: list[str] = []
    embedded_count = 0

    for idx, seg in enumerate(segs, start=1):
        start_sec = seg.start_sec
        end_sec = seg.end_sec
        picked = select_frames_for_segment(entries, start_sec, end_sec)
        if embed_images:
            hrefs = data_urls_for_selected(pool_root.resolve(), picked)
            embedded_count += sum(1 for h in hrefs if h)
        else:
            assert frames_dir is not None
            hrefs = copy_selected_frames(
                pool_root=pool_root.resolve(),
                selected=picked,
                frames_dest_dir=frames_dir,
            )
            embedded_count += sum(1 for h in hrefs if h)

        cards_parts.append(
            _render_segment_card(
                segment_index=idx,
                seg=seg,
                selected=picked,
                hrefs=hrefs,
            )
        )

    instruction_block = (
        build_instruction_html(
            embed_images=embed_images,
            embedded_frame_count=embedded_count,
        )
        + "\n"
        if not embed_images
        else ""
    )
    esc_title = html.escape(document.title, quote=False)
    cards_html = "".join(cards_parts)

    doc = (
        "<!DOCTYPE html>\n"
        '<html lang="zh-CN">\n'
        "<head>\n"
        '  <meta charset="UTF-8">\n'
        '  <meta name="viewport" content="width=device-width, initial-scale=1.0">\n'
        f"  <title>{esc_title}</title>\n"
        "  <style>\n"
        f"{styles}\n"
        "  </style>\n"
        "</head>\n"
        "<body>\n"
        '<div class="container">\n'
        "<header>\n"
        f"  <h1>{esc_title}</h1>\n"
        "</header>\n"
        f"{instruction_block}"
        '<div class="toolbar">\n'
        '  <button class="btn" type="button" onclick="toggleReference()">'
        "切换台词参考显示/隐藏</button>\n"
        "</div>\n"
        f"{cards_html}\n"
        "</div>\n"
        "<script>\n"
        "function toggleReference() {\n"
        "  const refs = document.querySelectorAll('.text-ref');\n"
        "  refs.forEach(ref => {\n"
        "    if (ref.style.display === 'none') {\n"
        "      ref.style.display = 'block';\n"
        "    } else {\n"
        "      ref.style.display = 'none';\n"
        "    }\n"
        "  });\n"
        "}\n"
        "function initFrameCarousels() {\n"
        "  document.querySelectorAll('[data-frame-carousel]').forEach((root) => {\n"
        "    const slides = root.querySelectorAll('.frame-slide');\n"
        "    const prevBtn = root.querySelector('.frame-nav-prev');\n"
        "    const nextBtn = root.querySelector('.frame-nav-next');\n"
        "    const caption = root.querySelector('.frame-caption');\n"
        "    const curEl = root.querySelector('.frame-counter .cur');\n"
        "    const n = slides.length;\n"
        "    if (!n) return;\n"
        "    let idx = 0;\n"
        "    const tipFor = (i) => {\n"
        "      const s = slides[i];\n"
        "      return (s && s.getAttribute('data-tip')) || '';\n"
        "    };\n"
        "    const apply = () => {\n"
        "      slides.forEach((s, i) => {\n"
        "        if (i === idx) s.classList.add('is-active');\n"
        "        else s.classList.remove('is-active');\n"
        "      });\n"
        "      if (caption) caption.textContent = tipFor(idx);\n"
        "      if (curEl) curEl.textContent = String(idx + 1);\n"
        "      if (prevBtn) prevBtn.disabled = idx <= 0;\n"
        "      if (nextBtn) nextBtn.disabled = idx >= n - 1;\n"
        "    };\n"
        "    if (prevBtn) {\n"
        "      prevBtn.addEventListener('click', () => {\n"
        "        if (idx > 0) {\n"
        "          idx -= 1;\n"
        "          apply();\n"
        "        }\n"
        "      });\n"
        "    }\n"
        "    if (nextBtn) {\n"
        "      nextBtn.addEventListener('click', () => {\n"
        "        if (idx < n - 1) {\n"
        "          idx += 1;\n"
        "          apply();\n"
        "        }\n"
        "      });\n"
        "    }\n"
        "    apply();\n"
        "  });\n"
        "}\n"
        "function initVocabTooltips() {\n"
        "  document.addEventListener('click', (e) => {\n"
        "    const t = e.target;\n"
        "    if (!(t instanceof Element)) return;\n"
        "    const hl = t.closest('.vocab-hl');\n"
        "    if (hl) {\n"
        "      const was = hl.classList.contains('active');\n"
        "      document.querySelectorAll('.vocab-hl.active').forEach((el) => {\n"
        "        el.classList.remove('active');\n"
        "        el.setAttribute('aria-expanded', 'false');\n"
        "      });\n"
        "      if (!was) {\n"
        "        hl.classList.add('active');\n"
        "        hl.setAttribute('aria-expanded', 'true');\n"
        "      }\n"
        "      return;\n"
        "    }\n"
        "    document.querySelectorAll('.vocab-hl.active').forEach((el) => {\n"
        "      el.classList.remove('active');\n"
        "      el.setAttribute('aria-expanded', 'false');\n"
        "    });\n"
        "  });\n"
        "  document.addEventListener('keydown', (e) => {\n"
        "    if (e.key === 'Escape') {\n"
        "      document.querySelectorAll('.vocab-hl.active').forEach((el) => {\n"
        "        el.classList.remove('active');\n"
        "        el.setAttribute('aria-expanded', 'false');\n"
        "      });\n"
        "      return;\n"
        "    }\n"
        "    const t = e.target;\n"
        "    if (!(t instanceof Element)) return;\n"
        "    const hl = t.closest('.vocab-hl');\n"
        "    if (!hl || (e.key !== 'Enter' && e.key !== ' ')) return;\n"
        "    e.preventDefault();\n"
        "    const was = hl.classList.contains('active');\n"
        "    document.querySelectorAll('.vocab-hl.active').forEach((el) => {\n"
        "      el.classList.remove('active');\n"
        "      el.setAttribute('aria-expanded', 'false');\n"
        "    });\n"
        "    if (!was) {\n"
        "      hl.classList.add('active');\n"
        "      hl.setAttribute('aria-expanded', 'true');\n"
        "    }\n"
        "  });\n"
        "}\n"
        "function initStudyCardsPage() {\n"
        "  initFrameCarousels();\n"
        "  initVocabTooltips();\n"
        "}\n"
        "if (document.readyState === 'loading') {\n"
        "  document.addEventListener('DOMContentLoaded', initStudyCardsPage);\n"
        "} else {\n"
        "  initStudyCardsPage();\n"
        "}\n"
        "</script>\n"
        "</body>\n"
        "</html>\n"
    )

    output_html.parent.mkdir(parents=True, exist_ok=True)
    output_html.write_text(doc, encoding="utf-8")


def build_export_study_html_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Export narrated segments to a static study-card HTML page (no LLM)."
    )
    p.add_argument(
        "--pipeline-json",
        required=True,
        help="Path to pipeline JSON (must contain narratedSegments)",
    )
    p.add_argument(
        "--frame-pool-dir",
        required=True,
        help="Frame pool directory containing manifest.jsonl and image files",
    )
    p.add_argument(
        "--output-html",
        required=True,
        help="Output HTML path (with --external-assets, frames go to sibling study_cards_assets/frames/)",
    )
    p.add_argument(
        "--external-assets",
        action="store_true",
        help="Copy frames to study_cards_assets/frames/ instead of embedding as Base64",
    )
    p.add_argument(
        "--page-title",
        default="NarraLingo · Scene Study Cards",
        help="HTML <title> and header text",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    args = build_export_study_html_parser().parse_args(argv)
    pipeline = json.loads(Path(args.pipeline_json).read_text(encoding="utf-8"))
    from movie_pipeline.study_cards_export import build_study_cards_document

    document = build_study_cards_document(
        payload=pipeline,
        page_title=str(args.page_title),
    )
    export_study_cards_html(
        document=document,
        pool_root=Path(args.frame_pool_dir),
        output_html=Path(args.output_html),
        embed_images=not bool(args.external_assets),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
