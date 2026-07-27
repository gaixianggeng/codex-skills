# 来源与许可说明

## 目标

本导航只保存市场目录和安装逻辑，不在 `codex-skills` 仓库中二次打包 295 个第三方
Skill 的源码。

## 来源

- 目录仓库：`infometa/workbuddyskills`
- 上游地址：`https://github.com/infometa/workbuddyskills`
- 固定提交：`d3d5c70a431c571d2e2a2b3bba8ffc4bac802809`
- 目录文件：`CATALOG.md`
- 快照日期：2026-07-27

该上游声明内容来自 WorkBuddy / CodeBuddy 公开市场包，并说明版权归各原作者与相关
产品方所有，仅作学习归档。它不是统一开源许可证；每个 Skill 的许可状态需要分别
检查。

## 为什么不整库镜像

公开可下载不等于获得再次分发、修改或商用授权。整库镜像还会产生三个实际问题：

1. 许可证和署名容易在复制时丢失；
2. 上游每日更新，本仓库会迅速过期；
3. 大量 Skill 依赖 WorkBuddy 宿主、登录态、专用 MCP 或外部服务，在 Codex 中不一定可用。

因此导航采用“固定目录快照 + 运行时按需拉取原目录”的方式。安装器保留上游目录中
原有的 `LICENSE`、`NOTICE` 和元数据，不执行其中的脚本。

## 对外表述

可以称为“WorkBuddy 公开市场 Skills 导航”或“面向 Codex 的按需安装导航”。不要称为
WorkBuddy 官方发行版、官方合作项目或已获得全部 Skill 的再分发授权。
