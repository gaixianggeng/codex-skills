---
name: workbuddy-skills-navigator
description: 浏览并按需安装 WorkBuddy 公开市场 Skill。用户想查看 WorkBuddy Skill 清单、搜索某项能力，或按“全部 / 一个或多个分类 / 一个或多个 Skill”安装到 Codex 时使用；仅浏览时不得安装，安装前必须展示计划并获得确认。
---

# WorkBuddy Skills 导航

把本 `SKILL.md` 所在目录记为 `SKILL_DIR`。统一通过
`python3 "$SKILL_DIR/scripts/workbuddy_skills.py"` 查询和安装，不手写下载地址。

## 数据范围

当前目录固定到 2026-07-27 的公开市场快照，共 295 个顶层 Skill：

| 分类 ID | 分类 | 数量 |
| --- | --- | ---: |
| `ai-agent` | AI / Agent 工具 | 159 |
| `cloud-deploy` | 云 / 存储 / 部署 | 4 |
| `content-marketing` | 内容 / 营销 / 媒体 | 5 |
| `development` | 开发 / 工程 | 2 |
| `research-knowledge` | 搜索 / 研究 / 知识 | 15 |
| `finance-data` | 数据 / 金融 / 股票 | 6 |
| `docs-office` | 文档 / 办公 / 协作 | 44 |
| `tencent-wechat` | 腾讯 / 微信 / 企微 | 47 |
| `design-ui-map` | 设计 / UI / 地图 | 12 |
| `other` | 其他 | 1 |

这是第三方学习归档的导航，不代表 WorkBuddy 或腾讯官方发行。各 Skill 的版权、
许可证、账号和服务依赖互不相同。用户询问来源或许可时，读取
`references/source-notice.md`。

## 工作流

### 1. 先确认用户要找什么

- 未指定范围：只列分类，不安装。
- 指定分类：列出该分类的 Skill，再让用户选择整个分类或具体 Skill。
- 指定能力但不知道名称：先搜索目录。
- 明确要求全部安装：可以进入全量预览，但必须提醒这是 295 个 Skill。

```bash
python3 "$SKILL_DIR/scripts/workbuddy_skills.py" --list-categories
python3 "$SKILL_DIR/scripts/workbuddy_skills.py" --list --category content-marketing
python3 "$SKILL_DIR/scripts/workbuddy_skills.py" --search humanizer
```

分类参数可重复，用于组合多个分类；Skill 参数也可重复。

### 2. 先预览安装计划

安装前必须运行 `--dry-run`。向用户展示：

- 选择方式和 Skill 数量；
- 安装目标目录；
- 已存在的同名目录；
- 需要 API Key、OAuth、登录或 MCP 的条目数量；
- 固定的上游来源与提交版本。

```bash
# 单项
python3 "$SKILL_DIR/scripts/workbuddy_skills.py" \
  --skill humanizer \
  --dry-run

# 多分类
python3 "$SKILL_DIR/scripts/workbuddy_skills.py" \
  --category content-marketing \
  --category design-ui-map \
  --dry-run

# 全部
python3 "$SKILL_DIR/scripts/workbuddy_skills.py" \
  --all \
  --dry-run
```

### 3. 获得明确确认

只有用户确认刚才展示的计划后，才执行写入。

- 单项或分类安装加 `--yes`。
- 全量安装必须同时加 `--yes --confirm-all`。
- 用户只说“看看”“有哪些”“推荐几个”时，不得把它理解为安装授权。
- 用户没有明确选择“全部”时，不得自动升级为全量安装。

### 4. 执行安装

```bash
# 安装单项
python3 "$SKILL_DIR/scripts/workbuddy_skills.py" \
  --skill humanizer \
  --yes

# 安装一个或多个分类
python3 "$SKILL_DIR/scripts/workbuddy_skills.py" \
  --category content-marketing \
  --category development \
  --yes

# 安装全部 295 个 Skill
python3 "$SKILL_DIR/scripts/workbuddy_skills.py" \
  --all \
  --yes \
  --confirm-all
```

默认目标是 `$CODEX_HOME/skills`；未设置 `CODEX_HOME` 时使用
`~/.codex/skills`。脚本不会覆盖已有同名目录。只有用户明确接受“跳过已安装项”
时才加 `--skip-existing`。

### 5. 安装后反馈

报告成功安装、跳过和失败的数量，并提醒用户：

1. 新 Skill 从下一轮对话开始可用；
2. “安装成功”不等于外部服务已经可用；
3. 涉及 API Key、OAuth、登录、MCP 或专用宿主的 Skill 还需单独配置；
4. 第一次使用前应检查该 Skill 的 `SKILL.md`、脚本和许可证。

## 安全边界

- 安装器只下载和复制文件，不执行下载到的任何脚本。
- 不读取或传输本机 Cookie、Token、WorkBuddy 登录态或个人资料。
- 不覆盖已有 Skill；需要更新时先做差异检查和备份。
- 不把“来源公开”解释为“允许任意再分发或商用”。
- 对支付、下单、发消息、发布、删除等外部动作，安装不构成执行授权。
- 全量安装会增加磁盘占用、触发冲突并扩大 Agent 可见能力面；优先推荐按需安装。
