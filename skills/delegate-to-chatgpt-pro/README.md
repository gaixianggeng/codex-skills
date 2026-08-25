# 委派给 ChatGPT Pro

`delegate-to-chatgpt-pro` 用于把复杂工程任务或 GitHub PR 审查交给网页版 ChatGPT Pro，同时由 Codex 继续担任总负责人。公开且版本一致的 PR 优先只发送 canonical PR 链接，不上传重复源码；私有、未发布或与本地不一致的代码只提供最小脱敏源码包。Codex 会独立复核结论、补丁和测试。Skill 不会上传密钥、环境变量、用户数据或浏览器凭据。

```text
$delegate-to-chatgpt-pro 修复支付回调偶发重复入账的问题。
```
