# 推到 GitHub：一步一步来

> 目标：把 ai-group 变成面试官**能点开看**的仓库。  
> 前置：Git 已装好（`C:\Users\yyy\Git`），ai-group 已 commit（96 个文件，0.52 MB）。

---

## 第 0 步：先想清楚推哪个

| 仓库            | 推吗         | 为什么                    |
| ------------- | ---------- | ---------------------- |
| **ai-group**  | ✅ **必须推**  | 你最值钱的项目，简历第一个项目        |
| **agent-lab** | ✅ 推        | 展示学习过程，commit 历史本身就是证据 |
| campus-market | ❌ 已舍弃      | 你自己说的                  |
| AI工作群-Tauri版  | ❌ **千万别推** | 里面有你的真实聊天记录和配置         |

> ⚠️ **推之前必须确认**：`.gitignore` 已排除 `data/`（聊天记录）、`.env`（密钥）、`dist/`、`build/`、`ai-group-window-profile/`。我已验证这四项**都是 0 个文件被跟踪**。

---

## 第 1 步：注册 / 登录 GitHub

1. 打开 <https://github.com/signup>
2. 用户名建议：**用真名拼音**（如 `huangyuming`）——面试官看到会觉得专业
   - ❌ 别用 `abc123`、`xiaoming666` 这类
   - ✅ 或者和你 gitee 那个 `huang-yuming1234` 保持一致的风格
3. 记下你的用户名，等下要用

> **网络提示**：本机实测 `github.com` 网页直连超时，但 **git 协议能通**（我已用 `git ls-remote` 验证过）。所以：
>
> - 网页注册如果打不开 → 用手机热点 / 或先注册再想办法
> - `git push` 本身没问题

---

## 第 2 步：在 GitHub 上建空仓库

1. 右上角 `+` → **New repository**
2. 填写：
   - **Repository name**：`ai-group`
   - **Description**：`多厂商大模型群聊协作系统：组长派发、组员响应、记录员汇总，Web 实时流式展示`
   - 选 **Public**（公开，面试官才看得到）
   - ⚠️ **不要**勾 "Add a README file"、**不要**勾 .gitignore、**不要**选 license  
     （因为本地已经有内容了，勾了会冲突）
3. 点 **Create repository**
4. 建完后页面会显示一串命令，**先别管**，按下面做

---

## 第 3 步：本地关联并推送

打开 PowerShell，**逐行**执行（把 `你的用户名` 换成实际的）：

```powershell
# 让 git 命令可用（新开终端会自动有，这里手动加一次）
$env:Path = "C:\Users\yyy\Git\cmd;$env:Path"

cd C:\Users\yyy\Documents\deepseek-harness\default-workspace\ai-group

# 关联远程仓库
git remote add origin https://github.com/你的用户名/ai-group.git

# 推送
git push -u origin main
```

**会弹出登录窗口**：

- 选 **Sign in with your browser**（浏览器登录最省事）
- 或者用 **Personal Access Token**（见下面"常见问题"）

推送成功后，打开 `https://github.com/你的用户名/ai-group` 应该能看到代码。

---

## 第 4 步：同样的步骤推 agent-lab

```powershell
cd C:\Users\yyy\Documents\deepseek-harness\default-workspace\agent-lab
git init
git branch -M main
git add -A
git commit -m "init: Agent 手搓训练场（讲义 + 作业骨架 + 验收脚本）"
```

然后在 GitHub 建一个叫 `agent-lab` 的空仓库，再：

```powershell
git remote add origin https://github.com/你的用户名/agent-lab.git
git push -u origin main
```

---

## 第 5 步：回来告诉我用户名

推完之后告诉我你的 GitHub 用户名，我立刻：

1. 把简历里的 `github.com/YOUR_GITHUB_ID` 换成真实链接
2. 重新生成简历 DOCX

---

## 常见问题

### Q: push 时提示要密码，输了账号密码却说不对？

GitHub 从 2021 年起**不再接受账号密码**，必须用 **Personal Access Token**：

1. 打开 <https://github.com/settings/tokens>
2. **Generate new token** → **classic**
3. Note 随便写（如 `local-git`），Expiration 选 90 天
4. 勾选 **repo**（整个 repo 大项）
5. Generate token → **复制那串 `ghp_xxxxx`**（只显示一次！）
6. push 时密码框粘贴这串 token

### Q: 提示 `remote origin already exists`？

```powershell
git remote set-url origin https://github.com/你的用户名/ai-group.git
```

### Q: 提示 `failed to push some refs` / `rejected`？

说明远程仓库不是空的（你可能勾了 README）。解决：

```powershell
git pull origin main --allow-unrelated-histories
git push -u origin main
```

### Q: 想确认推上去的没有敏感文件？

```powershell
git ls-files | Select-String -Pattern "env|data/|credential"
```

应该只看到 `.env.example`（那是示例文件，不含真实密钥）。

---

## 推完之后，你的简历就活了

面试官点开 `github.com/你的用户名/ai-group` 会看到：

- **96 个文件**，不是"一键生成"的骨架
- **group/engine.py 1539 行**的群聊内核——这玩意儿 AI 一键生成不了
- **docs/evidence/ 50+ 份证据**——这是你最稀缺的东西
- **commit 历史**——证明是持续开发的，不是某天批量上传

> 对比：你图 1 里被批评的那个人，被批的是"全是 gpt 一键生成的项目，自己有没有深入了解过每个组件具体逻辑都是问题"。  
> **有证据留档的仓库，恰恰是对这句话最有力的反驳。**
