# Codex Skills

## 目标

集中维护个人常用的 Codex Skills。每个 Skill 都保持独立、可验证、可单独安装，避免已安装副本散落后难以同步。

## 方案

```text
codex-skills/
├── AGENTS.md
├── README.md
└── skills/
    └── <skill-name>/
        ├── SKILL.md
        └── agents/
            └── openai.yaml
```

仓库根目录只负责管理合集；每个 `skills/<skill-name>/` 才是一个完整 Skill。

## 已收录 Skills

| Skill | 用途 |
| --- | --- |
| [`delegate-to-chatgpt-pro`](skills/delegate-to-chatgpt-pro/) | 通过 Codex 内置浏览器委派复杂工程任务给 ChatGPT Pro，并由 Codex 独立审查与验收 |
| [`init-project-workspace`](skills/init-project-workspace/) | 从当前会话提炼确认方案，初始化项目工作区并建立 GitHub 仓库 |
| [`workbuddy-skills-navigator`](skills/workbuddy-skills-navigator/) | 浏览 295 个 WorkBuddy 公开市场 Skill，按全部、分类或单项预览并安装 |

## 使用

克隆合集：

```bash
git clone git@github.com:gaixianggeng/codex-skills.git
cd codex-skills
```

安装单个 Skill：

```bash
cp -R skills/init-project-workspace ~/.codex/skills/
```

如果目标目录已经存在，先比较差异并备份，不要直接覆盖正在使用的版本。

### 按需安装 WorkBuddy 公开市场 Skills

> 来源与使用限制：本导航收录的第三方 Skill 均来源于 WorkBuddy 公开市场，
> 并通过公开市场归档按需拉取。仅供个人研究与学习，不支持商用；本项目不提供
> 任何第三方内容的商用授权。各 Skill 的版权和具体许可归原作者或相关权利人所有。

先安装导航 Skill：

```bash
cp -R skills/workbuddy-skills-navigator ~/.codex/skills/
```

然后在新对话中使用：

```text
使用 $workbuddy-skills-navigator 查看分类
使用 $workbuddy-skills-navigator 搜索“humanizer”
使用 $workbuddy-skills-navigator 安装“内容 / 营销 / 媒体”分类
```

导航提供 295 个顶层 Skill 的固定目录快照，支持全量、多个分类或多个单项组合。
实际写入前会先展示安装计划，并且不会覆盖已有同名目录。

## 新增或更新 Skill

1. 在 `skills/<skill-name>/` 中创建或修改 Skill。
2. 使用 Codex 的 `skill-creator` 维护 `SKILL.md` 和 `agents/openai.yaml`。
3. 运行校验：

   ```bash
   python3 ~/.codex/skills/.system/skill-creator/scripts/quick_validate.py skills/<skill-name>
   ```

4. 检查公开仓库中不包含令牌、密码、私有路径、内部资料或其他敏感信息。
5. 提交并推送，再按需同步到本机安装目录。

## 风险与优化

- 仓库源码和 `~/.codex/skills/` 下的已安装副本可能产生版本漂移；以本仓库内容为源码基准。
- WorkBuddy 导航中的第三方 Skill 不在本仓库二次打包；源码按固定提交从公开市场归档按需下载，仅供个人研究与学习，不支持商用，各项许可证和外部服务依赖需分别检查。
- 全量安装当前会写入 295 个 Skill，其中不少依赖 API Key、OAuth、登录或 MCP；优先按分类或单项安装。
- 暂不增加复杂发布脚本或包管理机制。Skills 数量增多、手工同步成为真实问题后，再补充安装与同步工具。
