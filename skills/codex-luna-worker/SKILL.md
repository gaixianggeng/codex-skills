---
name: codex-luna-worker
description: 将边界明确、可验收的 Codex 任务路由给 GPT-5.6 Luna，并在 Luna 无法作为当前主模型的原生子代理时，通过独立的 codex exec 任务安全执行。用户提到 Luna、Luna Max、降低 Sol 使用成本、配置 luna_worker、批量执行清晰小任务或让主 Agent 规划后交给低成本 Worker 时使用；不要用于需求模糊、架构决策、多个 Agent 同改一批文件或无人验收的高风险操作。
---

# Codex Luna Worker

让主 Agent 保留需求、决策和最终验收，把一个独立、边界清楚的执行任务交给 GPT-5.6 Luna。先判断任务是否适合委派，再优先尝试原生自定义 Agent；只有实际调用不可用时才改走隔离的 CLI 任务，不用内部模型目录覆盖等脆弱绕过方案。

## 判断是否适合 Luna

1. 先读取当前仓库适用的 `AGENTS.md`，继承文件范围、验证命令、权限和并发约束。
2. 只在任务同时满足以下条件时委派：
   - 能用一句话说明唯一目标。
   - 输入、允许修改的文件和禁止范围明确。
   - 有可执行的完成标准或验证命令。
   - 失败不会直接造成生产、资金、账户或数据损失。
3. 遇到需求澄清、架构取舍、安全结论、跨模块协调或最终发布判断时，由主 Agent 处理。先拆小，再把收敛后的执行项交给 Luna。
4. 默认一次只运行一个 Luna 任务。只有多个任务互不依赖、不会修改同一批文件且并行收益明显时才并行，并遵守项目的子代理数量上限。

适合的任务包括代码搜索、日志归类、单点修改、补一组明确测试、文档差异整理、结构化提取和批量机械检查。

## 选择执行通道

首次使用、Codex 更新后或原生调用失败后，运行：

```bash
codex debug models | jq -r '.models[] | select(.slug == "gpt-5.6-sol" or .slug == "gpt-5.6-luna") | [.slug, .multi_agent_version, ([.supported_reasoning_levels[].effort] | join(","))] | @tsv'
```

`multi_agent_version` 只用于诊断，不能单独证明两个模型无法协作。按以下顺序选择：

1. 当前 Codex 已发现 `luna_worker` 时，先真实调用一次原生自定义 Agent，等待它完成后再验收。
2. 当前多 Agent 工具未提供该自定义 Agent，或原生调用实际报错时，运行 `scripts/run_luna_worker.sh` 创建独立、临时的 Luna 任务。
3. 不修改内部模型目录、不伪装模型版本、不降低主线程模型，也不切换实验性 feature flag 来绕过兼容限制。

若系统没有 `jq`，读取 `codex debug models` 的 JSON，并核对同名字段即可。

## 选择推理强度

- `medium`：格式转换、分类、简单搜索和重复性检查。
- `xhigh`：有明确验收标准的代码实现或排障，作为复杂执行任务的常用起点。
- `max`：用户明确要求 Luna Max，或任务边界清楚但需要深入推理时使用。

不要因为 Luna 单价低就对所有任务固定使用 `max`。更高强度仍会增加 token 和等待时间。

## 编写任务包

委派前补齐以下字段，不把模糊目标直接转交给 Worker：

```text
任务目标：只写一个可验收结果。
工作目录：仓库绝对路径。
允许范围：可以读取和修改的文件或模块。
禁止事项：不得触碰的文件、外部系统和行为。
已知上下文：完成任务必需的事实，不粘贴无关聊天记录。
完成标准：结果必须满足的条件。
验证命令：可直接执行的检查或测试。
返回格式：结果、文件路径、验证证据、注意事项；禁止只回复“已完成”。
```

不要在任务包中放入密码、令牌、Cookie、私钥、生产连接信息或无关个人资料。

## 执行任务

### 原生自定义 Agent

要求 `luna_worker` 严格执行完整任务包，等待它结束，不让主 Agent 同时修改相同文件。若尚未安装自定义 Agent，从 `assets/luna-worker.toml` 安装到 `~/.codex/agents/luna-worker.toml`；目标已存在时先比较，不直接覆盖。

### 独立 CLI 任务

从本 Skill 所在目录调用脚本。只读调查保留默认 sandbox；明确授权修改仓库时才使用 `workspace-write`。

```bash
LUNA_SKILL_DIR=/absolute/path/to/codex-luna-worker
"$LUNA_SKILL_DIR/scripts/run_luna_worker.sh" \
  --effort max \
  --sandbox read-only \
  --workdir /absolute/path/to/repository <<'LUNA_TASK'
任务目标：找出指定测试失败的直接原因。
工作目录：/absolute/path/to/repository
允许范围：读取源码、测试和本地日志；不修改文件。
禁止事项：不访问生产环境，不输出任何凭据。
已知上下文：测试命令及失败输出已在当前仓库中可复现。
完成标准：给出一个有文件与行号证据支持的根因。
验证命令：运行指定失败测试一次。
返回格式：根因、证据、验证结果、仍不确定之处。
LUNA_TASK
```

脚本固定使用 `gpt-5.6-luna`、临时会话和 `approval=never`。需要新权限的动作会失败并返回主 Agent，不会在后台等待审批。

## 独立验收

Luna 返回后，主 Agent 必须：

1. 对比任务前后的 `git status --short`，确认没有越界文件。
2. 阅读实际 diff 或证据，不把 Worker 的自述当验证结果。
3. 运行任务包中的验证命令；修改代码时至少执行相关测试和 `git diff --check`。
4. 若结果接近完成但漏掉一项明确标准，只给一次针对性修正任务；若仍失败、范围开始扩张或需要新决策，停止委派并由主 Agent 接管。
5. 向用户报告执行通道、模型与强度、结果、改动文件、验证证据和重要边界。

## 配置本机

用户要求安装时：

1. 检查 `codex --version` 和 `codex debug models`，确认 Luna 及所选推理强度可用。
2. 检查 `~/.codex/agents/luna-worker.toml`；存在时先展示差异并保留用户定制。
3. 将 `assets/luna-worker.toml` 安装到目标位置，并用 Python `tomllib` 或等价 TOML 解析器验证语法。
4. 将完整 Skill 目录安装到 Codex 可发现的个人 Skills 目录；优先使用当前机器已经采用的目录约定。
5. 运行一次只读、无工具调用的 Luna 测试，并记录实际模型、推理强度、sandbox 和最终输出。
6. 新配置未被当前会话发现时，提醒用户新建任务或重启 Codex。
