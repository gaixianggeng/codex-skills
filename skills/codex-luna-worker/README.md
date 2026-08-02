# Codex Luna Worker

让 Sol 主线程保留规划与验收，把边界明确、独立、可验证的执行项交给 Luna Max。支持 `auto`、`sol-only`、`ask-each-time` 三种路由；推荐 `auto`，主 Agent 自动判断并只做进度告知，不反复询问。优先调用原生 `luna_worker`，不可用时回退到隔离的临时 CLI 任务。

```text
$codex-luna-worker 这次自动调度：排查失败测试，完成后由主 Agent 复验。
```
