# Local configuration overrides

仓库里只有 **`local.yaml.example`**（模板，可提交）。你要用的是同目录下的 **`local.yaml`**：把模板复制一份即可：

```bash
cp config/local.yaml.example config/local.yaml
```

`local.yaml` **默认不存在**，且被 `.gitignore` 忽略，所以在文件树里有时看不到——复制后即会出现（若仍不见，检查编辑器是否隐藏 gitignore 文件）。

也可以不写 YAML，只在仓库根目录使用 `.env`（模板见 [.env.example](../.env.example)）。Python 与 Node 都会尝试加载仓库根目录的 `.env`（Python 需在安装 `movieteller-config` 时带上依赖 `python-dotenv`，见 `python/movieteller_config/pyproject.toml`）。

## 当前推荐：统一走 gateway 配置

- `gateway.default_provider`：默认 provider slug
- `gateway.tts_provider`：TTS capability 单独使用的 provider slug
- `api_providers`：provider -> base URL
- `api_keys`：provider -> key
- `model_catalog`：模型白名单
- `model_defaults`：按 capability 指定默认模型
- `tts_defaults`：TTS 默认 voice/rate/volume/pitch/boundary
- `video_defaults`：视频混流默认音量

## 业务默认项

- **`api_keys`**：任意 **slug**（小写标识）→ 密钥；业务代码统一按 slug 取 `get_api_key(slug)`。
- **`api_providers`**：同一 slug → Base URL。
- **旁白润色配置**：`narration_polish_*` 控制 narration 之后、TTS 之前的文本重写，包括是否启用、目标语速、CEFR 难度级别，以及为 TTS 预留的时长 buffer。
- **旁白语音配置**：使用 `model_defaults.tts` + `tts_defaults.*`。
- **TTS provider 路由**：默认跟随 `gateway.default_provider`；若配置 `gateway.tts_provider`，则只有 TTS capability 单独切换 provider。
- **视频混流配置**：`narration_video_*` 控制把旁白音频混回源视频时的音量比例。
- **环境变量约定**：任意 **`YOUR_VENDOR_API_KEY`** → slug `your_vendor`；任意 **`YOUR_VENDOR_BASE_URL`** → slug `your_vendor`。也可用 **`API_KEYS_JSON`** / **`API_PROVIDERS_JSON`** / **`MODEL_DEFAULTS_JSON`** / **`MODEL_CATALOG_JSON`** 集中写 JSON；JSON 值支持整段 **`${VAR}`**、**`$$VAR`** 或 **`$VAR`**，从环境变量解析，便于不写死明文。

推荐示例 `config/local.yaml`：

```yaml
gateway:
  default_provider: newapi
  tts_provider: dashscope

api_keys:
  newapi: "$NEW_API_KEY_NARRATION_FREE"
  dashscope: "$TTS_API_KEY"
api_providers:
  newapi: "http://127.0.0.1:3000/v1"
  dashscope: "https://dashscope.aliyuncs.com/api/v1"
model_catalog:
  - Qwen/Qwen3-VL-30B-A3B-Instruct
  - qwen2.5-7b-instruct
  - qwen3-tts-flash
  - text-embedding-v4
model_defaults:
  narration: "Qwen/Qwen3-VL-30B-A3B-Instruct"
  polish: "qwen2.5-7b-instruct"
  tts: "qwen3-tts-flash"
  embedding: "text-embedding-v4"
narration_polish_enabled: true
narration_polish_target_wpm: 150
narration_polish_cefr_level: B1
narration_polish_strength: medium
narration_polish_safety_margin_sec: 0.2
narration_tts_enabled: true
tts_defaults:
  voice: Cherry
  rate: "+0%"
  volume: "+0%"
  pitch: "+0Hz"
  boundary: SentenceBoundary
video_defaults:
  background_audio_volume: 0.35
  speech_audio_volume: 1.0
max_frames_per_segment: 16
```

ModelScope 完整示例（密钥占位、`/v1/chat/completions`）见 **[.env.example](../.env.example)** 与 **`local.yaml.example`** 中的「ModelScope」段落。

Priority: **environment variables** override this file; this file overrides packaged defaults.

Git ignores `local.yaml` — do not commit secrets.

## VideoCaptioner 字幕提取（subtitle_extraction）

- **`videocaptioner_bin`**：``videocaptioner`` 可执行文件路径；留空则从 PATH 查找。
- **`videocaptioner_asr`**：传给 CLI 的 ``--asr``（``bijian`` / ``jianying`` / ``whisper-api`` / ``whisper-cpp``）。
- **`videocaptioner_language`**：源语言 ISO 639-1 或 ``auto``。
- **`videocaptioner_transcribe_timeout_ms`**：子进程超时（毫秒）；省略或 ``null`` 表示不限制。

对应环境变量：**``VIDEOCAPTIONER_BIN``**、**``VIDEOCAPTIONER_ASR``**、**``VIDEOCAPTIONER_LANGUAGE``**、**``VIDEOCAPTIONER_TRANSCRIBE_TIMEOUT_MS``**。服务端调用 Python 时可用 **``MOVIE_TELLER_PYTHON``** 指定解释器。

HTTP：**``POST /api/extract/subtitles``**，multipart 字段名 **`file`**，响应 JSON 仅含 **`cues`**（``startSec`` / ``endSec`` / ``text``）；临时字幕文件在响应结束后删除。
