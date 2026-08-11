# TOEFL 寫作自適應精熟與修訂鏈設計

日期：2026-08-07
狀態：待實作
範圍：TOEFL iBT 2026 Writing 的 Write an Email 與 Write for an Academic Discussion

## 1. 為何現在需要這個功能

目前 learner tracker 有 4 篇 `formal_original` 與 13 篇 `revision`。正式原稿中，`GRAM-CLAUSE` 出現在全部 4 篇；兩篇 Academic Discussion 分別有 `DISCUSSION-ELABORATION` 與 `DISCUSSION-SUPPORT`，但現行原子錯誤碼將它們各自呈現為一次新問題。另一方面，修訂鏈可達 Discussion 4 分與 Email 5 分，卻需要多輪修訂，且中途會引入新錯誤。

現行三篇里程碑報告只把直接以 formal original 為 parent 的 revision 納入 revision success，因此無法完整描述 R2 之後的修訂鏈。這會低估最後的修訂成果，也無法指出「同一篇改太久，應改做新題遷移驗證」的時機。

本設計把現有 tracker 從「列出錯誤」補強為「安排下一個最小有效練習，並驗證是否遷移到新題」。

## 2. 目標與非目標

### 目標

1. 為 `GRAM-CLAUSE` 建立由局部練習到新題正式作答的遷移流程。
2. 讓每條 revision chain 都能顯示首輪、最新輪、輪數、新錯誤與最終結果，不把多輪資料錯算為單一百分比。
3. 在不改變既有原子錯誤碼的前提下，顯示 `IDEA-DEVELOPMENT` 等能力群組，使 Discussion 的論證展開問題可跨 `DISCUSSION-ELABORATION` 與 `DISCUSSION-SUPPORT` 被看見。
4. 產生可解釋的下一次練習建議，仍遵守第一輪最多三個改善目標與不預先提供完整範文的規則。

### 非目標

- 不把任何單題或 drill 成績換算為 Writing section band。
- 不修改既有 original、revision、error event、rubric version 或 `historical_status`。
- 不由腳本判斷英文好壞；AI 仍負責語意回饋與事件標記，腳本只計算、驗證與產生衍生報告。
- 不阻止 learner 繼續修訂；兩輪後的規則是教練的「建議切換」，不是資料寫入禁令。

## 3. 使用者可見流程

```text
正式原稿
  → 第一輪回饋：最多三個目標
  → 最多兩輪完整修訂
  → 仍未完全解決時：針對性 drill
  → 全新、限時 formal original 作遷移測試
  → 依新題證據更新 mastery 與下一次計畫
```

對 `GRAM-CLAUSE`，drill 可包含 fragment、comma splice、讓步句、條件句與動詞框架轉換。對 Discussion 的 `IDEA-DEVELOPMENT`，drill 必須要求「主張 → 因果機制 → 具體結果 → 回扣立場」，而不是提供完整範文。

## 4. 資料模型與不變量

### 4.1 Revision lineage：衍生而非重寫

新增純函式 `root_formal_attempt(attempt_id)`：沿著 `parent_attempt_id` 找到 root formal original。它必須拒絕遺失 parent、跨 modality parent、cycle 與時間倒流。

每條鏈的衍生摘要至少包含：

```yaml
root_attempt_id: W-AD-20260805-001
revision_ids:
  - W-AD-20260805-001-R1
latest_revision_id: W-AD-20260805-001-R7
round_count: 7
score_trajectory: [3, 3, 3, 3, 3, 3, 4, 4]
latest_outcome:
  assigned: 3
  resolved: 3
  partly_resolved: 0
  unresolved: 0
  new_errors: 0
first_full_resolution_round: 6
total_new_errors: 8
switch_recommended_after_round: 2
```

`revision_outcomes` 是「該輪相對上一版」的結果。報告不得把多輪的 `resolved / assigned` 相加後稱為同一組目標的成功率；必須分別呈現首輪結果、最新輪結果、首次完全解決輪數與每輪新錯誤。

### 4.2 Targeted drill：不可混入正式 task 分數

沿用 `record_type: targeted_drill`，但新增只適用於 drill 的結構化 metadata：

```yaml
drill:
  drill_type: clause_transform
  target_codes: [GRAM-CLAUSE]
  target_family: SENTENCE-CONTROL
  source_attempt_id: W-AD-20260805-001
  items_total: 10
  items_correct: 8
  evidence_ids: [DRILL-...]
```

規則：

- drill 沒有 `task_score`，不增加 formal count，也不進入 dashboard score trend。
- 每個錯誤判定仍需有原文或 learner 作答證據；drill 不得用虛構正確率建立精熟狀態。
- `source_attempt_id` 必須能回溯至同一 modality 的 existing formal original。
- drill 可關聯 Email 或 Discussion，但共用語言目標可跨這兩條寫作路線。

### 4.3 Mastery 狀態：與 `historical_status` 分離

新增 derived `mastery` 摘要，不覆寫每個 error event 的 `historical_status`：

| 狀態 | 依據 |
|---|---|
| `identified` | 最近正式原稿出現目標錯誤。 |
| `practised` | 有至少一筆有效 targeted drill。 |
| `provisional` | 兩組 drill 都達門檻（各至少 8 題、正確率至少 80%）。 |
| `transferred` | 新的 formal original 有至少 3 個相關機會，且 0 個該目標事件。 |
| `controlled` | 兩篇不同的新 formal originals 都符合 transferred 條件。 |
| `relapsed` | 曾為 transferred/controlled 後，在新的 formal original 再次出現。 |

無相關使用機會的作文不能當作成功控制證據。

### 4.4 能力群組：只做衍生彙整

新增版本化 `writing-skill-families.yaml`。第一版至少包含：

```yaml
version: 1
families:
  SENTENCE-CONTROL:
    members: [GRAM-CLAUSE, GRAM-AGREEMENT, GRAM-ARTICLE, GRAM-NEGATION]
  LEXICAL-NATURALNESS:
    members: [LEX-COLLOCATION, LEX-WORDFORM]
  IDEA-DEVELOPMENT:
    members: [DISCUSSION-ELABORATION, DISCUSSION-SUPPORT]
  EMAIL-ACTION-CLARITY:
    members: [EMAIL-ACTION, EMAIL-MISSING-POINT, EMAIL-ORGANIZATION]
```

family 是報告與建議用的視角，不是新的 counted event code。每個 family hit 必須保留其 member code、attempt ID 與 exact excerpt。`IDEA-DEVELOPMENT` 可因此顯示為兩篇 Discussion 的共同診斷，但不會把 `ELABORATION` 與 `SUPPORT` 的原始事件混成一個新事件。

## 5. 下一次練習決策

`build_writing_training_plan()` 讀取 ordered formal originals、revision lineage、drills 與 families，輸出最多兩個 active targets：

1. 優先 `relapsed`、再來 `identified` 且跨最多 formal originals 的 shared code。
2. 有兩篇以上同 family 的 Discussion evidence 時，加入 `IDEA-DEVELOPMENT`，但仍顯示個別證據。
3. 已有兩輪 revision、但尚未完全解決時，建議 drill 與新的 formal original，而不是第三輪完整重寫。
4. Email 與 Discussion 的 task-specific target 只能在其對應 route 顯示；shared code 可跨 route。

目前 learner 的預期初始計畫：

1. `GRAM-CLAUSE`：先做 clause transform drill，再做新的限時 Academic Discussion。
2. `IDEA-DEVELOPMENT`：用一個因果鏈練習，接著在新的 Academic Discussion 寫一個完整理由。

`LEX-COLLOCATION` 與 `EMAIL-ACTION` 應保留在候補清單；除非 learner 本次選擇 Email，才取代第二項。

## 6. 報告與教練輸出

新增或擴充衍生檔：

- `tracker/writing/training-plan.md`：目前兩個 active targets、原因、下一個動作與遷移條件。
- `tracker/writing/mastery.md`：每個 active code 的 mastery 狀態、drill 證據與 formal transfer evidence。
- 既有 common/task reports 增加 `## Revision chains` 與 `## Skill families`，但維持三篇 milestone 的生成規則。

每筆 revision chain 顯示：root、輪數、分數軌跡、首輪／最新輪 outcomes、首次完全解決輪數、總新錯誤、是否建議切換。報告不能把最新修訂的 5 分當成新的 formal trend。

寫作 skill 在 progress request 時讀取 `training-plan.md`；在 revision round 2 後，如果仍未完全解決，要給出 bounded drill 與新題遷移任務。第一輪回饋合約維持不變。

## 7. 驗收標準

1. `GRAM-CLAUSE` 在目前四篇 formal originals 中被顯示為跨四篇的最高優先 shared target。
2. `IDEA-DEVELOPMENT` 顯示兩篇 Academic Discussion 的 member evidence，而不改寫舊 error code。
3. 對多輪 revision chain，報告能看見 R2 之後所有 revisions，並分開呈現首輪與最新輪 outcomes。
4. 兩輪後的 revision 不會被拒絕，但 training plan 會推薦 drill + new formal transfer test。
5. drill 不改變 formal count、task score trend、三篇 milestone 報告的正式計數。
6. `controlled` 僅能由足夠機會的新 formal originals 建立；沒有使用機會不能充當成功。
7. `rebuild_reports.py` 具冪等性，`validate_tracker.py` 能拒絕 lineage cycle、錯誤 drill metadata 與 stale derived outputs。

## 8. 相容性與資料保護

此功能只能新增 derived 檔案與新練習資料。既有使用者的 attempts、JSONL events、分數與回饋一律不可重寫。實作時必須在獨立 feature worktree 中進行，且先以 fixture 複製現有 tracker 做 migration/rebuild 測試，再決定是否將衍生檔套用到主工作區。
