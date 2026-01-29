# DeepWiki Agent

自动监控 GitHub 星标仓库，通过 DeepWiki MCP 获取文档，使用 Claude AI 精炼为高质量中文文档。

## 功能特性

- ⭐ **自动监控**：每 1 分钟检查新的 GitHub star 仓库
- 📚 **智能获取**：从 DeepWiki MCP 自动获取仓库文档
- 🤖 **AI 精炼**：使用 Claude 两阶段精炼（草稿 → 完善）
- 🎯 **智能标题**：自动生成简洁的中文标题
- 💾 **本地保存**：最终文档保存到本地，包含元数据
- 📢 **飞书通知**：处理完成后自动发送飞书通知
- 🔄 **状态追踪**：自动记录已处理仓库，避免重复

## 快速开始

### 1. 环境准备

```bash
# 切换到 deepwiki 用户
su - deepwiki

# 配置 Claude
claude login

# 安装依赖
pip install httpx python-dotenv
```

### 2. 配置环境变量

编辑 `~/Projects/autodoc_agent/.env`：
```bash
GITHUB_TOKEN=your_github_token
FEISHU_WEBHOOK_URL=https://open.feishu.cn/open-apis/bot/v2/hook/YOUR_WEBHOOK_URL
```

#### 获取 GitHub Token

1. 访问：https://github.com/settings/tokens
2. 点击 **Generate new token (classic)**
3. 勾选权限：
   - `read:org`
   - `read:user`
   - `read:public_key`
4. 生成并复制 token

#### 获取飞书 Webhook URL

1. 打开飞书群组
2. 点击 **群组设置** → **群机器人** → **添加机器人**
3. 选择 **自定义机器人**
4. 复制 Webhook URL
5. 添加到 `.env` 文件中

### 3. 启动服务

```bash
# 创建 screen 会话
screen -S deepwiki_agent

# 在 screen 中运行
cd ~/Projects/autodoc_agent
python run_agent.py

# 分离 screen：Ctrl+A 然后 D
```

### 4. 查看结果

```bash
# 查看生成的文档
ls -lh ~/Projects/autodoc_agent/final_docs/

# 重新连接 screen
screen -r deepwiki_agent
```

## 配置

### 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `GITHUB_TOKEN` | GitHub API Token（必需） | - |
| `POLL_INTERVAL` | 轮询间隔（秒） | 60（1 分钟） |

### 自定义轮询间隔

```bash
# 每 5 分钟
POLL_INTERVAL=300 python run_agent.py

# 每 30 分钟
POLL_INTERVAL=1800 python run_agent.py
```

## 工作流程

1. **监控 GitHub Stars**：获取最近星标的仓库
2. **准备工作区**：
   - 从 DeepWiki MCP 获取 overview.md
   - 复制其他文档到 docs/ 目录
   - 获取仓库 README
3. **Claude AI 精炼**（两阶段）：
   - 阶段一：根据 overview.md + README.md 生成草稿 (draft.md)
   - 阶段二：查看 docs/ 其他文档，完善生成最终文档 (final.md)
4. **保存结果**：将 final.md 保存到 final_docs/ 目录

## 输出结构

```
deepwiki_agent/
├── CLAUDE.md           # Claude AI 提示词模板
├── README.md           # 本文件
├── run_agent.py        # 主流程脚本
├── github_stars.py     # GitHub 监控模块
├── deepwiki_mcp.py     # DeepWiki MCP 客户端
├── feishu_notifier.py  # 飞书通知模块
└── requirements.txt    # Python 依赖
```

## 飞书通知格式

### 成功通知
```
✅ 文档生成成功

仓库: owner/repo
标题: AI编排框架
描述: 项目描述...
文件路径: /path/to/file.md
```

### 失败通知
```
❌ 文档生成失败

仓库: owner/repo
错误信息: 错误详情...
```

## 故障排查

### 重新处理某个仓库

编辑 `~/Projects/autodoc_agent/state.json`，删除对应的 repo_id 记录，然后重启。

### 查看日志

连接到 screen 查看实时输出：`screen -r deepwiki_agent`

## 许可证

MIT
