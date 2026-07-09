# Reports 项目目录规约

本仓库用于输出**公共报告**,所有产物面向公开发布。任何 AI agent 在创建、移动、重命名、提交文件之前,**必须先读完本文件并遵守规约**。有疑问先停下来问,不要动手。

**项目仓库:** `https://github.com/Xyz9Selu/reports`

---

## 一、核心原则

1. **一个主题 = 一个目录**。一份报告及其全部素材集中放在以主题命名的目录里,绝不散落到仓库根目录。
2. **目录名稳定,文件名带日期**。同一主题多次更新沿用同一目录,版本通过文件名中的日期区分。
3. **素材与报告同级管理**。图片、数据、脚本只放在所属主题目录下的 `assets/`、`data/`、`scripts/` 子目录。
4. **根目录最小化**。根目录只允许 `README.md`、`.gitignore` 等配置文件。
5. **永不覆盖历史版本**。同名同日期的文件视为冲突,需用户确认;旧版报告只增不删。
6. **英文优先**。主题目录、报告文件统一英文 kebab-case(`小写+连字符`),便于 URL、跨平台与跨语言检索。**严禁中英混用。**

---

## 二、目录结构

```
reports/
├── README.md                          ← 本文件
├── .gitignore
│
├── cpo-optical/                       ← 主题目录(英文 kebab-case)
│   ├── cpo-optical-2026-07-09.md      ← 报告正文
│   ├── cpo-optical-2026-07-21.md      ← 同主题更新版(保留旧版)
│   ├── assets/                        ← 图片
│   │   ├── chart_valuation.png
│   │   └── chart_radar.png
│   ├── data/                          ← 原始数据(可选)
│   └── scripts/                       ← 生成图表的脚本(可选)
│
└── _template/                         ← 新报告模板(可选)
    └── TEMPLATE.md
```

---

## 三、命名规范

### 3.1 主题目录名

- **英文 kebab-case**:`小写字母 + 数字 + 连字符(-)`。
- 2–24 个字符(英文转写的中文名可放宽)。
- 不带日期,不带空格,不带 `/ \ : * ? " < > |` 等特殊字符,不以 `-` 开头或结尾。
- 同一中文主题只能有一个固定英文名,目录里只放英文,中文别名若有需求自行维护映射表。

### 3.2 报告文件名

格式:**`<主题目录名>-<YYYY-MM-DD>.md`**

- 日期 ISO 8601 (`YYYY-MM-DD`),便于排序。
- 同主题更新 → 新日期文件,**保留旧版**。
- 不要加 `v2`、`final`、`最新版`、`草稿` 后缀——日期即版本号。
- 文件名同样使用英文 kebab-case。

### 3.3 素材文件名

- **英文小写 + 下划线 + 数字**(`snake_case`),与目录的 kebab-case 区分。
- 同名含义相同(同一图表跨版本可复用),不重复包含主题名(目录已表达)。

| ❌ 反例 | ✅ 正例 |
|---|---|
| `CPO光互联` | `cpo-optical` |
| `CPO 光互联` | `cpo-optical` |
| `CPO_Optical` | `cpo-optical` |
| `CPO光互联-2026` | `cpo-optical` |
| `CPO光互联.md` | `cpo-optical-2026-07-09.md` |
| `估值图.png` | `chart_valuation.png` |

---

## 四、Markdown 内容规范

1. 标题层级:`#` 写报告标题,正文从 `##` 开始。
2. 图片用相对路径:`![说明](assets/chart_xxx.png)`,**禁止外链**。
3. 引用的图片必须在 `assets/` 存在;`assets/` 里的图片必须在正文被引用(否则删除)。
4. 报告末尾注明数据截止与生成时间:
   ```
   ---
   数据截至:2026-07-08
   生成时间:2026-07-09
   ```
5. 不嵌 base64 大图,不贴爬虫原始输出(原始数据放 `data/`)。

---

## 五、AI Agent 自查清单

任何写文件操作**之前**逐项自查:

- [ ] 文件归属哪个主题?目录是否存在?
- [ ] 文件名符合 §三 规范?
- [ ] 图片/数据/脚本放在对应子目录?
- [ ] 不会让根目录出现新文件?
- [ ] 不会**覆盖**已有文件?(同日期同名 = 冲突,先确认)
- [ ] 不会**删除**已有文件?(默认禁止)
- [ ] 用 `git mv` 保留历史?

**拿不准就问,不要直接动手。**

---

## 六、禁止事项

- ❌ 报告、图片、数据放在仓库根目录。
- ❌ 多主题混在同一目录。
- ❌ 覆盖或删除历史报告。
- ❌ 用空格、`#`、`?`、`(`、`)` 等特殊字符命名文件。
- ❌ Markdown 用外链图片代替本地 `assets/`。
- ❌ 同一主题存在多个并列目录(中文/英文并存也算)。
- ❌ **目录或文件名中英混用**(如 `cpo-optical/CPO光互联-2026-07-09.md`)。
- ❌ 提交临时文件、IDE 配置、爬虫日志(用 `.gitignore` 忽略)。
- ❌ 把单个文件当作"主题"(主题必须是目录)。

---

## 七、迁移历史散落 / 中文命名文件

```bash
# 1. 改名目录(保留历史)
git mv "CPO光互联" cpo-optical

# 2. 改名文件
git mv "cpo-optical/CPO光互联-2026-07-09.md" "cpo-optical/cpo-optical-2026-07-09.md"

# 3. 移动散落的图片(若有)
git mv chart_*.png cpo-optical/assets/

# 4. 修正 .md 里的相对路径(若引用了旧目录)

# 5. 提交
git add -A
git commit -m "rename: CPO光互联 → cpo-optical,英文化命名"
```

---

## 八、报告 URL 生成(放好后必须返回给用户)

报告**提交并 push 之后**,必须把以下链接用 Markdown 形式返回给用户,方便点击查看。

### 模板

| 用途 | 模板 |
|---|---|
| 浏览器查看(GitHub 渲染) | `https://github.com/<owner>/<repo>/blob/<branch>/<dir>/<file>.md` |
| 目录浏览 | `https://github.com/<owner>/<repo>/tree/<branch>/<dir>` |
| 原始 Markdown | `https://raw.githubusercontent.com/<owner>/<repo>/<branch>/<dir>/<file>.md` |

### 本仓库填充值

- `<owner>` = `Xyz9Selu`
- `<repo>`  = `reports`
- `<branch>` = `main`

### Agent 操作流程

1. `git add -A && git commit -m "<type>: <主题> <日期> ..."`
2. `git push origin main`
3. 计算链接并返回:
   ```markdown
   报告已发布:
   - 渲染页: https://github.com/Xyz9Selu/reports/blob/main/<dir>/<file>.md
   - 目录页: https://github.com/Xyz9Selu/reports/tree/main/<dir>
   ```

### 注意事项

- `<dir>` 和 `<file>` 必须与 git 实际路径**完全一致**(大小写敏感,GitHub 区分大小写)。
- 默认 `main` 分支;若发布到其他分支则替换。

---

## 九、修订记录

| 日期 | 修订内容 |
|---|---|
| 2026-07-09 | 初版,定义主题目录、命名、自查清单 |
| 2026-07-09 | 英文优先(kebab-case),新增 §八 URL 生成规则;统一改为英文目录/文件名 |
| 2026-07-09 | 移除 §九 报告索引(节省 agent 上下文),整体精简 |