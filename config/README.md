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
- **模型 per slug**：`provider_models`（或 **`PROVIDER_MODELS_JSON`**）为每个 slug 指定 **单个** 模型 id。
- **同一 slug 多个可选模型**：`provider_model_catalog`（或 **`PROVIDER_MODEL_CATALOG_JSON`**）为 slug 提供 **列表**；再用 **`NARRATION_MODEL`**（明确 model id）或 **`NARRATION_MODEL_INDEX`**（选列表中的第几项，仅对当前 `narration_provider`）切换；未指定时仍可用 **`PROVIDER_MODELS_JSON`** 钉死其一（优先级高于 catalog）。以上都未命中时回退 **`narration_image_model`** / **`NARRATION_IMAGE_MODEL`**。
- **环境变量约定**：任意 **`YOUR_VENDOR_API_KEY`** → slug `your_vendor`；任意 **`YOUR_VENDOR_BASE_URL`** → slug `your_vendor`。也可用 **`API_KEYS_JSON`** / **`API_BASE_URLS_JSON`** / **`PROVIDER_MODELS_JSON`** / **`PROVIDER_MODEL_CATALOG_JSON`** 集中写 JSON（优先级更高）；JSON 值支持整段 **`${VAR}`**、**`$$VAR`** 或 **`$VAR`**，从环境变量解析，便于不写死明文。

示例 `config/local.yaml`：

```yaml
openai_api_key: sk-...   # optional legacy field; same as api_keys.openai
api_keys:
  openai: sk-...
  modelscope: "$MODELSCOPE_API_KEY_FREE"
api_base_urls:
  modelscope: https://api-inference.modelscope.cn/v1
provider_models:
  openai: gpt-4o
  modelscope: qwen/Qwen-VL-Max
provider_model_catalog:
  volcengine:
    - doubao-seed-2-0-mini-260428
    - doubao-seed-1-6-flash-250615
narration_image_model: gpt-4o-mini   # 仅当某 slug 未出现在 provider_models / catalog 时使用
max_frames_per_segment: 16
```

ModelScope 完整示例（密钥占位、`/v1/chat/completions`）见 **[.env.example](../.env.example)** 与 **`local.yaml.example`** 中的「ModelScope」段落。

Priority: **environment variables** override this file; this file overrides packaged defaults.

Git ignores `local.yaml` — do not commit secrets.
