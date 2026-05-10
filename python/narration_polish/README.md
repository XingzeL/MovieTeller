# narration_polish

Rewrite generated narration so later TTS is more likely to fit inside the target
segment duration.

This module is text-only. It does not inspect video frames itself. Typical flow:

1. `subtitle_analysis` finds no-subtitle gaps
2. `narration` generates raw English narration for each gap
3. `narration_polish` rewrites that narration for TTS fit
4. a future speech module turns the polished text into audio

## Setup

```bash
source .venv/bin/activate
python -m pip install -e python/movieteller_config -e python/narration_polish
```

## CLI

```bash
source .venv/bin/activate
python -m narration_polish \
  --text "A wizard in a gray robe leads a group along a sunlit path." \
  --duration-sec 2.8 \
  --target-wpm 150 \
  --cefr-level B1 \
  --strength medium \
  --json
```

## Output

The module returns:

- original narration text
- polished narration text
- target duration after safety margin
- target / actual word counts
- estimated speech durations
- configured CEFR level and rewrite strength

## Config

Shared settings live in `movieteller_config`:

- `narration_provider_models`
- `narration_provider_model_catalog`
- `narration_model`
- `narration_model_index`
- `narration_polish_enabled`
- `narration_polish_provider`
- `narration_polish_model`
- `narration_polish_model_index`
- `narration_polish_provider_models`
- `narration_polish_provider_model_catalog`
- `narration_polish_target_wpm`
- `narration_polish_cefr_level`
- `narration_polish_strength`
- `narration_polish_safety_margin_sec`
