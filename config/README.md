# Local configuration overrides

仓库里只有 **`local.yaml.example`**（模板，可提交）。你要用的是同目录下的 **`local.yaml`**：把模板复制一份即可：

```bash
cp config/local.yaml.example config/local.yaml
```

`local.yaml` **默认不存在**，且被 `.gitignore` 忽略，所以在文件树里有时看不到——复制后即会出现（若仍不见，检查编辑器是否隐藏 gitignore 文件）。

也可以不写 YAML，只在仓库根目录使用 `.env`（模板见 [.env.example](../.env.example)）。Python 与 Node 都会尝试加载仓库根目录的 `.env`（Python 需在安装 `movieteller-config` 时带上依赖 `python-dotenv`，见 `python/movieteller_config/pyproject.toml`）。

## 换供应商不必改配置加载代码

- **`api_keys`**：任意 **slug**（小写标识）→ 密钥；业务代码用同一 slug 取 `get_api_key(slug)`。
- **`api_base_urls`**：同一 slug → Base URL（若 HTTP 客户端按 slug 选 endpoint）。
- **旁白专用模型池**：`narration_provider_models` / `narration_provider_model_catalog` 专门给视频旁白用；再通过 **`NARRATION_MODEL`** / **`NARRATION_MODEL_INDEX`** 为当前 `narration_provider` 选择模型。这里建议只放多模态或视觉 narration 友好的模型。
- **旁白润色专用模型池**：`narration_polish_provider_models` / `narration_polish_provider_model_catalog` 专门给文本润色用；再通过 `narration_polish_model` / `narration_polish_model_index` 选择模型。这里建议只放文本模型，避免索引到多模态模型。
- **旁白润色配置**：`narration_polish_*` 控制 narration 之后、TTS 之前的文本重写，包括是否启用、使用哪个 provider、目标语速、CEFR 难度级别，以及为 TTS 预留的时长 buffer。若显式设置 `narration_polish_model`，它仍然高于 index。
- **环境变量约定**：任意 **`YOUR_VENDOR_API_KEY`** → slug `your_vendor`；任意 **`YOUR_VENDOR_BASE_URL`** → slug `your_vendor`。也可用 **`API_KEYS_JSON`** / **`API_BASE_URLS_JSON`** / **`NARRATION_PROVIDER_MODELS_JSON`** / **`NARRATION_PROVIDER_MODEL_CATALOG_JSON`** / **`NARRATION_POLISH_PROVIDER_MODELS_JSON`** / **`NARRATION_POLISH_PROVIDER_MODEL_CATALOG_JSON`** 集中写 JSON（优先级更高）；JSON 值支持整段 **`${VAR}`**、**`$$VAR`** 或 **`$VAR`**，从环境变量解析，便于不写死明文。

示例 `config/local.yaml`：

```yaml
openai_api_key: sk-...   # optional legacy field; same as api_keys.openai
api_keys:
  openai: sk-...
  modelscope: "$MODELSCOPE_API_KEY_FREE"
api_base_urls:
  modelscope: https://api-inference.modelscope.cn/v1
narration_provider_model_catalog:
  volcengine:
    - doubao-seed-1-6-vision-250815
  modelscope:
    - Qwen/Qwen3-VL-30B-A3B-Instruct
narration_polish_provider_model_catalog:
  dashscope:
    - qwen-turbo
    - qwen2.5-7b-instruct
narration_image_model: gpt-4o-mini   # narration/polish 都未命中专用模型池时回退
narration_polish_enabled: true
narration_polish_provider: glm
narration_polish_model_index: 0
narration_polish_target_wpm: 150
narration_polish_cefr_level: B1
narration_polish_strength: medium
narration_polish_safety_margin_sec: 0.2
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
