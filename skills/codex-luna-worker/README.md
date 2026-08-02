# Codex Luna Worker

`codex-luna-worker` 把边界明确、可验收的执行任务交给 GPT-5.6 Luna，主 Agent 继续负责拆解、决策和最终验收。它会优先尝试原生 `luna_worker`；实际调用不可用时，改用隔离的临时 Luna CLI 任务。适合代码搜索、单点修改、测试排查和结构化批处理，不适合模糊需求、架构决策或多个 Agent 同改一批文件。

```text
$codex-luna-worker 用 Luna Max 排查这条失败测试，并给出文件与行号证据。
```
