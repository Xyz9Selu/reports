# OpenClaw 记忆体系调研:全景 + 最佳实践

> 本报告基于 2026-07-08 在主会话中完成的 OpenClaw 2026.6.5 memory/context 体系调研,围绕"现状摸清 → 断裂点定位 → 行动建议"三段式展开。

---

## 一、当前架构全景

你其实已经堆了**三层半记忆系统**,但只有两层半在运作:

### ① MEMORY.md + memory/*.md(核心,最常用)
- ✅ MEMORY.md 85 行 / 11KB,正好在默认 bootstrapMax 的 20KB 线内,**没有截断**
- ✅ 148 个 daily note 文件,总共 14K 行
- ✅ `memory/.dreams/` 的 dreaming 系统一直在跑(events.jsonl 当天还在更新)
- ⚠️ dream promotion 还在做,但从 6/11 起 dreaming 的 short-term-recall 就停在那个日期的 migrated 文件 —— **promotion 管道半挂**

### ② memory-wiki(已启用,但被孤立)
- ✅ 配置在,vault 路径 `~/.openclaw/wiki/main`
- ❌ 最后一次编译 5/22,之后就没动过
- 原因:`includeCompiledDigestPrompt: false` → agent 不主动用它,wiki 只是个静态存档

### ③ active-memory 插件(已 disable)
- ❌ 配置还在但已关 —— 6/10 关 memorySearch 时顺带禁掉

### ④ memorySearch(彻底关闭)
- ❌ `enabled: false`,所有 agent 都搜不了
- 根因:SQLite meta 表不稳定
- fallback "none",不降级

---

## 二、关键断裂带

### 断裂 1:memorySearch 关了,但 dreaming promotion 还在跑
Dreaming 依赖 memory_search 做 recall gate,search 关了 = promotion gate 永远过不了。Candidates 写了但升不了 MEMORY.md。这就是为什么 6/11 后 short-term-recall.json 不再更新。

### 断裂 2:MEMORY.md 靠手工 curate,没有定期自动 distill
- AGENTS.md 里写了"定期 review daily notes → curate MEMORY.md",但实际没有机制保证
- 上次手动 promotion 是 7/7(从 daily 升到 MEMORY.md),但 curated 质量看运气
- 没有 cron 守护,没有 pre-compaction hook

### 断裂 3:compaction 触发时重要内容直接丢
当前对话被压缩时,所有未写入文件的关键决策、临时发现、状态变更全部丢失。这是 silent mode 的物理基础。

### 断裂 4:memory-wiki 装了没用
- 配置在、磁盘占着、agent 完全不用
- 既不是知识库,也不是搜索后端,纯粹是历史包袱

---

## 三、行动建议(按优先级)

### 🥇 P0:修 memorySearch(让 dreaming 管道复活)

**最小动作**:把 `memorySearch.provider` 从 SQLite 切到外部向量后端。

**推荐方案**:用 Gemini(你已经有 gemini-balance 的 key)。

具体步骤:
1. 在 `~/.openclaw/config.yaml` 加 `memorySearch.provider: gemini`
2. 配置 embedding endpoint:`http://localhost:8001/v1beta/...`(走 gemini-balance)
3. `fallback: none` 保持不变,但主路径走通
4. 重启 gateway,跑一次 `openclaw memory search "test"` 验证
5. 观察 `~/.openclaw/workspace/memory/.dreams/short-term-recall.json` 是否开始更新

**风险**:
- gemini-balance 是 OpenAI 兼容,OpenClaw 的 memorySearch 接口未必直接吃 —— 第一次试可能 schema 不匹配
- 如果不行,备选 provider:本地 sentence-transformers(慢但稳)

### 🥈 P1:加 pre-compaction flush hook

配置里加一行 `compaction.flushMemory: true`(假设 OpenClaw 2026.6.5 已支持;如不支持,需要先升级或写一个 wrapper)。

有了这行,每次 compaction 之前系统会自动跑一个静默 turn,提醒 agent 把当前对话里的重要内容写到 memory 文件里。这比任何手工策略都准时。

### 🥉 P2:MEMORY.md 瘦身与结构化

当前 11KB,好在还在 bootstrap 线内。但 85 行里有太多"漫游轨迹片段"(夏至 lag、Arecibo 信、个人 lag...),真正**可行动的记忆**只占 ~40%。

**短期**(今天能做的事):把"漫游类"内容归档到意识流文件(`memory/curiosities.md` 或类似),MEMORY.md 只留:
- 用户偏好(John/USER 信息、通信规则)
- 决策记录(A 股持仓、browser-use 选型记录)
- 系统决策(memorySearch 关闭的原因、fallback 链结构)
- 铁律(安全准则、执行纪律)

**长期**:等 dreaming 恢复后,让系统自动做这个 distill。

### P3:memory-wiki 要么用,要么拆
当前状态是"装了但没用"。如果你确认不要,就把配置里的 `enabled: false`,或者真的把它当一个知识库去维护 —— 至少每周 ingester 跑一次。

---

## 四、一句话总结

你当前的 memory 系统**表层正确但中层断裂**:MEMORY.md + daily notes 在正常运转,但 **memorySearch 关闭导致 dreaming 管道半死**,**compaction 没有 memory flush**,**memory-wiki 建了没用**。

**最该动的就是 P0 修复 search** —— 让 dreaming pipeline 复活,自动做你手工懒得做的 distill 工作。

---

## 五、关键证据链

| 现象 | 数据来源 | 状态 |
|---|---|---|
| MEMORY.md 85 行 / 11KB | `wc -l ~/.openclaw/workspace/MEMORY.md` | ✅ 正常 |
| 148 个 daily note | `ls ~/.openclaw/workspace/memory/ | wc -l` | ✅ 正常 |
| dreaming 事件在写 | `memory/.dreams/events.jsonl` 当天 mtime | ✅ 在写 |
| promotion 半挂 | `memory/.dreams/short-term-recall.json` mtime 停在 6/11 | ❌ 异常 |
| memorySearch 关 | `~/.openclaw/config.yaml` `memorySearch.enabled: false` | ❌ 关闭 |
| memory-wiki 孤立 | `~/.openclaw/wiki/main` 最后编译 5/22 | ❌ 孤立 |
| 上次手工 promotion | MEMORY.md 中 7/7 时间戳 | ⚠️ 手工 |

---

数据截至:2026-07-08
生成时间:2026-07-09