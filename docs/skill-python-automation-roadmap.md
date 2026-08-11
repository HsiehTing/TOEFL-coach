# Bug Capture Skill — Development Roadmap

日期：2026-08-11（重建）  
範圍：`.agents/skills/bug-capture/` 與唯一建立入口 `tools/capture_bug_report.py`。  
目標：讓正常使用 TOEFL coach 時發現的 bug，在任何修復前都有可重現、隱私受控、不可改寫且可一路追到驗證結果的證據鏈。

這是 Skill → Python CLI workflow 的第一個獨立專案。它不改變 TOEFL 題目、評分或 tracker 功能；實作時採獨立 branch，不混入主功能 roadmap。

## 不可跨越的邊界

- 只處理 learner 正常使用 coach 時遇到的非預期行為。
- 不用於 feature 開發、roadmap 整理、測試失敗、資料稽核，或刻意 fail-closed 的能力缺口。
- 缺少目的、預期、實際結果或至少一個錯誤前操作時，只補問事實，不建立報告、不診斷、不修改。
- skill 只能呼叫 public CLI；不得直接修改 `tracker/bug-reports/`、roadmap ledger 或 library module。
- 不保存 raw audio、credentials、完整未提交 diff（除非明確 opt-in 且已確認安全）、或與重現無關的 learner 內容。

## 目前基線（已完成）

| 能力 | 現況 | 證據 |
| --- | --- | --- |
| Scope gate 與 intake | 已建立 | `SKILL.md` 明確區隔正常使用 bug 與開發期問題。 |
| 唯一建立入口 | 已建立 | `tools/capture_bug_report.py` 呼叫 `toefl_tracker.bug_capture.capture_bug_report()`。 |
| 初始不可變 artifact | 已建立 | `report.yaml`、`snapshot.json`、`reproduction.md`、可選附件。 |
| Roadmap link | 已建立 | 唯一 TOEFL roadmap ledger 新增 Bug ID、狀態與 artifact 連結。 |
| 最小驗證 | 已建立 | Python 行為測試與 skill 契約測試。 |

目前 record schema 為 v1、初始狀態為 `reported`。它還沒有可復原的跨檔寫入流程、CLI 強制的附件隱私政策，或 append-only 的結案證據。

## 目標流程

```text
正常使用時的 defect
        ↓
Skill scope gate + 已確認 intake
        ↓
Capture CLI preflight（路徑、附件、privacy、roadmap）
        ↓
完整初始 artifact + 可復原 ledger link
        ↓
Read-only verify receipt
        ↓
調查與修復（原始 report 不改寫）
        ↓
Append-only resolution evidence + derived ledger status
```

## Milestone 1 — Capture transaction and recovery（P0，已完成）

目的：任何中斷都不能產生「roadmap 指向不存在 artifact」或無法識別的孤兒 report。

- 將 capture 改為 preflight → staging → 完整 artifact publish → atomic roadmap update 的順序；跨目錄無法原子化時以明確 journal / ready marker 表示狀態。
- 新增 idempotent recovery CLI，只修復已完整寫入但未連到 ledger 的 record；不得改寫 report 內容或自動刪除不明資料。
- ledger link 帶有 report artifact hash / schema version，驗證器可偵測斷鏈、重複 Bug ID、或摘要與 report 不一致。
- 為 report ID 產生與 ledger 寫入加入 lock / collision 防護。
- 加入 failpoint tests：附件複製失敗、artifact publish 後 roadmap 寫入失敗、重跑 recovery、同時 capture。

驗收：任一 failpoint 後，`verify_bug_reports.py` 可清楚列出可恢復狀態；recovery 重跑不產生第二個 Bug ID 或第二列 ledger。

實作結果：capture 現採 staging → `.ready` → publish → ledger 的順序；中斷後的 ready report 只能由 `recover_bug_reports.py` idempotently 補 link。ledger 會保存 schema version 與 `report.yaml` digest，`verify_bug_reports.py` 會以唯讀方式驗證 report、ledger、hash 與 staging 狀態；並行 capture 的 ID 與 ledger 列已有回歸測試。

## Milestone 2 — Privacy-safe evidence policy（P0，已完成）

目的：把目前 skill 的隱私指示變成 CLI 的硬性規則。

- 為附件加入 allow / deny policy：拒絕 raw audio、credentials、私鑰、環境檔與超出上限的檔案；接受明確的文字 log、終端輸出與圖片證據。
- report 僅保存 attachment 的原始檔名、相對儲存位置、MIME / size 與 checksum；不保存使用者機器的絕對原始路徑。
- snapshot 改為最小可重現環境：commit、branch、worktree 狀態、runtime；repository identity 使用穩定雜湊或 repo-relative identifier，避免暴露本機路徑。
- `--include-git-diff` 改成雙重明示的高風險路徑，並在 receipt 顯示是否實際保存 diff。
- 加入附件 policy、路徑去識別、大小上限與 diff opt-in 回歸測試。

驗收：不安全附件在建立 report 前被拒絕且不留下目錄；安全附件可由 checksum 驗證；artifact 中不含本機絕對附件路徑。

實作結果：CLI 僅接受小型文字／結構化資料或圖片附件，拒絕 raw audio、credential / key 類名稱與超過 10 MiB 的檔案；report 只保存檔名、相對路徑、MIME、大小與 checksum。snapshot 以 repository identity hash 取代本機絕對路徑；保留 git diff 必須同時指定 `--include-git-diff` 與 `--confirm-safe-git-diff`。

## Milestone 3 — Machine-readable CLI receipt and contract tests（P1，已完成）

目的：skill 能可靠呼叫 CLI，並能以機器可讀方式確認結果。

- 新增 `--format json` 成功 receipt：Bug ID、report path、schema version、ledger path、attachment count、privacy flags、validation result。
- 建立 CLI contract fixture：required arguments、重複 `--step` / `--attach`、exit code、stderr，以及 `--help` 的穩定介面。
- 新增 read-only `verify_bug_reports.py`：驗證 schema、checksum、artifact hash、ledger 唯一性與 capture state；不得更正資料。
- 在 skill 中固定 postflight：確認 receipt、讀取 `reproduction.md`、執行 verifier；失敗時停止調查並回報 recovery 所需資訊。

驗收：skill instructions、CLI `--help` 與 contract tests 同步；未知參數、缺漏 intake 或 verifier failure 都 fail closed。

實作結果：capture 與 verifier 均提供 `--format json`，receipt 含 Bug ID、相對 artifact／ledger 路徑、schema、附件數、diff privacy flag、digest 與 validation 結果；skill 固定讀取 receipt 後再進入調查。

## Milestone 4 — Append-only investigation and closure（P1，已完成）

目的：保留初始事實，同時讓已修復 bug 可追到修正與驗證。

- 新增唯一 append CLI，寫入不可改寫的 resolution evidence：Bug ID、結果類型、診斷摘要、修正 commit / PR（若有）、回歸測試、validation command 與結果、記錄時間。
- 支援 `fixed_verified`、`duplicate`、`cannot_reproduce`、`wont_fix`；每種結果都必填可審核理由與證據。
- resolution 不得覆寫 `report.yaml`、`snapshot.json` 或 `reproduction.md`；ledger status 是由 append-only evidence 衍生，而非人工改寫。
- 新增 lifecycle verifier：禁止沒有初始 report 的結案、禁止同一 resolution ID 重複、禁止將未驗證的修正標成 verified。

驗收：任一結案 Bug 可從 ledger 追至原始 capture、後續 evidence、修正引用與驗證輸出；初始 report checksum 維持不變。

實作結果：`tools/resolve_bug_report.py` 只會在 `resolutions/RES-*.yaml` 新增 closure evidence；`fixed_verified` 強制 fix reference 與 validation evidence，ledger 狀態由最近的 resolution 衍生，verifier 會拒絕不一致狀態或篡改的初始 digest。

## Milestone 5 — Skill decision quality and forward tests（P2，已完成）

目的：讓 skill 在真實對話中穩定做出「capture / 不 capture / 補問」決定。

- 將 `SKILL.md` 精簡成低自由度的 scope gate、最小 intake、CLI call、postflight 與禁止事項；細節保留在 reference。
- 為四種情境建立 prompt-level contract fixtures：完整正常使用 defect、不完整 defect、開發期測試失敗、刻意 fail-closed capability gap。
- 驗證完整 defect 會先 capture；不完整 defect 只補問；其餘三類不建立 Bug ID。
- 每次 skill 實質更新後，跑 skill validator、CLI contract tests 與至少一組無洩漏上下文的 forward test。

驗收：skill 不會直接修 bug、虛構重現步驟、或將開發期問題錯登為 learner bug。

實作結果：skill 已固定 scope gate、JSON postflight、recovery 與 append-only closure 指示，並有契約測試鎖定 creation-before-fix 的界線；四種 prompt-level decision fixture 已涵蓋完整 defect capture、不完整 intake 補問、開發期測試失敗與 intentional fail-closed capability gap。

## Milestone 6 — Operational review surface（P3，已完成）

目的：讓 roadmap ledger 保持簡短，但可讀取目前 bug 品質與處理狀態。

- 建立 read-only derived bug index：按 status、affected flow、reproducibility 與 artifact completeness 匯總。
- 僅連結 Bug ID 與摘要；不複製 screenshot、log、learner transcript 或敏感附件內容。
- 提供 stale / incomplete 提示，不能自動改狀態或建立新 evidence。

驗收：使用者可辨識哪些 report 尚缺結案證據；所有統計可從 artifacts 與 ledger 重建。

實作結果：`tools/rebuild_bug_report_index.py` 會產生 `tracker/bug-reports/index.yaml`，彙整 status、affected flow、reproducibility 與 artifact completeness，不複製原始證據內容。

## 交付順序與停止條件

```text
M1 transaction / recovery
    ↓
M2 privacy enforcement
    ↓
M3 receipt + verifier
    ↓
M4 append-only closure
    ↓
M5 skill forward tests
    ↓
M6 derived operational index
```

- M1 和 M2 必須先完成，才允許擴大正常使用範圍；它們保護 evidence 的完整性與隱私。
- M3 是 skill 呼叫其他 CLI 的可複用模式，不在本專案中建立通用 registry；只有驗證其必要性後才另立專案。
- M4 以前，Bug Capture 只可建立 `reported`，不得手動把 roadmap row 改為 resolved。
- 沒有真實 defect 的完整 intake 時，不用 Bug Capture 來「測試」workflow；使用匿名 fixture。

## Definition of Done

此 roadmap 完成時，`bug-capture` skill 能在正常使用 defect 發生後、修復前，以單一 CLI 建立具備完整性、隱私控制、可復原性與可驗證 receipt 的初始證據；修復完成後以 append-only evidence 結案。任何資料不足、scope 不符或安全風險都會在寫入前 fail closed。
