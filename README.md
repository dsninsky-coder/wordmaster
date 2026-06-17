# 单词大师 WordMaster

> 一个功能完整的单词学习与记忆 Web 应用，基于 Flask 构建，支持多用户、多种答题模式、金币激励体系与管理员管控。

**版本：v0.1.0**

---

## 目录

- [功能概览](#功能概览)
- [技术架构](#技术架构)
- [快速开始](#快速开始)
- [功能详解](#功能详解)
- [项目结构](#项目结构)
- [配置说明](#配置说明)
- [API 路由一览](#api-路由一览)
- [数据文件说明](#数据文件说明)
- [版本历史](#版本历史)
- [许可证](#许可证)

---

## 功能概览

### 核心学习功能
| 功能 | 说明 |
|------|------|
| 多词单管理 | 创建、导入、管理多个单词列表 |
| 双向答题模式 | 英→中（看英文写中文）、中→英（看中文写英文） |
| 新背单词 | 逐题学习新单词，即时判断对错 |
| 复习模式 | 复习已学单词，间隔重复巩固记忆 |
| AI 辅助判题 | 英→中模式支持 AI 语义判定（可配置 DeepSeek/OpenAI 等） |
| 关键词匹配 | 本地关键词优先匹配，减少 API 调用 |
| 词单成绩标签 | 已学词单显示通过率，一目了然 |
| 答错自动推进 | 答错后自动跳到下一题，不卡进度 |

### 激励体系
| 功能 | 说明 |
|------|------|
| 金币系统 | 完成学习任务获得金币奖励 |
| 每日打卡 | 登录签到 +1，新背通过 +3，复习通过 +5 |
| 免错券 | 使用免错券将答错题目计为正确 |
| 金币商城 | 用金币兑换免错券等商品 |
| 许愿池 | 花金币许愿，社区助力，管理员点亮 |

### 音效与交互
| 功能 | 说明 |
|------|------|
| 答题音效 | Web Audio API 合成音效（零依赖，离线可用） |
| TTS 发音 | 英→中模式支持浏览器离线 + 有道在线双引擎发音 |
| 预览弹窗 | 点击单词即可预览释义，无需跳转 |
| 冷却倒计时 | 未通过词单需等待冷却时间后重新挑战 |

### 管理员功能
| 功能 | 说明 |
|------|------|
| 超管面板 | 用户管控、共享 API、冷却配置 |
| 用户管控 | 管理员可控制用户的复习数量、答题模式等设置 |
| 三档复习管控 | 不强制 / 必须全部复习 / 一次即可 |
| 金币发放 | 管理员直接向用户发放或扣除金币（需密码验证） |
| 商品管理 | 上架/下架商城商品，处理订单发货 |
| 许愿池管理 | 点亮/驳回/标记实现用户愿望 |
| 密码重置 | 管理员可重置任意用户密码 |
| 查看用户统计 | 管理员可查看任意用户的学习统计数据 |

---

## 技术架构

| 层级 | 技术 |
|------|------|
| 后端 | Python 3.12+ / Flask 2.3 |
| 数据存储 | JSON 文件（无数据库依赖） |
| 密码安全 | Werkzeug `generate_password_hash` / `check_password_hash` |
| 前端 | Jinja2 模板 + 原生 CSS + 原生 JavaScript |
| 音效 | Web Audio API（合成音效，零依赖） |
| TTS | Web Speech API（离线） + 有道词典 API（在线） |
| AI 判题 | OpenAI 兼容 API（支持 DeepSeek / OpenAI / 自部署模型） |

---

## 快速开始

### 环境要求

- Python 3.8+
- pip

### 安装步骤

```bash
# 1. 克隆仓库
git clone https://github.com/dsninsky-coder/wordmaster.git
cd wordmaster

# 2. 安装依赖
pip install -r requirements.txt

# 3. 启动应用
python app.py
```

应用将在 `http://127.0.0.1:5000` 启动。

### 默认账号

| 角色 | 用户名 | 密码 |
|------|--------|------|
| 管理员 | admin | admin |

> **首次登录后请立即修改管理员密码！**

---

## 功能详解

### 1. 新背单词

用户从词单列表中选择词单进行学习。系统逐题展示单词，用户输入答案后即时判定对错。

- **英→中模式**：展示英文单词，用户输入中文释义。支持 AI 语义判定和关键词匹配。
- **中→英模式**：展示中文释义，用户输入英文单词。采用精确匹配。
- 答对自动播放上升音效，答错播放下降音效。
- 答错可使用**免错券**将本题计为正确。
- 词单完成后显示通过率和成绩标签。

### 2. 复习模式

复习已学单词，间隔重复巩固记忆。

- **三档复习模式**（管理员可配置）：
  - `none`：不强制复习
  - `all`：必须全部复习完才能学新词
  - `once`：复习通过一次即可
- 答错的单词 `next_review` 设为当天，确保立即回到待复习池。
- 未通过的词单有冷却时间，需等待后重新挑战。

### 3. 金币与打卡

每日签到和学习任务奖励金币：

| 行为 | 奖励 | 说明 |
|------|------|------|
| 登录签到 | +1 | 金币页面手动领取，每日一次 |
| 新背通过 | +3 | 每个词单每日首次通过 |
| 复习通过 | +5 | 每日首次复习通过 |

金币流水明细记录所有收支，包含来源和备注。

### 4. 免错券

- 答题答错后出现"使用免错券"按钮
- 使用后本题计为正确 +1 并推进，不计错误记录
- 免错券可从商城购买（2 金币/张）

### 5. 金币商城

- 管理员可上架文字商品
- 订单流程：下单 → 发货 → 确认收货
- 余额不足时商品灰显并禁用购买
- 购买弹窗内显示错误提示

### 6. 许愿池

- 用户花金币许愿（公开/私密）
- 其他用户可助力（花金币支持）
- 管理员可点亮愿望（发放）或驳回（退还全部金币）
- 私密愿望仅本人和管理员可见

### 7. 管理员面板

管理员（`/admin`）拥有完整的系统管控能力：

- **共享 API 配置**：设置全局 AI 判题 API Key 和模型
- **用户管控**：控制用户的复习数量、答题模式、AI 模型等
- **冷却配置**：设置未通过词单的重答冷却时间
- **金币发放**：选择用户、填写数量和留言，密码验证后发放
- **商品管理**：上架/下架/删除商品，发货处理
- **许愿池管理**：审批/驳回/点亮愿望
- **密码重置**：重置任意用户密码
- **用户统计**：查看任意用户的学习数据

### 8. 统计页面

- 英→中 / 中→英 分模式统计卡片
- 支持筛选特定词单查看
- 管理员可通过下拉菜单切换查看任意用户

### 9. 设置页面

- 修改密码（当前密码 → 新密码 → 确认）
- AI 模型配置（个人优先，管理员可覆盖）
- 复习数量设置
- 被管理员管控的设置项显示锁定标识

---

## 项目结构

```
wordmaster/
├── app.py                  # Flask 主应用（路由、中间件、业务逻辑）
├── data_manager.py         # 数据管理层（JSON 文件 CRUD）
├── requirements.txt        # Python 依赖
├── README.md               # 项目文档
├── .gitignore              # Git 忽略规则
├── data/                   # 数据目录（自动创建）
│   ├── config.json         # 全局配置
│   ├── words.json          # 词单数据
│   ├── user.json           # 用户数据（密码哈希）  ← 不上传
│   ├── admin_config.json   # 管理员配置              ← 不上传
│   ├── coins.json          # 金币数据                ← 不上传
│   ├── shop.json           # 商城数据                ← 不上传
│   ├── wishes.json         # 许愿池数据              ← 不上传
│   └── history/            # 用户历史记录             ← 不上传
│       └── {username}.json
├── templates/              # Jinja2 模板
│   ├── base.html           # 基础布局（导航栏）
│   ├── login.html          # 登录页
│   ├── register.html       # 注册页
│   ├── study.html          # 词单列表页
│   ├── check.html          # 答题页（学习+复习共用）
│   ├── review.html         # 复习入口页
│   ├── learn.html          # 学习浏览页
│   ├── import.html         # 导入词单页
│   ├── settings.html       # 设置页
│   ├── stats.html          # 统计页
│   ├── admin.html          # 管理员面板
│   ├── coins.html          # 金币/打卡页
│   ├── shop.html           # 商城页
│   └── wishes.html         # 许愿池页
└── static/                 # 静态资源
    ├── css/
    │   └── style.css       # 全局样式
    └── js/
        └── check.js        # 答题页辅助脚本
```

---

## 配置说明

### 全局配置（`data/config.json`）

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `review_count` | int | 20 | 每次复习题目数 |
| `chatgpt_api_key` | string | "" | AI 判题 API Key |
| `chatgpt_base_url` | string | "https://api.openai.com/v1" | AI API 基础 URL |
| `ai_model` | string | "deepseek-chat" | AI 模型名称 |
| `require_review_before_study` | bool | false | 是否必须先复习再学新词（旧字段，兼容保留） |
| `require_both_modes` | bool | false | 是否需要双模式都通过 |
| `review_mode` | string | "none" | 复习模式：none/all/once |

### 管理员配置（`data/admin_config.json`）

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `shared_api_key` | string | "" | 共享 API Key |
| `shared_base_url` | string | "https://api.openai.com/v1" | 共享 API URL |
| `shared_ai_model` | string | "" | 共享 AI 模型（覆盖用户个人设置） |
| `allowed_api_users` | list | [] | 允许使用共享 API 的用户列表 |
| `retry_cooldown_seconds` | int | 60 | 未通过词单重答冷却时间（秒） |
| `controlled_users` | dict | {} | 被管控用户及其配置 |

### 配置优先级

```
管理员共享配置 > 用户个人设置 > 全局默认值
```

- AI 模型：`shared_ai_model` > 用户设置 `ai_model` > 全局 `ai_model`
- API Key：`shared_api_key`（仅在 `allowed_api_users` 中的用户可用）> 用户个人 key
- 复习管控：管理员管控 > 用户个人设置（被管控时显示锁定标识）

---

## API 路由一览

### 认证

| 方法 | 路由 | 说明 |
|------|------|------|
| GET/POST | `/login` | 登录 |
| GET/POST | `/register` | 注册 |
| GET | `/logout` | 退出登录 |

### 学习

| 方法 | 路由 | 说明 |
|------|------|------|
| GET | `/study` | 词单列表页 |
| POST | `/study/preview` | 预览词单 |
| POST | `/study/start` | 开始学习词单 |
| POST | `/study/next` | 获取下一题 |
| POST | `/study/submit` | 提交答案 |
| POST | `/study/advance` | 推进到下一题 |
| POST | `/study/restart` | 重新挑战词单 |
| POST | `/study/ticket_override` | 免错券使用 |

### 复习

| 方法 | 路由 | 说明 |
|------|------|------|
| GET | `/review` | 复习入口页 |
| POST | `/review/start` | 开始复习 |
| POST | `/review/next` | 获取下一题 |
| POST | `/review/submit` | 提交答案 |
| POST | `/review/advance` | 推进到下一题 |
| POST | `/review/restart` | 重新复习 |
| POST | `/review/ticket_override` | 免错券使用 |

### 导入

| 方法 | 路由 | 说明 |
|------|------|------|
| GET | `/import` | 导入页面 |
| POST | `/import/upload` | 上传 CSV 文件 |
| POST | `/import/confirm` | 确认导入 |

### 设置与统计

| 方法 | 路由 | 说明 |
|------|------|------|
| GET/POST | `/settings` | 用户设置页 |
| GET | `/stats` | 统计页面（支持 `?user=xxx` 查看其他用户） |
| GET | `/learn` | 学习浏览页 |

### 金币与商城

| 方法 | 路由 | 说明 |
|------|------|------|
| GET | `/coins` | 金币页面 |
| POST | `/coins/checkin_login` | 登录签到领取 |
| GET | `/coins/balance` | 查询余额 |
| POST | `/coins/use_ticket` | 使用免错券 |
| GET | `/shop` | 商城页面 |
| POST | `/shop/buy` | 购买商品 |
| POST | `/shop/confirm_receipt` | 确认收货 |

### 许愿池

| 方法 | 路由 | 说明 |
|------|------|------|
| GET | `/wishes` | 许愿池页面 |
| POST | `/wishes/create` | 创建愿望 |
| POST | `/wishes/pledge` | 助力愿望 |
| POST | `/wishes/fulfill` | 用户标记已实现 |

### 管理员

| 方法 | 路由 | 说明 |
|------|------|------|
| GET/POST | `/admin` | 管理员面板 |
| POST | `/admin/user_control_data` | 获取/设置用户管控数据 |
| POST | `/admin/grant_coins` | 发放金币（需密码验证） |
| POST | `/admin/shop/products` | 商品列表 |
| POST | `/admin/shop/add_product` | 添加商品 |
| POST | `/admin/shop/toggle_product` | 上下架商品 |
| POST | `/admin/shop/delete_product` | 删除商品 |
| POST | `/admin/shop/ship` | 发货 |
| POST | `/admin/wish_approve` | 点亮愿望 |
| POST | `/admin/wish_reject` | 驳回愿望 |
| POST | `/admin/wish_fulfill` | 标记实现 |
| POST | `/admin/wishes_data` | 许愿池数据 |

---

## 数据文件说明

> **注意**：用户数据文件（含密码哈希、个人记录）未包含在仓库中，首次运行时自动创建。

| 文件 | 说明 | 初始内容 |
|------|------|----------|
| `config.json` | 全局配置 | 默认复习数量、空 API Key |
| `words.json` | 示例词单 | list1（apple/boy/cat）、list2（dog/book） |
| `user.json` | 用户数据 | admin 管理员账号（密码哈希） |
| `admin_config.json` | 管理员配置 | 空 API、60秒冷却 |
| `coins.json` | 金币数据 | 空 |
| `shop.json` | 商城数据 | 空 |
| `wishes.json` | 许愿池数据 | 空 |
| `history/*.json` | 用户历史 | 按用户名分文件 |

### 词单数据格式

```json
{
  "list_name": [
    {"word": "apple", "meaning": "苹果"},
    {"word": "book", "meaning": "书"}
  ]
}
```

### 导入词单格式（CSV）

```csv
word,meaning
apple,苹果
book,书
hello,你好
```

---

## 版本历史

### v0.1.0 (2026-06-17)

首个公开版本，包含以下功能模块：

- **核心学习**：多词单管理、英→中/中→英双模式答题、AI 辅助判题
- **复习系统**：间隔重复复习、三档复习管控、冷却倒计时
- **激励体系**：金币系统、每日打卡、免错券、金币商城、许愿池
- **音效交互**：Web Audio 合成音效、TTS 双引擎发音
- **管理后台**：用户管控、共享 API、金币发放、商品管理、许愿池审批、密码重置
- **统计系统**：分模式统计、用户切换、词单成绩标签
- **安全机制**：Werkzeug 密码哈希、管理员操作密码验证

---

## 许可证

MIT License

Copyright (c) 2026 dsninsky-coder

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
