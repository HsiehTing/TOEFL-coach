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

## Learner request — 修訂完成後的自然度與精確度回饋（2026-08-11）

Learner 明確要求：在每一輪 Writing revision 中，當必要的題目要點已清楚、且可維持或提升 simulated task score 時，coach 要進一步精修文意是否通順、語句是否自然、字詞是否精確，以及文法用法是否道地。此輪的回饋焦點不應完全放在論點表達或邏輯展開；只有它們阻礙題意、讀者理解或分數上限時，才優先處理。

### 使用者結果

每次完成一輪修訂評估後，coach 先完成既有的分數與修訂比對，再在不重複第一輪錯誤表、不把可選潤飾混入錯誤率的前提下，提供一個簡短的「高分精修：自然度、文意與精確度 follow-up」：

- 最多三則 exact-excerpt 建議，優先處理同一封回應中重複的意思／句型、文意或指涉不夠順暢、字義過泛或不精確的字詞，以及雖可理解但不符合自然英文慣用法的句型或文法結構。
- 每則建議說明其對讀者造成的效果，並提供一個保留 learner 原意的單句改寫選項；不得把選項串成完整範文。
- Follow-up 只提供精修建議，不出題、不要求 learner 交回改寫，也不提供答案；任何 learner 作答練習只屬於其明確同意的 targeted drill。
- 若沒有足夠的高分精修問題，明確說明「沒有可指出的語句自然度、文意或精確度問題」，不為了湊數而製造問題。

此 follow-up 是 revision completion 的 coaching artifact，不是 `targeted_drill`：它不產生 task score、不增加 formal count、不寫入 counted error event、不改變 error rate、historical status、mastery 或 transfer gate。正式 targeted drill 仍只由 training plan 的有來源 recommendation 產生。

### 觸發與邊界

- 適用於 Email 與 Academic Discussion 的 revision output；至少先完成「resolved／partly resolved／unresolved／newly introduced」的既有修訂比對。
- 只在 learner 已提交修訂後顯示，因此可使用 learner 已修改過的句子提供 clearer options；第一輪回饋的「不提供完整範文」與最多三個改善目標規則維持不變。
- 每個建議都必須引用實際 learner excerpt；重複可跨段落判定，但不得臆測 learner 未寫出的意思。
- 「重複」是同一交際功能或意思在短距離內以近似表達再次出現，不是合理的關鍵詞重複，也不是單純出現相同冠詞或介系詞。
- 「不精確」需說明為何不精確（例如原因、行動者、時段或影響不明），而非只以更艱深的詞彙取代。
- 當 prompt points、立場與基本因果關係已足以支持目前或更高的 score 時，follow-up 預設優先順序為：語句通順／文意 → 自然句型與文法用法 → 字詞精確度 → 避免不必要重複；不額外要求擴寫論點或重做邏輯。
- 若論點或邏輯確實會使讀者無法理解問題、方案或請求，coach 必須說明這是高分精修以外的 task-completion blocker，並回到既有 must-fix／should-fix 流程處理。
- Targeted drill 的練習題必須沿用 learner 的 task route 與原始情境；不得把 Email 練習變成 Discussion 題目，亦不得假裝為 ETS 題目或正式分數。

### 驗收條件

1. 一篇完成修訂的 Email 若重複使用 `Students urgently need...`，follow-up 能引用兩個 exact excerpts，說明重複的語用效果，並提供一個保留 urgency 的單句替代方案。
2. 不自然但可理解的搭配（例如過泛的 `is from the construction`）能得到一個更精確的單句選項與原因；不會被寫成 counted error，除非它同時符合既有 must-fix／should-fix 標準。
3. 一篇論點、邏輯與 prompt points 均已清楚的回應，follow-up 仍會優先找出語句通順、指涉、自然用法或精確字詞問題，而不是要求多加一個論點。
4. follow-up 只提供 excerpt-based 精修建議；不得產生 mini-practice、改寫題或其他 learner 作答要求。
5. 沒有重複、文意、自然度或精確度問題的完成修訂，輸出明確的零項結果與不計分的 transfer suggestion，而非虛構 feedback。
6. 回歸測試確認此流程不改寫 immutable attempt、feedback、event，且不改變 dashboard、error rate、mastery、training plan 或 practice queue。

### 實作進度（2026-08-11）

已完成：

- revision feedback 可在既有六個評估區塊後附加 `# Naturalness and precision follow-up`；此區塊只保存於 immutable feedback，不會寫入 event 或衍生學習狀態。
- 有問題時，gate 會要求 1–3 則 response 中的 distinct exact excerpts；零項結果可明確寫出固定的 no-issue 訊息。
- Writing coach skill 已規定用字重複、語意不精確或慣用法不自然的界線，以及保持 route/context 的限制；契約測試會拒絕臆測 excerpt 與任何 follow-up 內的練習題。

## Learner clarification — Writing revision → conditional drill → mandatory follow-up（2026-08-12）

此流程取代「每一輪 revision 都直接附上 follow-up」的舊順序。Writing coaching 必須依序通過三個階段：修訂目標、learner-directed targeted drill、自然度與精確度 follow-up。Follow-up 是完成修訂流程後的必觸發階段；drill 只在流程進入第三輪修訂前提出，並由 learner 決定是否開始。

### 階段與閘門

| 階段 | 觸發條件 | 必要輸出／動作 | 下一步 |
| --- | --- | --- | --- |
| 1. 修訂目標 | learner 提交 revision | 比對 assigned priorities，列出 `resolved`、`partly_resolved`、`unresolved`、`newly introduced` 與 resolution rate | 目標未完成時繼續 revision gate；全部完成時檢查 drill gate |
| 2. Targeted drill gate | 第二輪 revision 後仍有未完成目標，原流程將要求第三輪 revision | 先以 exact excerpt 提供針對 learner 產出的建議與 bounded rewrite direction，再詢問是否要開始 drill；只有 learner 同意才列出來源、target codes、有限題數與完成條件 | 同意後完成 drill，再回到必要的 revision 驗證；拒絕時記錄 `declined`，進入 follow-up 並結束該 revision chain |
| 2a. Drill skipped | learner 在需要第三輪 revision 之前已完成全部修訂目標 | 明確標示 drill 為 `skipped`，原因為「未觸發第三輪修訂」；不得為了完成流程而強迫產生或作答 drill | 直接進入 follow-up |
| 3. Naturalness and precision follow-up | 所有修訂目標已完成，且任何 opted-in drill 也已完成；或 learner 在 R2 後明確拒絕 drill | 必須輸出 actionable follow-up；依既有契約提供 1–3 則未處理過的 exact-excerpt 精修建議，不出題 | 只有完整完成的 revision chain 才可建議 new-prompt transfer；`declined` 結束該 chain，不開 transfer |

### Skill 修改模式

- 將 `toefl-writing-coach` 的 revision workflow 改為明確 state machine：`revision_targets → drill_gate → follow_up → transfer`，不得只靠段落順序或 coach 自由判斷跳階段。
- 每次 revision feedback 都要計算目前 revision round。只有「第二輪 revision 後仍未完成、下一步原本會進入第三輪」才詢問 learner 是否要做 drill；learner 同意時設為 `required`，拒絕時設為 `declined`；第一輪或第二輪已完成時設為 `skipped`。
- Learner 選擇的 `required` drill 必須交由 `writing-drill-lifecycle` 產生、評量與登錄，沿用來源 route、target codes、有限 item count、answer-key 隔離與 immutable lineage 契約；follow-up 不得產生額外練習。
- Drill 不是每條 revision lineage 的強制產物。未觸發第三輪 revision 時，不要求 learner 先完成 drill，也不得因缺少 drill record 阻塞 follow-up。
- Follow-up 是完成閘門，不是可選潤飾。只要修訂目標已完成，且 learner 選擇的 drill 已完成或合法 skipped，就必須執行 follow-up；R2 未完成但 learner 明確拒絕 drill 時也必須執行 follow-up，並結束該 chain。其他未滿足條件時不得提前顯示 follow-up。
- `No naturalness or precision issue to flag.` 只能在完成真實的自然度／精確度檢查且確實沒有可操作問題時使用；不得把它當成跳過 follow-up 的捷徑。存在 genuine issue 時必須提供 actionable follow-up。
- Follow-up 不重複 scored evidence、parent feedback、targeted drill 或已完成 priority；它只提供建議，不得含 mini-practice、改寫題或其他 learner 作答要求；不建立 counted events、不改變 task score、formal count、error rate、historical status、mastery 或 transfer gate。
- Transfer 只能出現在 follow-up 之後；不得由「修訂目標完成」或「drill 完成」直接跳到 transfer。

### 狀態範例

```text
R1 全部完成 → drill: skipped → follow-up: required → transfer suggestion

R1 未完成 → R2 全部完成 → drill: skipped → follow-up: required → transfer suggestion

R1 未完成 → R2 仍未完成 → 詢問 drill
    → learner 同意 → drill: required → 完成 drill → 完成必要 revision 驗證 → follow-up: required → transfer suggestion
    → learner 拒絕 → drill: declined → follow-up: required → chain ends
```

### 驗收條件

1. R1 或 R2 已解決全部 assigned priorities 時，輸出明確顯示 `drill: skipped`，並在同次完成流程中提供 actionable follow-up。
2. R2 後仍有 unresolved 或 partly resolved priority 時，先輸出 learner 可選的 drill invitation；learner 同意才生成 required drill，拒絕則記錄 `declined` 並進入 follow-up。
3. Required drill 完成後仍須確認修訂目標已完成；drill 結果不能自動冒充 revision resolution。
4. 所有修訂目標完成且 drill 為 completed 或合法 skipped 時，follow-up 必須出現；若 learner 拒絕 drill，也必須提供 follow-up，但不得開 transfer 或第三輪 revision。若 response 尚有 genuine naturalness／precision issue，零項訊息必須被拒絕。
5. Follow-up 之前不得產生 new-prompt transfer suggestion；follow-up 完成後才開放 transfer。
6. 回歸測試至少涵蓋四條路徑：R1 完成、R2 完成、R2 未完成而 learner 選擇 required drill、R2 未完成而 learner 拒絕 drill；並確認每條路徑都只有在合法閘門後進入 follow-up。

### 實作進度（2026-08-12）

已完成：

- Writing registration gate 會依 persisted revision lineage 計算輪次，強制 `not_required_yet`、`skipped`、`required`、`declined`、`completed` 五種 drill 狀態，並在發布鎖內重驗。
- R1／R2 完成目標時合法略過 drill 並強制 follow-up；R2 未完成時先詢問 learner，僅在同意後要求列出 source、1–2 個 lineage target codes、1–8 題與完成條件；拒絕時須保留 learner decision、提供 follow-up 並結束 chain。
- 未存在 R2 後登錄、回連同一 formal root 的 targeted drill 時，第三輪 revision 會 fail closed；drill 完成後仍需獨立驗證 revision targets，不能以 drill 結果自動標為 resolved。
- 完成 revision 的 follow-up 為必要 heading；零項結果必須附 1–3 個實際 learner excerpt 的 naturalness audit 與 transfer suggestion，不能只輸出固定句跳過檢查。
- Writing coach skill 與 UI default prompt 已同步此 state machine；獨立 forward test 確認 R2 未完成時可等待 learner 選擇，或在明確拒絕後合法提供 follow-up 而不開 transfer。
- 回歸測試涵蓋 R1 完成、R2 完成、R2 未完成 required drill、R2 未完成 declined drill、缺 drill 的 R3 被拒絕、完成 drill 後的 R3、未完成時禁止 follow-up，以及 no-issue audit gate。
- Learner-like 端到端測試使用政府免費職訓情境，實際走 dedicated registration 的 `formal → R1 未完成 → R2 完成`：R1 保存 `drill: not_required_yet` 且沒有 follow-up；R2 保存 `drill: skipped`，其後緊接 actionable follow-up，formal count 維持 1。

## Learner clarification — Constructive revision explanations（2026-08-13）

縮減版 revision feedback 仍必須教會 learner 如何遷移，而不只標示對錯。每個未完成的既定 priority 要先承認原句中可接受的意圖或結構，再指出唯一最有價值的調整與其讀者效果。最多兩個高槓桿項目可以採 `Keep → Adjust → Direction` 的緊湊比較：保留的意思、要改的精確結構／詞語、可重複使用的句級方向或有限改寫選項。

- 必須區分 hard error 與 acceptable-but-less-natural choice；不可把可理解的句子誤報為嚴重文法錯誤。
- 說明要具體到可遷移的機制，例如 parallelism、redundancy、reference、collocation、specificity 或 cause-and-effect；不可只以「更自然」作結論。
- 不要求每個 issue 都附詳細講解，也不得把解釋擴張成完整範文、新 priority 或同輪 drill target。
- Academic Discussion 已加入對 `able to` 後的平行動詞、語義重複、對比中的名詞重複、主動限制與被動受限等常見句級問題的說明方向。

## Incident-driven optimization requirements（2026-08-10）

本節將 `W-AD-20260809-002` 的 drill 產出問題轉成 Milestone 1 的必要開發需求。原始失敗案例為：Academic Discussion 的品牌行銷／世界盃題目，卻產生公共運輸、大學政策與新設施題目；同一 pack 含多組重複題；recommendation 要求 causal-chain items，輸出卻是無關的通用文法模板；並將 causal chain 的四個語意元素誤呈現為每題四個完整句子的硬性要求。

### 使用者流程複核與狀態（2026-08-10）

複核順序為：training plan → 產生 learner drill → 填答／讀取 → drill 結果 → transfer → mastery／下一步 queue。以下狀態以目前工作區與實際命令輸出為準，而非只看單元測試。

| 流程節點 | 狀態 | 結論 |
| --- | --- | --- |
| 從未解決 revision 產生 training plan | 可用 | 可產生有來源、route 與目標 code 的 recommendation。 |
| 新 pack 的答案隔離 | 已修復 | 目前 `build_drill_pack()` 的 learner markdown 不含 answer key；answer key 保持獨立。 |
| 重新產生既有 recommendation | 已修復 | renderer／schema version 已納入 pack identity；現行 `PLAN-W-AD-20260809-002` 會產生 v11 的新 ID `WD-E3B7138B89BE6A83`，不覆寫 legacy `WD-90608621535FD7B6`。 |
| 新生成題目的情境與獨立性 | 已修復（支援情境） | 產生前會檢查 context binding 與正規化後的 prompt 唯一性；沒有對應安全模板的情境直接拒絕產生。 |
| 作答完整性讀取 | 可用 | 讀取器會拒絕遺漏的 response field。 |
| 開放題評量與 drill 統計 | 已修復（教練判定） | 每題保存 `meets_target`／`partially_meets_target`／`needs_revision` 與理由；各 target code 另保存題數與達標摘要。語意與語言正確性仍由教練判定。 |
| transfer 前置條件 | 已修復 | transfer 會逐一檢查每個 target code 的最低正確率；未達標的 code 無法進入新題 transfer。 |
| 多個 plan 的下一步呈現 | 已修復 | queue 列出所有 active plan，並標示 `ready`、`deferred_by_priority` 或具體阻塞原因。 |

歷史 artifact 要與現行功能分開處理：已存的 `WD-90608621535FD7B6/drill.md` 含示範答案，這是需要隔離或遷移的舊資料問題，不代表新的 learner renderer 仍會洩漏答案。現有測試與 tracker audit 通過只能證明其既有契約；本節的流程案例必須成為新的回歸契約。

### P0 lifecycle repair 實作進度（2026-08-10）

已完成：

- pack format 升級至 version 11；renderer／schema 更新會產生新的 stable drill ID，不覆寫舊 pack。
- 舊版或 learner artifact 含非 response 內容時，`read_completed_drill()` 會拒絕註冊。
- transfer 會檢查 persisted drill 的最低正確率；未達門檻不能進入新題 transfer。
- practice queue 會輸出 `ready`、`blocked_by_drill`、`blocked_by_accuracy`、`blocked_by_pack_drift`、`blocked_by_template` 等狀態與原因；目前工作區的舊 5-code drill 因與最新 2-code plan 不一致而顯示 `blocked_by_pack_drift`。
- 回歸測試已涵蓋 version collision、legacy pack、答案混入、低正確率 transfer 與 unsupported target 狀態。
- source prompt 現為 drill 的必要 context evidence；Academic Discussion pack 會保存 context summary 與 prompt hash，且無法辨識主題時 fail closed。品牌行銷案例已確認不再生成公共運輸／大學設施題目。
- drill 現可保存每題 `meets_target`、`partially_meets_target`、`needs_revision` 與判定理由；`correct_count` 必須與實際達標題數一致，mastery 會另外顯示部分達標題數。
- practice queue 現會列出所有 active training plan；目前最高優先項以外的 plan 明確標示 `deferred_by_priority`，並保留 template／accuracy／pack drift 等阻塞原因。
- causal-chain drill 已改為每題單一、明示 25–35 字的句子作答；主張、機制、具體結果與回扣立場是同一句的語意條件，不再是四個完整句子的欄位。
- 獨立 answer key 現會列出每題短示範答案與 `Acceptable when` 判定條件；learner drill 仍不含示範答案。
- 每個新 pack 會產生 `assessment.json` 逐題評量模板；registration 預設讀取它並驗證題號、狀態與 `correct_count` 的一致性。
- `validate_drill_pack()` 現在是 build 與 write 的必經品質閘門：驗證 context/template family、每題 evidence、response field、正規化 prompt 唯一性、learner／answer-key renderer 一致性，以及 learner artifact 不含示範答案或判定條件。模板池不足時會在落檔前失敗，而不是複製題目補足數量。
- source context 現採 fail-closed template family：已支援品牌識別的 Academic Discussion，以及校園設施、職涯選擇建議、印錯文件更正的 Email；其他來源題目會明確要求先補對應模板，不再挪用不相關的固定情境。
- Email 已新增「職涯選擇建議」與「印錯文件的緊急更正」兩個 context-safe template family；題目、示範答案與可接受條件均留在原始任務情境，並有回歸測試避免混入校園設施內容。
- 以 `W-AD-20260812-003` 的真實來源新增「專題式學習、實務技能與職場準備」Academic Discussion template family；以 `W-EM-20260812-001` 的真實來源新增「瑕疵教材與緊急換貨」Email template family。兩者只在明確辨識到該題型時啟用，其他未知情境維持 fail closed。
- 新完成的 generated drill 在成功登錄後，會把最低門檻、來源 prompt hash 與 renderer version 轉存到標記為 `result_only` 的 targeted drill metadata，隨即刪除該 `drill-packs/WD-...` 下的 learner drill、answer key 與 assessment artifact，以及 targeted drill attempt 內的 prompt／learner response。transfer 改讀這份已登錄的最小 lineage；audit 會拒絕 result-only record 殘留的 learner content 或 item events。既有歷史 pack 與 drill attempt 不會被自動刪除。
- practice queue 現在會在顯示「可生成 drill」前讀取來源 prompt；若缺少對應的 context-safe template，會直接標示 `blocked_by_template` 與具體原因，而不是先把使用者帶到失敗的生成步驟。
- practice queue 也會讀取最新未完成 R2 的 learner decision：沒有明確 opt-in 時顯示 `awaiting_learner_choice` 並只要求 coach 提問；明確 `declined` 時顯示 `closed_by_learner_choice`，不產生 drill、transfer 或第三次修訂。舊 feedback 不會被倒改成同意。
- 新登錄的 `required` R2 feedback 必須保存 `Decision: learner opted in ...`；少了這個明確決定會 fail closed。已 `declined` 的 plan 仍顯示結案原因，但不再佔用 queue 的目前優先順位，下一個未結案 plan 可成為可執行動作。
- 新登錄的 `required`／`declined` R2 feedback 也必須保存固定的 `Invitation` 紀錄，明示選擇是在 exact-excerpt feedback 與 bounded rewrite direction 之後才提出；這不能只靠 coach 文字規範。缺少 invitation 會 fail closed，避免只留下 drill 狀態而沒有針對 learner 實際產出的前置建議。
- `review_writing_drill.py` 可對完成但尚未登錄的 drill 產生一次性的 `assessment-hints.json`：檢查句尾、句數、字數與 causal-chain 的 25–35 字／單句規則。輸出固定為 `diagnostic_only`，不會自行決定 `meets_target`，仍由教練完成語意與語言正確性判定。
- 每個 drill item 現明確保存 `response_mode`；目前所有產生題皆為 `open_response`，評量輔助也會輸出此標記，禁止將示範答案當成唯一正解。未來若加入封閉題，必須明確標為 `closed_response` 才能使用唯一答案比對。
- `review_writing_drill.py` 現會額外建立一次性的 `assessment-review.md` 給教練審核：逐題集中 learner response、target code、來源 evidence ID、接受條件與格式提示，並明確要求由教練寫入語意／語言判定；不會產生自動對錯結論，成功登錄後會隨 drill pack 清除。
- 多 code drill 現保證每個 target code 至少有一題，登錄時保存各 code 的 item／達標／部分達標數；transfer、queue 與 mastery 會逐一檢查每個 code 的門檻，不能以總分掩蓋單一弱點未達標。

尚未完成：

- 開放題的語意與語言正確性判定仍由教練提供；目前已新增一次性的 coach assessment worksheet，集中 learner response、來源 evidence ID、接受條件與格式提示，但不會自動判為正確或錯誤；登錄後會隨 pack 清理。
- 只有出現新的真實來源題目情境時，才補上相應的 context-safe template family（例如期限調整）；不預先堆疊可重複練習的題庫或生成 artifact。

### 需求 DRILL-RETENTION-11：一次性 drill artifact 清理

- Drill 題目、answer key 與逐題評量檔是當次訓練介面，不是可重複使用的題庫；完成且成功登錄後不得繼續保留在 `tracker/writing/drill-packs/`。
- 登錄後必須保留最小 transfer lineage：drill ID、來源 attempt、target codes、item / correct count、最低門檻、來源 prompt hash、renderer version 與逐題評量結果。
- `prepare_transfer_attempt()` 必須只依賴已登錄的最小 lineage，不得需要已刪除的 learner drill 或 answer key。
- 清理只能發生在 targeted drill attempt 已成功寫入後；註冊失敗或尚未完成評量時，原始 pack 必須保留以便續作。
- 新的 result-only targeted drill 不保存 prompt、learner response 或 item event；其 `source_hash` 僅作為當次已完成內容的不可逆識別，audit 不會嘗試從已刪除內容重新計算它。
- 既有歷史 pack 不做自動刪除；只對採用此 retention contract 的新完成 drill 生效。若需要清理歷史資料，另行提供明確、可預覽的 migration 指令。

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
- 僅當 learner 在正常使用 coach 時回報非預期行為，才使用 `tools/capture_bug_report.py` 建立不可覆寫的 Bug Capture；開發中的 feature work、測試失敗、roadmap 整理與 intentionally fail-closed 的 capability gap 不建立 Bug Capture。
- 正常使用 bug 不得直接修改：先確認目的／預期結果／實際結果／操作流程／使用時機與觸發條件／影響範圍／可用證據；資訊不足時先追問，不得臆測。
- 確認後先以 capture CLI 把 Bug ID、確認過的摘要與 artifact 連結寫入本 roadmap，再開始調查或修復；完整 context、snapshot 與附件放在 artifact，避免 roadmap 取代可重現證據。

## Bug capture ledger

僅記錄正常使用 coach 時發現的 bug。每筆回報至少保存：功能目的、預期／實際結果、錯誤前的操作步驟、時機或觸發條件、受影響流程、重現性與影響範圍、Git revision 與工作區狀態、runtime 資訊，以及使用者提供的 log、畫面或輸出附件及其 checksum。預設不保存完整未提交 diff，避免把無關變更或敏感內容納入證據；若當次重現確實需要，才由呼叫者明確加上 `--include-git-diff`。完整證據存於 `tracker/bug-reports/<BUG-ID>/`，而不是把 snapshot 複製進 roadmap。

| Bug ID | Status | Summary | Evidence | Artifact |
| --- | --- | --- | --- |
<!-- BUG-CAPTURE-LEDGER -->
| `BUG-20260812-005` | reported | Required drill begins without learner choice or causal-chain guidance | [reproduction](tracker/bug-reports/BUG-20260812-005/reproduction.md) | `v1` `sha256:45137d0a8c569781fec2bf044ccf1c0ef76ae994b151a3d14ec3df21bd8c68bf` |

| `BUG-20260812-004` | reported | Revision feedback mixes newly found issues with prior target tracking | [reproduction](tracker/bug-reports/BUG-20260812-004/reproduction.md) | `v1` `sha256:10c171de59e5a9d4e0f14698eef48571602cf7ab4147ae630d64c13750bfa860` |

| `BUG-20260812-003` | reported | Targeted drill generation rejects education discussion prompt | [reproduction](tracker/bug-reports/BUG-20260812-003/reproduction.md) | `v1` `sha256:abb66306450edddfd400e2fd2056bca69d740a9d32a9f99fe79f1e5a6989848f` |

| `BUG-20260813-001` | reported | Naturalness follow-up did not provide a concrete next follow-up | [reproduction](tracker/bug-reports/BUG-20260813-001/reproduction.md) | `v1` `sha256:d85ad6d0ba31e0f37062f9ebd18948dd04648c14ebe65460f4c244b561859fb3` |
| `BUG-20260812-002` | reported | Completed writing revision skips mandatory actionable follow-up | [reproduction](tracker/bug-reports/BUG-20260812-002/reproduction.md) | `v1` `sha256:5c385393e2f072c3dbe9ed1a65af2d751e850adc8ded629901858d4e5dd75186` |

| `BUG-20260812-001` | fixed_verified | Revision follow-up repeats prior scored advice instead of advancing toward score 5 | [reproduction](tracker/bug-reports/BUG-20260812-001/reproduction.md) | `v1` `sha256:912c8e0a35ded5dbe4ae0ff7de00f3e9da6df43c85ba7410a1fec5b8fd3ee0a4` |



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

### 實作進度（2026-08-11）

已完成：

- overview 同時輸出 Markdown 與 YAML；重建不改寫 attempt 或 canonical event。
- 最近三篇正式作答顯示 route、模擬 task score、錯誤密度與 meaning-changing 密度；資料不足三篇時維持 diagnostic-only early view。
- 各 route 分開列出 atomic code 的 historical trend signal 與 skill-family evidence 統計，不混用 route-specific code。
- 每條 revision chain 顯示輪數、最新解決率、最新／累計新增錯誤，以及首次完全解決輪次。
- 每個 mastery code 顯示 drill sets、逐 code drill accuracy、部分達標題數、transfer opportunities／errors，並分開列出 drill 與 transfer attempt evidence。
- 已重建 `tracker/writing/progress-overview.md` 與 `.yaml`，並有回歸測試防止資訊遺漏。

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

### 實作進度（2026-08-11）

已完成：

- Email 與 Academic Discussion 各有兩個固定、匿名化校準樣本，涵蓋不同的模擬 task-score 水準與診斷重點。
- 每個樣本鎖定 route、attempt ID、rubric version、核准 score range、全部 counted error codes，以及 `Why this level`／`Why not the next level` 的關鍵理由標記。
- `validate_writing_calibration.py` 會 fail closed 偵測 score、route、rubric version、分類 code、exact excerpt 或關鍵理由漂移。
- 既有 schema-v2 `re_evaluation` 測試持續驗證新版 rubric 評估只會新增 lineage，不覆寫原始評估。

## Milestone 5 — Speaking Progress Parity

優先度：P2

在 Writing 閉環穩定後，將相同概念延伸到 Listen and Repeat 與 Take an Interview，但保留 speaking-specific evidence：learner timestamp、角色確認、音訊可靠維度與 `diagnostic_only` 邊界。

### 第一階段實作進度（2026-08-11）

已完成：

- 新增 `tracker/speaking/progress-overview.md`／`.yaml` 與 `tools/rebuild_speaking_progress_overview.py`；正式 session 顯示 task route、duration、timestamp-based counted events、role mapping 確認與 persisted reliable dimensions。
- Listen and Repeat 與 Take an Interview 的 atomic code、taxonomy dimension、recent focus 分開統計；至少三個 formal session 前不選擇進度 focus。
- 每次 `register_speaking_session.py` 成功後會重建 speaking aggregate events、dashboard、三次 session reports 與 progress overview。
- overview 固定標示 `diagnostic_only`：未被 persisted audio inspection 標為可靠的 pronunciation、prosody、fluency 與 intelligibility 不會從 transcript 推測，且絕不換算 section band。

已完成（audio-performance evidence contract）：

- 錄音品質的 `all` 僅表示訊號完整，不再自動授權 pronunciation、prosody、fluency 或 intelligibility 判定。
- 若要登錄這些 audio-performance code，必須為每個 learner segment 保存 timestamp-aligned、path-free 的 `human_observed` dimension observation，含觀察時間、對應 dimension 與簡短證據理由；所有 learner segment 的交集才成為 reliable dimension。
- 未提供該證據時維持 fail closed；不從逐字稿或正常音量推測音訊表現。

### 已核准、實作中：Speaking revision、drill 與 transfer contract

目標是讓 learner 可用新的、有限範圍的口說練習檢查改善是否遷移；它只產生 diagnostic evidence，不產生 TOEFL task score 或 section band，也不把逐字稿當成完整音訊評分。

| 階段 | 允許的輸入與產物 | 必要 evidence | 禁止事項 |
| --- | --- | --- | --- |
| Revision / re-recording | 連到一個完整 formal session 的 partial 或 complete re-recording transcript | parent session、指定 item／priority、learner transcript、明確 prompt/learner pairing；若評語涉及音訊維度，該 learner segment 必須有對應 reliable dimension | 不把 partial re-recording 計為新的 formal session；不補寫未提供的字詞或時間戳。 |
| Targeted drill | 一次性的 mini set：Listen and Repeat 為新句子／受限的 reconstruction target；Interview 為新問題／受限的 response goal | source event IDs、target code、route、item IDs、learner transcript、逐項 `meets_target`／`partially_meets_target`／`needs_revision` 與理由 | 不重複舊題作為 transfer；不保存 raw audio；不以示範答案作唯一正解。 |
| Transfer | 與來源 formal session 不同的新 stimulus：Listen and Repeat 不重用原句；Interview 不重用原問題 | completed drill、每個 target code 的門檻、new prompt hash、逐 code opportunity、timestamp／transcript evidence | target code 未逐一達標時不可 transfer；audio-unreliable dimension 不可被宣告已 transfer。 |
| Progress state | 每個 code 只顯示 `identified`、`practised`、`transcript_transferred` 或 `audio_evidence_unavailable` 等 diagnostic state | drill／transfer evidence IDs，及每個 evidence 的 reliable dimensions | 不宣告完整 spoken control；不把文字成功擴大為 pronunciation、prosody、fluency 或 intelligibility 成功。 |

共通資料與門檻：

- 每筆 revision、drill 與 transfer 必須保留 route、source formal session、target code、item／segment ID、learner timestamp（若原始證據含 timestamp）及 reason；不得只保存整組分數。
- `SPK-PRONUNCIATION`、`SPK-STRESS`、`SPK-RHYTHM`、`SPK-INTONATION`、`SPK-FLUENCY`、`SPK-INTELLIGIBILITY` 只有在每個關聯 learner segment 的 persisted inspection 把該維度列為 reliable 時，才可被評為達標或 transfer；否則 state 必須是 `audio_evidence_unavailable`。
- transcript-supported code（Listen and Repeat 的 reconstruction、兩種任務的 grammar／vocabulary；Interview 的 directness／relevance／elaboration／coherence）仍須由 learner 提供完整、角色明確的 transcript；沒有 opportunity 不能提升狀態。
- generated drill prompt、示範答案與審核模板是一次性訓練介面。成功登錄後只保留最小 result lineage，不保留可重複練習的 prompt／answer key／learner transcript；historical formal session 不自動清理。
- schema、CLI、與資料 migration 必須在本 contract 核准後才實作；第一個實作切點是 transcript-supported code，audio-performance code 保持 fail closed。

第一個實作切片（完成）：`speaking_practice.validate_transcript_drill()` 與 `tools/validate_speaking_drill.py` 會先鎖定 transcript-supported target codes、逐題狀態與每個 code 的練習覆蓋。`tools/register_speaking_drill.py` 只登錄不可變的 result lineage（來源 formal session、逐題／逐 code 結果及 result hash），不保留 prompt、answer key 或 learner transcript。所有 audio-performance codes 仍明確拒絕。

第二個實作切片（完成）：`speaking_transfer.prepare_speaking_transfer_attempt()` 與 `register_speaking_session.py --transfer-drill --confirmed-opportunities` 已強制 Speaking transfer 必須連到逐 code 達門檻的 drill、使用不同於來源 session 的新 prompt，並讓每個 target code 在新的 formal session 都有正數的確認 opportunity。transfer 仍只產生 diagnostic evidence，且 audio-performance 維度在有獨立 audio contract 前維持 fail closed。

第三個實作切片（完成）：Speaking progress overview 現在會按 route、target code 顯示 result lineage：`needs_drill_revision`、`ready_for_transfer`、`awaiting_coach_outcome` 或 transcript-supported 的 `transfer_outcome_*`，並連回 drill／transfer attempt ID 與最近一次 per-code 門檻結果。這是追蹤狀態，不是 TOEFL task score、section band、mastery 宣告或 audio-performance 判斷。

第四個實作切片（完成）：端對端測試已覆蓋 formal source session → result-only drill（無 prompt／transcript）→ 新 prompt 的 formal transfer → 含 exact transcript excerpt 的 per-code outcome → overview lineage，且 Speaking audit 通過。不可用「沒有新增 error event」直接推論已 mastered。

第五個實作切片（完成）：`speaking_revision.validate_transcript_rerecording()` 與 `tools/validate_speaking_rerecording.py` 先鎖定 partial／complete scope、parent session、source event、item prompt/learner pairing、逐 code outcome 與 exact transcript excerpt。`tools/register_speaking_rerecording.py` 會將通過預檢的 payload 寫成不可變 Speaking revision record，保留 transcript 與 pairing，但不產生 audio artifact、也不增加 formal session。audit 會核對 parent formal session、source event coverage 與保存的 re-recording payload。它拒絕 audio-performance code，避免逐字稿被誤用為發音或流暢度判定。

第六個實作切片（完成）：Speaking progress overview 會按 route 顯示每筆 re-recording 的 parent、partial／complete scope 與逐 code transcript-supported outcome，並明確排除在 formal session 計數之外；它不產生 TOEFL task score、section band 或 audio-performance 結果。

下一個切入點：回到主 roadmap 的下一個未完成 learner-facing 或資料品質項目；Speaking revision、drill 與 transfer 的 transcript-supported 閉環已可安全使用，audio-performance 維度仍維持獨立 fail-closed。

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

目前已完成 Writing naturalness follow-up、Bug Capture P0–P3，以及 Speaking 的 transcript-supported revision、targeted drill、result-only retention、new-session transfer、progress lineage 和 audio-performance evidence contract。下一個切入點只在出現真實 learner source context 時擴充 drill template；不能以預先生成題庫取代來源情境。
