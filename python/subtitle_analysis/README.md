# subtitle_analysis

Analyze `.srt` subtitle output and derive **non-subtitle intervals** that are good
candidates for frame extraction and narration. It can also directly call
`narration` and emit a timed JSON script list.

This module does **not** run ASR itself. It assumes subtitles already exist
(for example from `subtitle_extraction` / `videocaptioner transcribe`).

## What It Does

Given subtitle cues, it computes:

- merged subtitle-covered spans
- gaps with no subtitles
- filtered narration candidates, optionally trimmed away from subtitle edges

Those candidate gaps can then be passed to `narration.narrate_segment(...)`.

## Setup

```bash
source .venv/bin/activate
python -m pip install -e python/subtitle_extraction
python -m pip install -e python/subtitle_analysis
```

If you also want the one-click narration pipeline, install `narration` in the same
`.venv`:

```bash
python -m pip install -e python/movieteller_config -e python/narration -e python/narration_polish
```

## CLI

Analyze an extracted `.srt` and emit JSON:

```bash
source .venv/bin/activate
python -m subtitle_analysis \
  --srt subtitle_example.extracted.srt \
  --video subtitle_example.mp4 \
  --min-gap-sec 1.5 \
  --subtitle-guard-sec 0.25 \
  --json
```

Run the full pipeline and generate narration JSON for the derived gaps:

```bash
source .venv/bin/activate
python -m subtitle_analysis \
  --srt subtitle_example.extracted.srt \
  --video subtitle_example.mp4 \
  --min-gap-sec 1.5 \
  --subtitle-guard-sec 0.25 \
  --narrate \
  --polish \
  --polish-provider glm \
  --polish-model-index 0 \
  --polish-target-wpm 150 \
  --polish-cefr-level B1 \
  --max-candidates 3 \
  --json
```

## Python API

```python
from subtitle_analysis import analyze_subtitle_file

result = analyze_subtitle_file(
    "subtitle_example.extracted.srt",
    video_path="subtitle_example.mp4",
    min_gap_sec=1.5,
    subtitle_guard_sec=0.25,
)

for seg in result.narration_candidates:
    print(seg.start_sec, seg.end_sec, seg.duration_sec)
```

Then hand the selected gap to `narration`:

```python
from narration import narrate_segment

text = narrate_segment(
    "subtitle_example.mp4",
    start_sec=result.narration_candidates[0].start_sec,
    end_sec=result.narration_candidates[0].end_sec,
)
```

Or do it in one step:

```python
from subtitle_analysis import analyze_and_narrate

payload = analyze_and_narrate(
    srt_path="subtitle_example.extracted.srt",
    video_path="subtitle_example.mp4",
    min_gap_sec=1.5,
    subtitle_guard_sec=0.25,
    max_candidates=3,
    polish=True,
)
```

## Notes

- Internal gaps can be inferred from SRT alone.
- To infer the **trailing** no-subtitle segment after the last subtitle, the module
  needs either `video_duration_sec` or `video_path`.
- `subtitle_guard_sec` trims candidate gaps away from subtitle boundaries so frame
  extraction does not start or stop directly on subtitle speech.
