---
name: codex-luna-worker
description: 在 Sol 主线程执行工程任务时，根据 auto、sol-only 或 ask-each-time 路由偏好，判断是否把边界明确、独立、可验收的执行项交给 GPT-5.6 Luna Max，并由主 Agent 最终验收。用户提到 Luna、Luna Max、降低 Sol 使用成本、自动调度子代理、配置 luna_worker、批量执行清晰小任务或让主 Agent 规划后交给低成本 Worker 时使用；不要用于需求模糊、架构决策、多个 Agent 同改一批文件或无人验收的高风险操作。
---

# Codex Luna Worker

主 Agent 保留需求、决策和最终验收，主线程模型不因委派而改变；本机主线程可以继续使用 GPT-5.6 Sol，只有收敛后的执行任务交给 GPT-5.6 Luna Max。先解析路由偏好，再判断任务是否适合委派，优先尝试原生自定义 Agent；只有实际调用不可用时才改走隔离的 CLI 任务。

## 解析路由偏好

按以下优先级解析，前者覆盖后者：

1. 用户在当前请求中的明确指令。
2. 当前目录适用的最近一层 `AGENTS.md`。
3. 当前对话中已经确认的选择。
4. 个人级 `~/.codex/AGENTS.md`。

支持三种模式：

- `auto`：推荐。主 Agent 自己判断是否使用 Luna Max；每次自动委派前只做一句简短进度告知，不重复询问模型选择，完成后独立验收。
- `sol-only`：当前任务全部由主 Agent 完成，不调用 Luna。
- `ask-each-time`：每次准备委派 Luna 前都先询问用户。

以下说法视为当前任务的临时覆盖，不改持久偏好：

- “这次只用 Sol” → `sol-only`
- “这次强制 Luna Max” → 在满足安全边界后直接委派
- “这次自动调度” → `auto`

如果没有任何偏好，且已经发现一个适合 Luna 的任务，在第一次实际委派前只询问一次。用户明确说“以后”“默认”或要求本机长期生效时，才把选择写入 `~/.codex/AGENTS.md`；只对单个仓库生效时，写入仓库级 `AGENTS.md`。Skill 不会在尚未被发现或调用前自行弹出问题，因此长期自动调度必须配合 `AGENTS.md`。

`auto` 不是“所有任务都用 Luna”。不要设置全局 `agents.default_subagent_model = "gpt-5.6-luna"` 来实现本流程，因为这会连 reviewer、explorer 等其他子代理一起改成 Luna。

## 判断是否适合 Luna

1. 先读取当前仓库适用的 `AGENTS.md`，继承文件范围、验证命令、权限和并发约束；更具体的项目规则优先。
2. 只在任务同时满足以下条件时委派：
   - 能用一句话说明唯一目标。
   - 输入、允许修改的文件和禁止范围明确。
   - 有可执行的完成标准或验证命令。
   - 失败不会直接造成生产、资金、账户或数据损失。
   - 能减少主线程的执行噪音或成本，或者存在真实的并行收益。
3. 遇到需求澄清、架构取舍、安全结论、跨模块协调、最终发布判断或高影响外部操作时，由主 Agent 处理。先拆小，再把收敛后的执行项交给 Luna。
4. 几分钟内即可由主 Agent 完成且不会污染上下文的小任务直接处理，避免为委派付出额外协调成本。
5. 默认一次只运行一个 Luna 任务。只有多个任务互不依赖、不会修改同一批文件且并行收益明显时才并行，并遵守项目的子代理数量上限。

适合的任务包括代码搜索、日志归类、单点修改、补一组明确测试、文档差异整理、结构化提取和批量机械检查。

## 选择执行通道

首次使用、Codex 更新后或原生调用失败后，运行：

```bash
codex debug models | jq -r '.models[] | select(.slug == "gpt-5.6-sol" or .slug == "gpt-5.6-luna") | [.slug, .multi_agent_version, ([.supported_reasoning_levels[].effort] | join(","))] | @tsv'
```

`multi_agent_version` 只用于诊断，不能单独证明两个模型无法协作。按以下顺序选择：

1. 当前 Codex 已发现 `luna_worker` 时，真实调用原生自定义 Agent，等待它完成后再验收。
2. 当前多 Agent 工具未提供该自定义 Agent，或原生调用实际报错时，运行 `scripts/run_luna_worker.sh` 创建独立、临时的 Luna 任务。
3. 不修改内部模型目录、不伪装模型版本、不降低主线程模型，也不切换实验性 feature flag 来绕过兼容限制。

若系统没有 `jq`，读取 `codex debug models` 的 JSON，并核对同名字段即可。

## 选择推理强度

- 默认使用 `max`，与 `assets/luna-worker.toml` 的 Luna Max 配置保持一致。
- 用户更重视延迟时，可将清晰的格式转换、分类、搜索或重复性检查降到 `medium`。
- 边界明确但不需要最大推理深度的实现或排障可用 `xhigh`。

Luna 单价降低不等于延迟消失；`max` 仍可能更慢。若任务很小，主 Agent 直接完成通常更快。

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

### 自动路由时的用户体验

`auto` 模式下，准备调用 Luna 时先用 commentary 告知一句，例如：“这个测试排查边界清楚，我交给 Luna Max 执行，完成后我会检查 diff 并复跑测试。”这是进度通知，不是确认请求。

只有以下情况需要暂停并询问：

- 需要新的权限、外部写入、发布、删除或其他高影响动作。
- 任务范围发生实质扩张，必须由用户做产品或架构取舍。
- 并行任务将修改同一文件或存在不可安全自动化解的冲突。
- 当前模式本来就是 `ask-each-time`。

不要仅因为选择了 Luna，就在 `auto` 模式下重复询问。

### 原生自定义 Agent

要求 `luna_worker` 严格执行完整任务包，等待它结束，不让主 Agent 同时修改相同文件。若尚未安装自定义 Agent，从 `assets/luna-worker.toml` 安装到 `~/.codex/agents/luna-worker.toml`；目标已存在时先比较，不直接覆盖。

### 独立 CLI 任务

从本 Skill 所在目录调用脚本。只读调查保留默认 sandbox；明确授权修改仓库时才使用 `workspace-write`。脚本默认使用 Luna Max。

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

用户要求安装或长期启用时：

1. 检查 `codex --version` 和 `codex debug models`，确认 Luna 及所选推理强度可用。
2. 检查 `~/.codex/agents/luna-worker.toml`；存在时先展示差异并保留用户定制。
3. 将 `assets/luna-worker.toml` 安装到目标位置，并用 Python `tomllib` 或等价 TOML 解析器验证语法。
4. 将完整 Skill 目录安装到 Codex 可发现的个人 Skills 目录；优先使用当前机器已经采用的目录约定。
5. 按用户确认的模式更新个人或项目 `AGENTS.md`。`auto` 的个人级示例：

   ```md
   ## Luna 任务路由

   - 路由模式：`auto`。
   - 主线程保持当前模型；每个执行阶段先判断是否把边界明确、独立、可验证的子任务交给 `$codex-luna-worker`。
   - 自动调用时只做简短进度告知，不重复征求模型选择确认。
   - 主 Agent 等待 Luna 完成，独立检查 diff 或证据，并运行验证。
   - 模糊、高风险或会与主线程修改同一文件的任务由主 Agent 处理。
   ```

6. 运行一次只读、无工具调用的 Luna 测试，并记录实际模型、推理强度、sandbox 和最终输出。
7. 新配置未被当前会话发现时，提醒用户新建任务或重启 Codex；`AGENTS.md` 在新任务启动时重新加载。
