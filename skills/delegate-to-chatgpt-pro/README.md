# 委派给 ChatGPT Pro

`delegate-to-chatgpt-pro` 用于把复杂工程任务交给网页版 ChatGPT Pro 协助处理，同时由 Codex 继续担任总负责人。它会先检查本地仓库，整理最小且脱敏的代码上下文，再通过 Codex 内置浏览器发起任务、收集补丁，并在本地独立审查和测试。适合复杂缺陷、架构方案、迁移和安全审查；简单修改通常无需使用。Skill 不会上传密钥、环境变量、用户数据或浏览器凭据。

```text
$delegate-to-chatgpt-pro 修复支付回调偶发重复入账的问题。
```
