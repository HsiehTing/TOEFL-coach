# TOEFL Coaching System — Next Feature Roadmap

日期：2026-08-07
目標：把目前的弱點偵測、revision lineage、skill families、targeted drill、mastery 與 training plan 接成可重複運作的改善閉環。

## 現況基線

系統目前可以：

- 分開處理 2026 Writing Email 與 Academic Discussion。
- 保存不可覆寫的正式作答、巢狀修訂、評分版本與逐項證據。
- 每三篇產生 common 與 same-task 報告。
- 保留原子錯誤碼，同時顯示能力群組。
- 記錄不計分的 targeted drill，衍生 mastery 狀態。
- 在同一修訂鏈兩輪仍未完全解決時產生 training plan。

Drill、transfer 與 progress overview 的基礎 artifact 已存在；目前缺少的是一條可由 learner 從頭走到尾、結果可信且能恢復舊資料的完整流程。下列使用者流程複核取代「功能存在即視為可交付」的判斷方式。

## Incident-driven optimization requirements（2026-08-10）

本節將 `W-AD-20260809-002` 的 drill 產出問題轉成 Milestone 1 的必要開發需求。原始失敗案例為：Academic Discussion 的品牌行銷／世界盃題目，卻產生公共運輸、大學政策與新設施題目；同一 pack 含多組重複題；recommendation 要求 causal-chain items，輸出卻是無關的通用文法模板；並將 causal chain 的四個語意元素誤呈現為每題四個完整句子的硬性要求。

### 使用者流程複核與狀態（2026-08-10）

複核順序為：training plan → 產生 learner drill → 填答／讀取 → drill 結果 → transfer → mastery／下一步 queue。以下狀態以目前工作區與實際命令輸出為準，而非只看單元測試。

| 流程節點 | 狀態 | 結論 |
| --- | --- | --- |
| 從未解決 revision 產生 training plan | 可用 | 可產生有來源、route 與目標 code 的 recommendation。 |
| 新 pack 的答案隔離 | 已修復 | 目前 `build_drill_pack()` 的 learner markdown 不含 answer key；answer key 保持獨立。 |
| 重新產生既有 recommendation | 阻塞 | `WD-90608621535FD7B6` 的 persisted 內容與現行 renderer 對同一 ID 的輸出不同，immutable write 因而正確拒絕覆寫，但使用者無法取得可用的新 pack。 |
| 新生成題目的情境與獨立性 | 未修復 | 目前仍可生成公共運輸／大學設施模板，且可重複同一 prompt。 |
| 作答完整性讀取 | 可用 | 讀取器會拒絕遺漏的 response field。 |
| 開放題評量與 drill 統計 | 未修復 | 現行資料只有整組 `correct_count`；`W-DRILL-20260810-001` 同時記錄 0/8 與四題已有部分因果概念，不能可靠支持 mastery。 |
| transfer 前置條件 | 未修復 | 現行實作驗證來源、route、prompt 與 opportunity，但未強制檢查 drill 是否達到 recommendation 的最低正確率；0/8 理論上仍可送進 transfer。 |
| 多個 plan 的下一步呈現 | 未修復 | queue 只顯示一組行動，未說明其他 pending plan 是延後、阻塞或不支援。 |

歷史 artifact 要與現行功能分開處理：已存的 `WD-90608621535FD7B6/drill.md` 含示範答案，這是需要隔離或遷移的舊資料問題，不代表新的 learner renderer 仍會洩漏答案。現有測試與 tracker audit 通過只能證明其既有契約；本節的流程案例必須成為新的回歸契約。

### P0 lifecycle repair 實作進度（2026-08-10）

已完成：

- pack format 升級至 version 4；renderer／schema 更新會產生新的 stable drill ID，不覆寫舊 pack。
- 舊版或 learner artifact 含非 response 內容時，`read_completed_drill()` 會拒絕註冊。
- transfer 會檢查 persisted drill 的最低正確率；未達門檻不能進入新題 transfer。
- practice queue 會輸出 `ready`、`blocked_by_drill`、`blocked_by_accuracy`、`blocked_by_pack_drift`、`blocked_by_template` 等狀態與原因；目前工作區的舊 5-code drill 因與最新 2-code plan 不一致而顯示 `blocked_by_pack_drift`。
- 回歸測試已涵蓋 version collision、legacy pack、答案混入、低正確率 transfer 與 unsupported target 狀態。

尚未完成：

- source prompt 的情境抽取與 Academic Discussion 題目保真；目前仍需移除固定公共運輸／大學設施模板。
- 逐題 `meets_target`／`partially_meets_target`／`needs_revision` 評量與 mastery 統計重建。
- queue 對所有 active training plan 的完整排序、延後與不支援原因呈現。

### 需求 DRILL-CONTEXT-01：來源情境必須保真

- Drill context 必須保存 `source_attempt_id`、`task_type`、原始 prompt 的 route/context 摘要、target codes 與 exact evidence IDs。
- Academic Discussion 題目必須沿用來源題目的討論領域與 learner 的立場；本案例應留在品牌識別、品牌更新、世界盃行銷與顧客反應，不得降級成公共運輸或大學政策模板。
- Evidence link 不得只有 metadata 標籤；每個題目必須能說明它如何使用來源 evidence 或來源 task context。
- 若無法建立可信的 task context，產生器必須 fail closed，要求人工指定 context；不得產生看似完成但與原題無關的泛用題。

### 需求 DRILL-SHAPE-02：recommendation 與題型必須一致

- recommendation 必須明確區分 `grammar_control`、`clause_transform`、`causal_chain` 或其組合，不得只用 target code 推測題型。
- `causal_chain` 的 `claim → mechanism → concrete outcome/example → link back` 是四個語意欄位，不是每題四個完整句子的規定。
- 預設每個 causal-chain item 只要求一個簡短回答；若需要四欄結構，介面必須明確標示為四個短欄位，並顯示預期字數與總負擔。
- Grammar item 應以一句改寫或一句產出為基本單位，不得因為 causal-chain recommendation 額外膨脹成 `item_count × 4` 個完整句子。
- Learner-facing instructions may identify the target concept, but must not reveal the expected answer pattern (for example, prescribing `worth discussing` or `that is worth + -ing` in a task intended to test independent rewriting).

### 需求 DRILL-SCORING-07：開放題不得假設唯一答案

- `grammar_control`、`clause_transform` 與 `causal_chain` 的開放式題目通常有多個可接受答案；answer key 必須標示為「示範答案／接受條件」，不得宣稱只有一個正確句子。
- 每個 item 必須明確標記 `open_response` 或 `closed_response`；只有 closed-response item 才能使用唯一答案比對。
- Open-response 評量至少要區分 `meets_target`、`partially_meets_target` 與 `needs_revision`，不得因為未複製示範答案就直接計為錯誤。
- `correct_count` 的計算規則必須和 item kind、接受條件與 learner-facing instructions 一致；不得把開放題的整組結果簡化成沒有證據的 `0/N`。
- 回饋必須分開記錄「概念／因果鏈已出現」與「句法、搭配或格式仍需修正」，避免把部分成功誤報為完全失敗。

### 需求 DRILL-UNIQUENESS-03：題目必須獨立且不重複

- 同一 pack 內的 prompt 以正規化文字去重；不可只替換 item ID 或 evidence ID 就視為不同題目。
- 預設 8 題必須有 8 個可辨識的練習機會；若模板池不足，產生器應降低題數或 fail closed，不得複製題目填滿數量。
- 產生結果須保存 deterministic seed，但 seed 不得破壞去重與 route/context 驗證。

### 需求 DRILL-LOAD-04：工作量與指令必須可預期

- `item_count` 指的是 learner 要完成的 item 數，不得隱藏額外的句子倍增規則。
- learner-facing drill 必須在開頭明示：題數、每題回答形式、建議字數，以及是否需要新題 transfer。
- 8 題 causal-chain drill 的預設負擔應是 8 個短回答；不得默認為 32 個完整句子。
- answer key 必須繼續獨立保存，初次輸出不得洩漏完整答案。

### 需求 DRILL-QA-05：交付前自動品質檢查

產生器交付前必須執行以下 lint／contract checks：

1. source route、task type、target codes 與每題 kind 一致。
2. 每題均有 evidence ID 與可讀的 context binding。
3. pack 內 prompt 正規化後無重複。
4. recommendation 的 drill kind、item count 與 learner instructions 一致。
5. 題目不含與 source context 無關的固定模板領域；若 context binding 不足則 fail closed。
6. learner drill 與 answer key 的 item IDs、順序與欄位完全一致。
7. 開放題 answer key 含至少一個示範答案與可接受變體／判定條件；評量結果不得只靠字串相等。

### 需求 DRILL-ARTIFACT-08：immutable pack 必須可演進且可恢復

- Pack identity 必須納入 renderer／prompt-schema 版本或等價內容 fingerprint；更改 learner-facing prompt 不得重用既有 drill ID。
- 遇到同 ID、不同內容的歷史 artifact 時，不得覆寫；應產生新的 versioned pack，並將舊 pack 標記為 legacy／不可重新使用的來源。
- 含 answer key、非預期文字或已知錯誤 renderer 輸出的 legacy learner drill，不得再作為新的練習或註冊來源；遷移需保留原始證據與既有 attempt，不得改寫。
- `read_completed_drill()` 必須能辨識受污染或 renderer 版本不相容的 pack，回報可操作的遷移指示，而非把洩漏的示範答案併入新的 prompt evidence。

### 需求 TRANSFER-GATE-09：transfer 必須真正受 drill 結果約束

- `prepare_transfer_attempt()` 必須讀取已持久化 drill 的最低門檻與逐題評量結果；未達門檻（例如 0/8）必須 fail closed。
- 只有達門檻的 target codes 可進入 fresh transfer；未達標的 code 必須回到限定 drill，不得藉由同一份 formal attempt 繞過。
- Transfer gate 的結果要寫入 queue：`ready`、`blocked_by_accuracy`、`blocked_by_incomplete_assessment` 或等價狀態與原因。

### 需求 QUEUE-STATUS-10：多個建議必須有可理解的排程狀態

- Queue 必須列出每個 active training plan 的狀態：現在執行、等待 drill 評量、可做 transfer、延後，或無支援模板。
- 當系統只選一組目前行動時，必須說明排序依據與其他 plan 未被選中的原因；不支援的 code 不得靜默消失。

### 需求 DRILL-REGRESSION-06：把本次錯誤固定成回歸案例

- 將 `W-AD-20260809-002` 的品牌行銷案例加入 drill-generation fixture。
- 測試必須拒絕公共運輸／大學政策題目混入該 Discussion pack。
- 測試必須拒絕重複 prompt，以及將四個 causal-chain 元素渲染成四句硬性作答要求的輸出。
- 測試必須確認 `GRAM-CLAUSE`、`GRAM-AGREEMENT` 與 Discussion causal-chain 題目可在同一 pack 中以明確、有限的形式共存。
- 測試必須確認開放題可接受多種正確表達，且部分符合目標時不會被錯誤彙整為 `0/8`；answer key 必須明確區分示範答案與唯一答案。
- 測試必須確認同一 recommendation 在 renderer 更新後取得新 ID，不會因 immutable collision 讓使用者無法產生新 pack；含答案的 legacy learner pack 必須被拒絕重新使用。
- 測試必須確認低於門檻的 drill 無法建立 transfer，即使來源、route、prompt 與 opportunity 都正確。
- 測試必須確認 queue 對所有 active plan 顯示明確狀態，並顯示 unsupported code 的原因。

### 本次事件的完成定義

此事件只有在以下條件全部成立時才算關閉：

- 來源題目、錯誤證據與 drill 情境一致。
- 每題都是獨立題目，無重複填充。
- 因果鏈四元素被當成語意要求，而非四句固定作文要求。
- 產出前 lint 能自動攔截 route/context、題型、重複與工作量錯誤。
- 開放題的示範答案、可接受變體與部分達成狀態可被保存並正確計算；不得以唯一答案或字串相等誤判整組作答。
- learner 完成 drill 後，仍可沿用既有 `targeted_drill → new-prompt transfer` 流程。
- 既有 legacy pack 不阻塞重新產生可用的新版本，且不會把洩漏答案帶入新的 prompt evidence。
- 未達 drill 門檻不能建立 transfer；部分達標會保留逐題證據而非被壓成誤導性的整組分數。
- 使用者能看見所有 active training plan 的目前狀態與下一步理由。

## 開發原則

- 不改寫 formal original、revision、舊 rubric evaluation 或 error event。
- Drill、transfer 與 mastery 都不得宣稱為 TOEFL task score 或 section band。
- 每個訓練建議必須回連到 attempt ID、錯誤碼與確切證據。
- Email 與 Academic Discussion 保持不同任務路線；只有 common language code 可跨路線。
- 衍生檔可以重建，來源紀錄不可覆寫。
- 每個 milestone 先建立契約測試，再實作，最後執行全套測試與 `tools/validate_tracker.py`。

## Milestone 1 — Personalized Drill Pack Generator

優先度：P0

### 使用者結果

當 `training-plan.md` 指出 `GRAM-CLAUSE` 或 `IDEA-DEVELOPMENT` 等目標時，使用者可以直接取得一組可作答的練習，不必手動設計題目。

### 預計產物

- `tools/generate_writing_drill.py`
- `tools/toefl_tracker/drill_generation.py`
- route-specific drill templates
- `tests/test_drill_generation.py`

### 功能範圍

- 輸入 recommendation ID 或來源 attempt ID。
- 從 immutable evidence 取得錯誤摘錄，不接受沒有來源的泛用弱點描述。
- 預設產生 8 題；同一題不得只是複製原句與答案。
- `GRAM-CLAUSE`：辨識、合併、改寫與新句產出混合題型。
- `IDEA-DEVELOPMENT`：使用 claim → mechanism → concrete outcome/example → link-back 因果鏈。
- Email 任務使用請求、行動與具體細節語境；Discussion 使用立場與論證語境。
- 初次輸出不顯示完整答案；答案與解釋保存為可延後開啟的獨立 artifact。
- 產生 stable drill ID，供 `register_writing_drill.py` 使用。

### 驗收條件

- 每題可追溯至 recommendation、目標 code/family 與來源 attempt。
- 不混用 Email-only 與 Discussion-only code。
- Drill artifact 不含 `task_score`。
- 相同輸入與固定 seed 產生可重現結果。
- 空證據、未知 code、錯誤 route 必須 fail closed。

## Milestone 2 — Transfer Check Lifecycle

優先度：P0

### 使用者結果

完成 drill 後，系統會指定下一次應做的新題，並判斷弱點是否真正 transfer，而不是只會修改原句。

### 預計產物

- targeted drill schema v2 或相容擴充
- `tools/register_writing_transfer.py`
- `tools/toefl_tracker/transfer.py`
- `tests/test_transfer.py`

### 功能範圍

- 建立 `source formal → recommendation → drill set → transfer attempt` 的明確鏈結。
- Transfer 必須使用新 prompt；以 source hash 與 prompt hash 阻止重用原題。
- 記錄目標 code 的 opportunity count，區分「沒有錯」與「根本沒有使用機會」。
- 先產生 opportunity suggestion，再由教練確認後登錄，避免完全依賴自動推測。
- Mastery transition 保存 evidence IDs 與 transition reason。
- 只有達成 drill 門檻、至少三個可驗證 opportunity 且沒有相同 counted event，才可進入 `transferred`。
- 再經兩篇新的正式作答維持控制，才可進入 `controlled`；之後再犯標記 `relapsed`。

### 驗收條件

- Revision 與 targeted drill 不增加 formal count。
- 沒有 opportunity 的作答不能提升 mastery。
- 舊 event 的 `historical_status` 不被 mastery transition 改寫。
- 重複 prompt、斷裂 parent、跨 route transfer 必須被拒絕。

## Milestone 3 — Writing Progress Overview

優先度：P1

### 使用者結果

使用者開啟一份報告即可回答：最近三篇有沒有進步、哪些錯誤一再出現、修訂是否有效、下一步該練什麼。

### 預計產物

- `tracker/writing/progress-overview.md`
- `tracker/writing/progress-overview.yaml`
- `tools/rebuild_progress_overview.py`
- `tests/test_progress_overview.py`

### 顯示內容

- 正式作答與 route 分布。
- 最近三篇的 task score、counted errors / 100 words、meaning-changing errors。
- Atomic code 與 skill-family 趨勢。
- Revision round count、最新解決率、首次完全解決輪次與新增錯誤。
- Targeted drill accuracy、mastery 狀態與 transfer evidence。
- 最多兩個下一步 focus，並說明選擇依據。
- Timing／assistance 未知時明確標示，不推測改善原因。

### 驗收條件

- 所有數字可由 immutable attempt 與 canonical event 重建。
- Common 與 route-specific 統計不互相污染。
- 不將單題趨勢換算為完整 section band。
- 在資料不足三篇時顯示 diagnostic-only early view，不偽造趨勢。

## Milestone 4 — Calibration Regression Suite

優先度：P1

### 功能範圍

- 為兩種 Writing route 各建立多組匿名化固定樣本。
- 保存預期 task-score range、關鍵 rubric 理由與必須辨識的 error codes。
- 比較相同 rubric version 下的重跑結果，偵測評分漂移與分類漂移。
- Rubric 更新時使用 `re_evaluation`，不得覆蓋舊評估。

### 驗收條件

- 分數落在核准範圍，且「why this level／why not next」契約完整。
- Counted event 必須有 exact excerpt。
- 第一輪仍維持最多三個目標與不提供完整範文。

## Milestone 5 — Speaking Progress Parity

優先度：P2

在 Writing 閉環穩定後，將相同概念延伸到 Listen and Repeat 與 Take an Interview，但保留 speaking-specific evidence：learner timestamp、角色確認、音訊可靠維度與 `diagnostic_only` 邊界。

## 建議執行順序

```text
P0 Lifecycle repair: legacy pack migration + transfer gate + queue status
    ↓
Milestone 1 Drill Generator hardening
    ↓
Milestone 2 Transfer Lifecycle
    ↓
Milestone 3 Progress Overview
    ↓
Milestone 4 Calibration
    ↓
Milestone 5 Speaking Parity
```

Milestone 1 與 2 應視為同一個 P0 release：只有 drill generator 而沒有 transfer，仍無法證明學習遷移；只有 transfer schema 而沒有可執行 drill，使用成本仍然過高。

## 下一個開發切入點

下一個 commit 從 `tests/test_drill_generation.py` 的 RED contract 開始，先固定：

1. `GRAM-CLAUSE` drill 必須引用真實 evidence，但題目不能洩漏完整答案。
2. `IDEA-DEVELOPMENT` drill 必須產生因果鏈欄位。
3. Email 與 Academic Discussion route isolation。
4. stable ID、固定 seed 可重現、未知 code fail closed。

完成 Milestone 1 後立即進入 Transfer Check Lifecycle，不插入新的低優先度報表功能。
