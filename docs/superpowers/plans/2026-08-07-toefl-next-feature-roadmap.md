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

目前缺少的是「自動產生可做的 drill、完成後連到新題 transfer、最後集中呈現成果」的完整流程。

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
Milestone 1 Drill Generator
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
