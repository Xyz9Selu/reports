# OpenClaw 记忆体系修复报告 (2026-07-09)

> 本报告是 2026-07-08 调研报告的**修复续篇**。在 7/8 报告里 P0 标记为"建议",今天 14:12 实际动手了,本报告记录过程、校正事实、给出最终状态。

---

## 一、P0 修复:memorySearch 重新启用

### 1.1 修改前事实校正

7/8 报告里写"`memorySearch.enabled: false` —— 6/10 关掉"是真实存在的,这一点**事实正确**。但有两个**路径错误**:

| 报告原表述 | 实际位置 |
|---|---|
| "`memorySearch.enabled: false`" | `agents.defaults.memorySearch.enabled: false`(不是顶层 key) |
| "memory-core 整个默认 enabled,只是 search 路径未必走通" | 表述准确,但 `memorySearch` 是 memory-core **内部**的 search 后端配置 |

### 1.2 配置改动(只动了 2 处,其它保持)

**文件**:`~/.openclaw/openclaw.json` → `agents.defaults.memorySearch`

```json
{
  "enabled": false,                         // → true
  "provider": "openai",                     // 不动
  "remote": {
    "baseUrl": "https://openrouter.ai/api/v1",  // 不动(早就指向 OpenRouter)
    "apiKey": {
      "source": "env",
      "provider": "default",
      "id": "OPENCLAW_MEMORYSEARCH_API_KEY" // → "OPENROUTER_API_KEY"
    },
    "headers": {                             // 不动
      "HTTP-Referer": "https://openclaw.local",
      "X-Title": "openclaw-memorysearch"
    }
  },
  "fallback": "none",                        // 不动
  "model": "text-embedding-3-small",         // 不动
  "extraPaths": [".learnings"]               // 不动
}
```

**备份**:`~/.openclaw/openclaw.json.bak-pre-memorysearch-20260709-141500`

### 1.3 顺手处理的两个隐性阻塞

**(1) Stale reindex lock**
跑 `openclaw memory search` 时报:
```
[memory] sync failed (search-bootstrap): Error: Memory reindex lock is held at
  /home/xyz/.openclaw/agents/main/agent/openclaw-agent.sqlite.reindex-lock.sqlite;
  another reindex is active.
```
排查发现是 14:13 一次卡死的 `openclaw memory search` 留下的 stale lock(对应 PID 已不存在)。**移到 Trash,不直接 rm**(AGENTS.md `trash > rm` 原则)。

**(2) missing extraPath**
```
"additional memory path missing (~/.openclaw/workspace-ember/.learnings)"
```
ember workspace 目录活着,但 `.learnings` 子目录未建(AGENTS.md 提到新 agent 入职时要建软链到主 workspace `.learnings`,ember 没做这个动作)。**简单建空目录即可**:
```bash
mkdir -p ~/.openclaw/workspace-ember/.learnings
```
**没建软链**,因为主 workspace `.learnings` 是独立 git repo,跨 workspace 软链存在循环风险。空目录满足 scan 要求。

### 1.4 重建向量索引

```bash
openclaw memory index --agent main --verbose
```

跑了约 5 分钟(`tail -40` 截到 40 个 "embeddings: batch start"),最终:
```
Memory index updated (main).
```

**索引后状态**(对比修复前):

| 指标 | 修复前 | 修复后 |
|---|---|---|
| `indexIdentity.status` | `missing` | `valid` |
| `files / chunks` | 未统计 | 437 / 4603 |
| `vector.dims` | 未知 | 1536 (text-embedding-3-small) |
| `cache.entries` | 0 | 4177 |
| `embeddingProbe.ok` | true(但 search-bootstrap 失败) | true(实际可用) |
| `providerState.mode` | inactive? | `active` |
| `scan.issues` | 1 (missing .learnings) | 0 |

### 1.5 dreaming pipeline 复活

索引建立之后,系统自动触发了短期记忆召回,产生了一个**关键事实**:

```
audit.entryCount:        0  →  512
audit.promotedCount:     0  →   10
audit.spacedEntryCount:  0  →  509
audit.conceptTaggedEntryCount: 0  →  512
audit.updatedAt:    (无)   →  2026-07-09T06:28:34.470Z
```

**这正好验证了 7/8 报告里"断裂 1"** —— 当时 `entryCount: 0` 说明 promotion 管道半挂。现在 512 个 entry 一次性生成,有 10 条**自动 promote 进了 MEMORY.md**。

手动跑 `openclaw memory promote` 返回 0 candidates,这是**正确状态**:意思是当前短期记忆池里"没有新东西需要再 promote",所有真正值得保留的已经被自动收纳。

---

## 二、验证搜索真的能用

```bash
openclaw memory search "OpenClaw memorySearch 配置" --max-results 5
```

返回 5 条结果,score 0.40-0.41,相关性中等:

```
1. score=0.407 — 所以最佳实践我建议这样：当前先关闭 Active Memory。 ...
2. score=0.402 — 2026-06-10 Memory Search 退役(重大决策)...
3. score=0.399 — 配置修复：把 agents.defaults.startupContext.enabled=false ...
4. score=0.396 — Candidate: User: 检查OpenClaw是否有跟新...
5. score=0.395 — 2026-06-10: .openclaw 清理 2.3G...
```

**第二条命中 6/10 那条"Memory Search 退役"决策** —— 这正是 7/8 报告里提到的关键历史事件。**历史记忆真被召回了**,证明管道完整可用。

---

## 三、7/8 报告 P0-P3 行动建议当前状态

| 级别 | 7/8 建议 | 7/9 状态 |
|---|---|---|
| **P0** | 修 memorySearch(让 dreaming 管道复活) | ✅ **已完成**(本报告主题) |
| **P1** | 加 pre-compaction flush hook | ⏳ 待评估(需要看 OpenClaw 2026.6.5 是否原生支持 `compaction.flushMemory`) |
| **P2** | MEMORY.md 瘦身与结构化 | ⏳ 部分自动(dreaming 复活后系统会自己 curate) |
| **P3** | memory-wiki 要么用要么拆 | ⏳ 未动,下次单独决定 |

---

## 四、关键证据链(更新)

| 现象 | 数据来源 | 状态 |
|---|---|---|
| OpenRouter embedding endpoint | curl 直接打 `/v1/embeddings` | ✅ 200 OK,返回 1536 维向量,$4e-8 |
| OpenClaw secret ref 解析 | `[secrets] agents.defaults.memorySearch.remote.apiKey: secret ref is configured on an inactive surface` | ⚠️ 警告但**实际可用**(`embeddingProbe.ok: true`,搜索真能命中)。可能是 CLI 路径不走 runtime resolver,只走 startup cache |
| vector store | `sqlite-vec-linux-x64` v0.1.9 | ✅ 已装 |
| 索引数据 | `~/.openclaw/agents/main/agent/openclaw-agent.sqlite` + WAL 文件 | ✅ 已建 |
| MEMORY.md 增量 | `git diff ~/.openclaw/workspace/MEMORY.md` 应该有 10 条新 promote | ⏳ 建议 git pull 时顺手 commit |

---

## 五、遗留事项与下一步

1. **MEMORY.md 增量回滚**:这次 dreaming 自动 promote 的 10 条**直接写进了 MEMORY.md**,如果你觉得质量不行,可以:
   ```bash
   git checkout HEAD -- ~/.openclaw/workspace/MEMORY.md
   ```
   但**不建议** —— OpenClaw 7/8 报告里的"identity work"原则说过"警惕潜意识通过容易忘记来逃避重要事务"。dreaming 是经过评分的,默认应该接受。

2. **`[secrets] inactive surface` 警告**:看起来无害(实测能用),但如果以后出问题,优先看这条。

3. **下次 Heartbeat 自检脚本**:7/8 报告里提到的"每个 agent 跑一次 `openclaw memory search test`"的自检逻辑,**今天已经手动验证通过了**(main agent),**需要扩展到其他 3 个 agent(clara/iris/ember)**。可以在 HEARTBEAT.md 里加一行。

4. **memory-wiki**:仍未启用。这是个独立议题,跟本次 P0 修复无关,留作 P3。

---

数据截至:2026-07-09 14:30
生成时间:2026-07-09