# Reports 项目目录规约

本仓库用于输出**公共报告**,所有产物面向公开发布。任何 AI agent 在创建、移动、重命名、提交文件之前,**必须先读完本文件并遵守规约**。有疑问先停下来问,不要动手。

**项目仓库:** `https://github.com/Xyz9Selu/reports`

---

## 一、核心原则

1. **一个主题 = 一个目录**。一份报告及其全部素材集中放在以主题命名的目录里,绝不散落到仓库根目录。
2. **目录名稳定,文件名带日期**。同一主题多次更新沿用同一目录,版本通过文件名中的日期区分。
3. **素材与报告同级管理**。图片、数据、脚本只放在所属主题目录下的 `assets/`、`data/`、`scripts/` 子目录。
4. **根目录最小化**。根目录只允许 `README.md`、`.gitignore` 等配置文件。任何新文件先想清楚属于哪个主题。
5. **永不覆盖历史版本**。同名同日期的文件视为冲突,需用户确认;旧版报告只增不删。
6. **英文优先 (English-first)**。主题目录、报告文件、素材文件**统一使用英文小写 + 连字符**(`kebab-case`)。URL、跨平台兼容性、跨语言检索都更友好。中文/英文混用会增加冲突概率,严格禁止。

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
│   ├── assets/                        ← 该报告用到的图片
│   │   ├── chart_valuation.png
│   │   ├── chart_radar.png
│   │   └── chart_risk_matrix.png
│   ├── data/                          ← 原始数据(可选)
│   │   └── financials.csv
│   └── scripts/                       ← 生成图表的脚本(可选)
│       └── gen_charts.py
│
├── ev-q3-2026/                        ← 电动车 2026Q3 主题
│   ├── ev-q3-2026-2026-09-15.md
│   └── assets/
│       └── trend.png
│
└── _template/                         ← 新报告模板(可选)
    └── TEMPLATE.md
```

---

## 三、命名规范

### 3.1 主题目录名

- **英文 kebab-case**:`小写字母 + 数字 + 连字符(-)`。
- **简短、可读、稳定**:2–24 个字符。英文转写的中文名(如 `xingye-silver-tin`)可放宽。
- **不带日期**(日期写在文件名里)。
- **避免空格和特殊字符**(`/`, `\`, `:`, `*`, `?`, `"`, `<`, `>`, `|`、连续 `-`、首尾 `-`、首尾空格)。
- **同一中文主题必须有固定的英文翻译**,不能今天叫 `cpo-optical` 明天叫 `cpo-interconnect`;在 README 的 §九(当前报告索引)中可附中文别名,但目录只能有一个英文名。

| ❌ 反例 | ✅ 正例 | 说明 |
|---|---|---|
| `CPO光互联` | `cpo-optical` | 中英混用,改用纯英文 |
| `CPO 光互联` | `cpo-optical` | 含空格 |
| `CPO_Optical` | `cpo-optical` | 用下划线,统一用连字符 |
| `CPO-optical-2026` | `cpo-optical` | 目录不带日期 |
| `cpo optical interconnect` | `cpo-optical` | 含空格 |
| `CPO光互联最终版` | `cpo-optical` | "最终版" 应放在文件名或 README,目录只表达主题 |
| `cpo-optical & photonics` | `cpo-optical` | 含特殊字符 `&` |

### 3.2 报告文件名

格式:**`<主题目录名>-<YYYY-MM-DD>.md`**

- 日期用 **ISO 8601**:`YYYY-MM-DD`,便于排序。
- 同主题再次更新 → 新日期文件,**保留旧版**。
- 不要加 `v2`、`final`、`最新版`、`草稿` 等后缀,日期本身就是版本号。
- 文件名也使用英文 kebab-case。

| ❌ 反例 | ✅ 正例 |
|---|---|
| `CPO光互联.md` | `cpo-optical-2026-07-09.md` |
| `CPO光互联-final.md` | `cpo-optical-2026-07-09.md` |
| `CPO光互联-v2.md` | `cpo-optical-2026-07-21.md` |
| `CPO光互联-20260709.md` | `cpo-optical-2026-07-09.md` |

### 3.3 素材文件名

- **英文小写 + 下划线 + 数字**,便于跨平台。
- 同名含义相同(同一图表跨版本可复用)。
- 不要包含主题名(目录已经表达了主题)。

| ❌ 反例 | ✅ 正例 |
|---|---|
| `估值图.png` | `chart_valuation.png` |
| `最终雷达图 (1).png` | `chart_radar.png` |
| `CPO_Chart_Radar.PNG` | `chart_radar.png` |
| `image.png` | `chart_supply_chain.png` |

---

## 四、Markdown 报告内容规范

1. **标题层级**:`#` 写报告标题,正文从 `##` 开始。
2. **图片引用使用相对路径**:
   ```markdown
   ![估值图表](assets/chart_valuation.png)
   ```
   禁止绝对路径、禁止用外链 URL 替代本地素材。
3. **每个图表在 `assets/` 必须存在,正文里至少被引用一次**;反过来,引用了的图必须有文件。
4. **报告末尾注明来源与时间**:
   ```markdown
   ---
   数据截至:2026-07-08
   生成时间:2026-07-09
   ```
5. **不要在 Markdown 里嵌 base64 大图**;统一放 `assets/`。
6. **不要在报告正文里贴大段爬虫原始输出**;原始数据放 `data/`,正文里只放结论和图表。

---

## 五、AI Agent 自查清单

任何 agent 在执行写文件操作**之前**,逐项自查:

- [ ] 我要创建的文件属于哪个主题?对应目录是否存在?不存在就先建。
- [ ] 文件名是否符合 §三 的规范?(英文 kebab-case)
- [ ] 图片/数据/脚本是否放在了 `<主题>/assets/`、`data/`、`scripts/`?
- [ ] Markdown 里引用的图片,文件是否都已生成并位于 `assets/`?
- [ ] 我是否会让根目录出现新文件?如果是,停下来确认它不属于任何主题。
- [ ] 我是否会**覆盖**已有文件?是的话必须先向用户确认。
- [ ] 我是否会**删除**已有文件?默认禁止;真要删先问用户。
- [ ] 是否设置了 `git mv` 而不是 `mv`(保留历史)?
- [ ] 新增/修改后是否同步更新了 §九 当前报告索引?

**任何一项拿不准,停下来问用户,不要直接动手。**

---

## 六、禁止事项

- ❌ 把任何报告、图片、数据放在仓库根目录。
- ❌ 多个主题混在同一个目录。
- ❌ 覆盖已有报告(同日期同名文件 = 冲突,需用户确认)。
- ❌ 删除历史报告(只允许新增,或经用户明确同意后归档)。
- ❌ 用空格、`#`、`?`、`(`、`)` 等特殊字符命名文件。
- ❌ Markdown 中用外链图片替代本地 `assets/` 引用。
- ❌ 同一主题存在多个并列目录(如同时有 `cpo-optical` 和 `CPO光互联`)。
- ❌ 同一主题混用中英文目录/文件名(如目录叫 `cpo-optical` 而文件名是 `CPO光互联-2026-07-09.md`)。
- ❌ 提交临时文件、IDE 配置、爬虫日志(用 `.gitignore` 忽略)。
- ❌ 把单个文件当作"主题"(主题必须是目录,即使里面只有一份报告)。

---

## 七、迁移历史散落文件

如果发现历史文件散落在根目录或使用中文命名,按以下步骤整理:

```bash
# 1. 用 git mv 改名为英文目录(保留历史)
git mv "CPO光互联" cpo-optical

# 2. 用 git mv 改名为英文文件名
git mv "cpo-optical/CPO光互联-2026-07-09.md" "cpo-optical/cpo-optical-2026-07-09.md"

# 3. 移动该报告相关图片(若有散落在根目录的)
git mv chart_*.png "cpo-optical/assets/"

# 4. 更新 Markdown 里的图片引用(若引用了旧目录路径)
#    ![alt](chart_valuation.png) → ![alt](assets/chart_valuation.png)

# 5. 提交
git add -A
git commit -m "rename: CPO光互联 → cpo-optical,英文化命名"
```

---

## 八、报告 URL 生成

每份报告都可以直接生成一个**可在浏览器打开的 GitHub URL**,用户点击即可查看(带 GitHub 渲染)。

### 8.1 URL 模板

| 场景 | 模板 | 备注 |
|---|---|---|
| 在浏览器查看(推荐) | `https://github.com/<owner>/<repo>/blob/<branch>/<dir>/<file>.md` | GitHub 自动渲染 Markdown |
| 查看原始 Markdown 源码 | `https://raw.githubusercontent.com/<owner>/<repo>/<branch>/<dir>/<file>.md` | 纯文本,适合脚本抓取 |
| 查看目录树 | `https://github.com/<owner>/<repo>/tree/<branch>/<dir>` | 列出目录内所有文件 |
| 查看图片(浏览器) | `https://github.com/<owner>/<repo>/blob/<branch>/<dir>/assets/<img>.png` | GitHub 自动渲染 PNG |
| 查看图片(raw) | `https://raw.githubusercontent.com/<owner>/<repo>/<branch>/<dir>/assets/<img>.png` | 直链,可被 Markdown 渲染 |

### 8.2 本仓库的填充值

- `<owner>` = `Xyz9Selu`
- `<repo>`  = `reports`
- `<branch>` = `main`

所以本仓库的浏览器查看链接简化为:

```
https://github.com/Xyz9Selu/reports/blob/main/<dir>/<file>.md
```

### 8.3 生成步骤

Agent 在产出新报告后,**必须**执行以下三步:

1. `git add -A && git commit -m "<type>: <主题> <日期> ..."`
2. `git push origin main`
3. 计算并把以下两个链接返回给用户:
   - **GitHub 渲染页**:`https://github.com/Xyz9Selu/reports/blob/main/<dir>/<file>.md`
   - **目录浏览页**:`https://github.com/Xyz9Selu/reports/tree/main/<dir>`

并在回复里以可点击 Markdown 形式给出,例如:

```markdown
报告已发布,链接:
- 渲染页: https://github.com/Xyz9Selu/reports/blob/main/cpo-optical/cpo-optical-2026-07-09.md
- 目录页: https://github.com/Xyz9Selu/reports/tree/main/cpo-optical
```

### 8.4 注意事项

- 链接里的 `<dir>` 和 `<file>` 必须和实际 git 中的路径**完全一致**(英文、连字符、大小写)。GitHub 区分大小写,大小写错了会 404。
- 默认指向 `main` 分支;若发布到其他分支,把 `main` 换成对应分支。
- 若启用了 GitHub Pages,渲染页可以用 `<owner>.github.io/<repo>/<dir>/<file>` 的形式,这里是 raw 仓库所以用 blob 链接。

---

## 九、当前报告索引

所有已发布的报告(以及对应 GitHub 链接):

| 主题(英文) | 中文别名 | 最新日期 | 报告 | GitHub 链接 |
|---|---|---|---|---|
| `cpo-optical` | CPO 光互联 | 2026-07-09 | `cpo-optical-2026-07-09.md` | [查看](https://github.com/Xyz9Selu/reports/blob/main/cpo-optical/cpo-optical-2026-07-09.md) |
| `xingye-silver-tin` | 兴业银锡 | 2026-07-09 | `xingye-silver-tin-2026-07-09.md` | [查看](https://github.com/Xyz9Selu/reports/blob/main/xingye-silver-tin/xingye-silver-tin-2026-07-09.md) |
| `iris-daily` | Iris 日报 | 2026-07-09 | `iris-daily-2026-07-09.md` | [查看](https://github.com/Xyz9Selu/reports/blob/main/iris-daily/iris-daily-2026-07-09.md) |
| `iris-daily` | Iris 日报 | 2026-07-08 | `iris-daily-2026-07-08.md` | [查看](https://github.com/Xyz9Selu/reports/blob/main/iris-daily/iris-daily-2026-07-08.md) |
| `iris-daily` | Iris 日报 | 2026-07-07 | `iris-daily-2026-07-07.md` | [查看](https://github.com/Xyz9Selu/reports/blob/main/iris-daily/iris-daily-2026-07-07.md) |
| `openclaw-memory` | OpenClaw 记忆体系 | 2026-07-08 | `openclaw-memory-2026-07-08.md` | [查看](https://github.com/Xyz9Selu/reports/blob/main/openclaw-memory/openclaw-memory-2026-07-08.md) |

### 主题目录浏览

- `cpo-optical/` → https://github.com/Xyz9Selu/reports/tree/main/cpo-optical
- `xingye-silver-tin/` → https://github.com/Xyz9Selu/reports/tree/main/xingye-silver-tin
- `iris-daily/` → https://github.com/Xyz9Selu/reports/tree/main/iris-daily
- `openclaw-memory/` → https://github.com/Xyz9Selu/reports/tree/main/openclaw-memory

> 新增主题时,在此表追加一行,并在 §三.1 中确认英文目录名已固定。

---

## 十、修订记录

| 日期 | 修订内容 | 修订人 |
|---|---|---|
| 2026-07-09 | 初版,定义主题目录、命名、自查清单 | — |
| 2026-07-09 | 补充 §八 URL 生成规则、§九 当前报告索引;统一改为英文命名(cpo-optical、xingye-silver-tin、iris-daily、openclaw-memory) | — |