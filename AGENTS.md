# 仓库协作规则

## 目标

本仓库用于维护可公开发布、可单独安装的个人 Codex Skills。

## 目录约定

- 每个 Skill 放在 `skills/<skill-name>/`。
- 每个 Skill 必须包含合法的 `SKILL.md`；按需包含 `agents/`、`scripts/`、`references/` 和 `assets/`。
- 仓库级说明放在根目录，不在单个 Skill 内增加无必要的 README、变更日志或重复文档。

## 修改要求

- 创建或更新 Skill 时使用 `skill-creator`，完整读取其规则后再修改。
- 保持 Skill 简洁，优先交付最小可运行闭环，不引入未被真实需求验证的脚本或依赖。
- 核心流程和关键设计使用中文说明；命令与配置必须完整、可执行。
- 修改现有 Skill 前先检查当前实现和 Git 状态，保留用户已有改动。
- 更新 `SKILL.md` 后同步检查 `agents/openai.yaml`，并运行官方 `quick_validate.py`。

## 公开发布边界

- 不提交真实密钥、令牌、密码、证书、生产连接串、私有资料或无关个人信息。
- 发布前检查暂存范围和敏感信息；只提交属于目标 Skill 的文件。
- 不把 `~/.codex/skills/` 整体复制进仓库，只收录明确选择的个人 Skills。
