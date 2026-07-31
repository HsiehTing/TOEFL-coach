# TOEFL 2026 寫作與口說回饋追蹤系統設計

日期：2026-07-31
狀態：待使用者審閱
適用工作區：`/Users/twinb00599242/Documents/TOEFL`

## 1. 目的

建立一套可跨 Codex 對話持續運作的 TOEFL iBT 2026 寫作與口說教練系統。系統必須同時做到：

1. 以使用者的 Writing 與 Speaking section 目標 band 6 為長期方向。
2. 依 ETS 2026 題型與公開評分依據提供一致回饋。
3. 區分官方分數、任務層級模擬分數與非官方診斷指標。
4. 保存每次正式練習、修改版、錯誤證據與評分版本。
5. 使用固定錯誤代碼辨識一錯再錯、改善、已控制與復發。
6. 寫作與口說各自依題型走不同回饋路線。
7. 每三次正式練習產生共用能力報告，每三次同題型練習產生題型專屬報告。
8. 所有統計皆能追溯至原始作答或錄音中的具體證據，且能由原始紀錄重新計算。

## 2. 設計原則

### 2.1 以持久資料取代聊天記憶

Codex 對話不是學習歷史的唯一來源。所有正式練習均寫入工作區；新對話必須能從工作區重建使用者目前的能力輪廓。

### 2.2 官方標準與診斷標準分離

- ETS 公開的題型、量尺與 rubric 標示為「官方依據」。
- ETS 未公開任務層級量尺的面向，標示為「診斷標準」。
- 不把單題結果冒充完整 section score。
- 不把內部診斷數字冒充 ETS 官方算法。

### 2.3 任務分流

寫作開放式作答分成：

- Write an Email
- Write for an Academic Discussion

口說分成：

- Listen and Repeat
- Take an Interview

Build a Sentence 是 2026 Writing section 的第三種題型，但屬客觀句法題；本系統保留擴充位置，不混入兩種開放式寫作的迭代回饋。

### 2.4 原始紀錄不可覆寫

原始作答、修改版、重新評分與 rubric 更新後的 re-evaluation 必須分開保存。衍生報告可以重建，原始證據不可被衍生結果覆蓋。

### 2.5 回饋以行動為中心

每次第一輪最多指定三個優先改善目標。完整範文延後至使用者自行修改後提供，避免回饋退化為被動閱讀。

## 3. 系統架構

```text
TOEFL/
├── AGENTS.md
├── .agents/
│   └── skills/
│       ├── toefl-writing-coach/
│       │   ├── SKILL.md
│       │   ├── agents/
│       │   │   └── openai.yaml
│       │   └── references/
│       │       ├── email-feedback.md
│       │       ├── discussion-feedback.md
│       │       └── writing-error-taxonomy.md
│       └── toefl-speaking-coach/
│           ├── SKILL.md
│           ├── agents/
│           │   └── openai.yaml
│           └── references/
│               ├── listen-and-repeat.md
│               ├── take-an-interview.md
│               ├── audio-intake.md
│               └── speaking-error-taxonomy.md
├── standards/
│   └── ets-2026/
│       ├── manifest.yaml
│       ├── score-policy.md
│       ├── writing-email.md
│       ├── writing-discussion.md
│       ├── speaking-listen-repeat.md
│       └── speaking-interview.md
├── tracker/
│   ├── writing/
│   │   ├── attempts/
│   │   ├── error-events.jsonl
│   │   ├── dashboard.csv
│   │   └── profile.md
│   └── speaking/
│       ├── attempts/
│       ├── error-events.jsonl
│       ├── dashboard.csv
│       └── profile.md
└── tools/
    ├── register_attempt.py
    ├── rebuild_reports.py
    └── validate_tracker.py
```

### 3.1 `AGENTS.md`

`AGENTS.md` 是精簡的專案憲法與路由器，不保存完整 rubric 或個人練習資料。內容涵蓋：

- 教練目標與回覆語言。
- 寫作、口說 skill 的路由規則。
- task score、section score、官方標準與診斷標準的界線。
- 正式練習、修改版與不記錄模式的判定。
- 原始資料不可覆寫。
- 每次最多三個改善目標。
- 追蹤資料更新後必須驗證。
- ETS 標準版本不可靜默改寫。
- 音檔的隱私與保存原則。

目標長度為 50–100 行，避免把無關規則載入每次任務。

### 3.2 Skills

兩個 repo-scoped skills 位於 `.agents/skills`：

- `toefl-writing-coach`：寫作題型辨識、rubric 路由、迭代批改與寫作追蹤。
- `toefl-speaking-coach`：音訊品質檢查、說話者配對、口說題型路由、回饋與口說追蹤。

兩個 skills 都使用共用追蹤工具，但不得互相混算 task score。

### 3.3 Standards

`standards/ets-2026` 保存 ETS 依據的摘要、適用日期與來源連結，不大量複製官方文件。

`manifest.yaml` 至少包含：

```yaml
schema_version: 1
test_version: "TOEFL iBT 2026"
effective_from: "2026-01-21"
last_verified: "2026-07-31"
sources:
  writing_tasks: "https://www.ets.org/toefl/test-takers/ibt/about/content/writing.html"
  writing_rubric: "https://www.ets.org/content/dam/ets-org/pdfs/toefl/writing-rubrics.pdf"
  speaking_blueprint: "https://www.es.ets.org/pdfs/toefl/toefl-ibt-test-specifications-2026.pdf"
  score_scale: "https://www.ets.org/toefl/institutions/ibt/score-scale-update.html"
```

### 3.4 Tracker

Tracker 是個人進度的唯一資料來源：

- `attempts/`：每次練習的完整、可閱讀紀錄。
- `error-events.jsonl`：每個可計數錯誤事件。
- `dashboard.csv`：每次練習的衍生統計。
- `profile.md`：目前主要問題、狀態與下一階段目標。

`dashboard.csv` 與 `profile.md` 是衍生資料；若內容遺失，必須能從 attempts 與 error events 重建。

### 3.5 Tools

腳本負責確定性工作：

- `register_attempt.py`：產生 ID、驗證欄位、偵測重複、寫入正式紀錄。
- `rebuild_reports.py`：重新計算 dashboard、profile 與三次練習報告。
- `validate_tracker.py`：檢查 schema、引用完整性、修改版連結、統計一致性與 rubric 相容性。

AI 負責語意判斷；腳本不得自行推測作文或錄音的語言品質。

## 4. 練習類型與資料生命週期

每次輸入先分類為：

1. `formal_original`：正式原始作答，計入趨勢與掌握狀態。
2. `revision`：同一作答的修改版，只計入修改成功率。
3. `targeted_drill`：局部句子或發音練習，不計入 task score 趨勢。
4. `discussion_only`：討論、草稿或使用者指定不記錄的內容。

預設規則：

- 完整題目加完整作答視為 `formal_original`。
- 使用者說「不要記錄」時設為 `discussion_only`。
- 使用者說「修改版」時必須連結既有 attempt。
- 無法判定是否為新作答或修改版時，先詢問，不可猜測。

## 5. 作答紀錄資料模型

每筆 attempt 至少包含：

```yaml
schema_version: 1
attempt_id: "W-AD-20260731-001"
modality: "writing"
task_type: "academic_discussion"
record_type: "formal_original"
submitted_at: "2026-07-31T00:00:00+08:00"
practiced_at: null
timed: null
duration_seconds: null
assistance:
  spellcheck: null
  translation: null
  other: null
word_count: 182
rubric_version: "ets-writing-guide-2025-applicable-2026"
task_score:
  scale: "0-5"
  value: 3
  confidence: "medium_high"
source_hash: "sha256:<hex-digest>"
parent_attempt_id: null
```

同一 attempt 目錄保存：

- `prompt.md`
- `response-original.md` 或 `transcript-original.md`
- `feedback-round-1.md`
- `response-revision-N.md` 或 `audio-revision-N` 的引用
- `feedback-round-N.md`
- `attempt.yaml`

## 6. 錯誤事件資料模型

每個計入追蹤的錯誤事件至少包含：

```json
{
  "event_id": "ERR-20260731-0001",
  "attempt_id": "W-AD-20260731-001",
  "taxonomy_version": 1,
  "code": "GRAM-NEGATION",
  "source_excerpt": "I do not think that it is not sufficient",
  "suggested_revision": "I do not think it is sufficient",
  "reason": "The double negative reverses the intended claim.",
  "level": "must_fix",
  "severity": "meaning_changing",
  "task_specific": false,
  "opportunity_present": true,
  "historical_status": "new"
}
```

只有 `must_fix` 與 `should_fix` 納入錯誤率；`polish` 不納入。

同一篇中同類錯誤重複發生時，同時保存：

- 事件數：錯誤實例總數。
- 受影響 attempt 數：此類錯誤出現於幾篇獨立正式練習。

## 7. 寫作回饋路線

### 7.1 Write an Email

使用 ETS Write an Email 0–5 rubric，檢查：

- 寄件者、收件者、角色與關係。
- 溝通目的。
- 題目要求事項是否完整。
- 支持溝通目的的 elaboration。
- register、禮貌與社交慣例。
- 資訊組織。
- request、proposal、refusal、criticism 等行動表達。
- 句型、詞彙與語言錯誤。

Email 任務專屬代碼使用 `EMAIL-*` 前綴，例如：

- `EMAIL-PURPOSE`
- `EMAIL-MISSING-POINT`
- `EMAIL-REGISTER`
- `EMAIL-POLITENESS`
- `EMAIL-ORGANIZATION`
- `EMAIL-ACTION`

### 7.2 Write for an Academic Discussion

使用 ETS Academic Discussion 0–5 rubric，檢查：

- 是否精準回答教授問題。
- 立場是否明確。
- 是否回應或承接討論內容。
- 是否提出原創貢獻。
- 是否過度借用同學或 stimulus 的文字。
- 解釋、例子、細節與因果是否充分。
- 句型、詞彙與語言錯誤。

Discussion 任務專屬代碼使用 `DISCUSSION-*` 前綴，例如：

- `DISCUSSION-ALIGNMENT`
- `DISCUSSION-POSITION`
- `DISCUSSION-BORROWING`
- `DISCUSSION-CONTRIBUTION`
- `DISCUSSION-ELABORATION`
- `DISCUSSION-SUPPORT`

### 7.3 共用語言代碼

兩種寫作共用：

- `GRAM-ARTICLE`
- `GRAM-NEGATION`
- `GRAM-CLAUSE`
- `GRAM-AGREEMENT`
- `LEX-WORDFORM`
- `LEX-COLLOCATION`
- `MECH-SPELLING`
- `MECH-PUNCTUATION`

跨題型出現的共用錯誤可判定為跨題型持續性問題；任務專屬代碼不得跨路線混算。

## 8. 口說回饋路線

### 8.1 共用音訊入口

所有口說正式評估前先執行：

1. 驗證音檔能否解碼。
2. 記錄長度、格式、取樣率、聲道、音量、削波與可用性。
3. 分段並辨識題目／考官與考生聲音。
4. 產生題目—回答配對表及信心。
5. 配對有歧義時先請使用者確認。
6. 音訊品質不足時，列出可可靠評估與不可可靠評估的面向。

題目與回答配對未完成前不得正式評分。不得把錄音失真或低音量直接判定為發音問題。

### 8.2 Listen and Repeat

一組完整七題視為一個 formal speaking session。回饋包含：

- 題目原句與回答的遺漏、增加、替換、詞序差異。
- 還原準確度。
- intelligibility。
- 發音、重音、節奏與語調。
- 每題證據與整組模式。
- 局部重錄任務。

若 ETS 未公開可直接套用的任務層級量尺，結果必須標示為診斷評估，不得宣稱為官方 task score。

### 8.3 Take an Interview

一組完整四題視為一個 formal speaking session。回饋包含：

- 是否直接回答問題。
- 回答內容是否相關。
- 是否有清楚、連貫的 elaboration。
- 理由與例子。
- 文法與詞彙。
- 流暢度與停頓。
- 發音、重音、語調與 intelligibility。

同樣區分官方公開依據與內部診斷面向。

## 9. 迭代教練流程

### 9.1 第一輪

固定輸出：

1. 作答資訊與條件。
2. task score 或診斷結果、信心與依據。
3. 一句話總評。
4. 為什麼是目前層級。
5. 為什麼尚未到下一層級。
6. 具原文或音檔時間戳的證據。
7. 必改、應改、潤飾分類。
8. 最多三個優先改善目標。
9. 明確的重寫或重錄任務。

第一輪不提供完整範文或完整示範錄音文字。

### 9.2 第二輪

使用者自行重寫或重錄。系統比較指定目標是否解決，並連結至原 attempt。

### 9.3 第三輪

固定輸出：

- 修改前後結果。
- 三個指定目標的解決狀態。
- 有效修改。
- 新增錯誤。
- 修改成功率。
- 尚未解決的反覆問題。
- 是否需要再改一次。

完成自行修改後才提供高分示範，並說明示範如何符合 rubric。

## 10. 錯誤狀態規則

- `new`：首次在 formal original 中出現。
- `recurring`：至少兩個不同 formal originals 出現。
- `persistent`：最近五個可比較 formal originals 中至少三個出現。
- `improving`：至少已有四個可比較 formal originals；最近兩次的每機會發生率低於前兩次，或最近兩次的最高嚴重度均下降，且尚未達 controlled。
- `controlled`：連續三個可比較 formal originals 未出現，且每次具有相關使用機會。
- `relapsed`：controlled 後再次出現。

Revision 與 targeted drill 不得用來滿足 controlled 條件。

若某次沒有相關使用機會，該 attempt 不使錯誤狀態前進或倒退。例如沒有使用否定結構時，不得據此宣稱雙重否定已控制。

## 11. 指標

### 11.1 共用指標

- formal attempt/session 數。
- 必改與應改事件數。
- 再次出現錯誤的占比。
- 修改目標解決率。
- 新出現、recurring、persistent、controlled、relapsed 數量。

### 11.2 寫作指標

- 同題型 task score 0–5 趨勢。
- 字數與作答時間。
- 語言錯誤數／每 100 字。
- meaning-changing 錯誤數／每 100 字。
- Email 與 Discussion 任務指標分開。
- 計時與非計時資料清楚標示，不混成單一趨勢結論。

### 11.3 口說指標

- 完整 formal session 數。
- 題目—回答配對信心。
- 音訊品質狀態。
- 共用 intelligibility、流暢度、文法與詞彙問題。
- Listen and Repeat 的還原模式。
- Take an Interview 的回答、elaboration 與 coherence 模式。

不建立缺乏官方依據的任意綜合 AI 分數。

## 12. 三次練習報告

### 12.1 寫作

- 每三篇任意 formal writing：共用語言報告。
- 每三篇 Email：Email 專屬報告。
- 每三篇 Academic Discussion：Discussion 專屬報告。

### 12.2 口說

- 每三個完整 formal speaking sessions：共用口說報告。
- 每三組 Listen and Repeat：Listen and Repeat 專屬報告。
- 每三組 Take an Interview：Interview 專屬報告。

同一次練習可能同時觸發共用與專屬報告。共用報告不得把不同 task scores 直接平均。

每份報告至少包含：

1. 可比較資料範圍。
2. 分數或診斷趨勢。
3. 嚴重錯誤趨勢。
4. 反覆錯誤排行榜。
5. 新出現、改善、已控制與復發。
6. 修改成功率。
7. 阻礙下一層級的主要瓶頸。
8. 下一階段最多兩個訓練重點。

## 13. Rubric 版本與更新

每筆評估保存 `rubric_version` 與 `standard_verified_at`。

ETS 標準更新時：

1. 更新 manifest 與標準摘要。
2. 產生新的 rubric version。
3. 新作答使用新版本。
4. 舊評估保持不變。
5. 需要重評時新增 re-evaluation，不覆蓋舊值。
6. 報告跨版本比較時揭露差異。

如果無法即時查核官方來源，回饋必須顯示目前採用的最後驗證版本。

## 14. 音檔與隱私

- 不在回饋中公開可直接存取的私人錄音網址。
- 預設保存逐字稿、分段、音訊品質指標、分析與原始檔引用。
- 預設不複製原始音檔進工作區；只有使用者明確要求時才保存副本。
- 若保存原始音檔，應放在不提交 Git 的本機媒體目錄，除非使用者明確要求版本化。
- 暫存檔不得被視為長期唯一來源。

## 15. 錯誤處理

- 缺少題目：可做語言診斷，不做完整 task score。
- 缺少作答時間：標示 unknown，不猜測。
- 缺少音檔題目或回答：只評估可識別區段。
- 音訊無法解碼：停止口說內容評估並回報格式問題。
- 說話者配對不確定：先要求確認。
- taxonomy 無合適代碼：標示 `UNCLASSIFIED` 並提出 taxonomy 變更，不臨時創造近義代碼。
- 重複匯入：拒絕增加正式 attempt 數，回報既有 ID。
- 修改版找不到 parent：停止登記並要求指定。
- 衍生報告與原始資料不一致：以原始資料為準，重新生成報告。

## 16. 驗證與測試

### 16.1 基本驗證

- 所有 YAML、JSONL 與 CSV 可解析。
- 每個 error event 指向存在的 attempt。
- 每個計數錯誤有 source excerpt 或音訊時間戳。
- `polish` 不進入錯誤率。
- revision 不增加 formal attempt/session 數。
- 重複匯入不改變統計。
- 每個評估引用存在的 rubric version。

### 16.2 路由測試

- Email 輸入只載入 Email 路線。
- Academic Discussion 輸入只載入 Discussion 路線。
- Listen and Repeat 不使用 Interview 指標。
- Interview 不使用逐句還原作為主要內容指標。
- 共用語言或口說問題可以跨題型追蹤。
- 任務專屬代碼不跨路線污染。

### 16.3 報告測試

- 第三篇任意寫作觸發共用寫作報告。
- 第三篇同題型寫作觸發專屬報告。
- 第三個完整口說 session 觸發共用口說報告。
- 第三組同題型口說觸發專屬報告。
- 同時觸發時生成兩份分離的分析。

### 16.4 前向測試案例

至少使用：

- 目前的歷史 Academic Discussion 作答。
- 一篇 Email 正式作答。
- 一組 Listen and Repeat 音檔。
- 一組四題 Interview 音檔。
- 一筆 revision。
- 一筆重複匯入。
- 一個曾 controlled 後 relapsed 的模擬序列。

在新 Codex 對話中重新讀取工作區，確認可重建相同 profile 與 dashboard。

## 17. 驗收標準

實作完成必須滿足：

1. 根目錄 `AGENTS.md` 能正確路由寫作與口說。
2. 兩個 skills 可被 Codex 發現並在正確情境觸發。
3. Email 與 Discussion 使用不同回饋模板。
4. Listen and Repeat 與 Interview 使用不同回饋模板。
5. 第一輪不直接提供完整範文。
6. 只有必改與應改計入錯誤率。
7. Formal original、revision、drill、discussion only 正確分流。
8. 三次練習的共用與專屬報告依規則觸發。
9. 所有 dashboard 數字可追溯並可重建。
10. 重複匯入、修改版與 rubric 版本不會污染趨勢。
11. 新對話可從工作區恢復相同學習狀態。
12. 所有評分清楚標示官方依據、模擬分數或診斷結果。

## 18. 非目標

本階段不包含：

- 建立網站或行動 App。
- 模仿 ETS 未公開的內部 AI scoring model。
- 自動產生官方 TOEFL section score。
- 將原始錄音上傳到外部服務。
- 自動安排每日提醒。
- 閱讀與聽力追蹤。
- 將本系統封裝為公開 plugin。

上述項目可在核心寫作與口說追蹤驗證穩定後另行設計。

## 19. 官方參考來源

- [ETS TOEFL iBT Writing Section](https://www.ets.org/toefl/test-takers/ibt/about/content/writing.html)
- [ETS Writing Scoring Guide](https://www.ets.org/content/dam/ets-org/pdfs/toefl/writing-rubrics.pdf)
- [ETS TOEFL iBT 2026 Test Blueprint and Specifications](https://www.es.ets.org/pdfs/toefl/toefl-ibt-test-specifications-2026.pdf)
- [ETS TOEFL Score Scale Update](https://www.ets.org/toefl/institutions/ibt/score-scale-update.html)
- [OpenAI Custom Instructions with AGENTS.md](https://learn.chatgpt.com/docs/agent-configuration/agents-md.md)
- [OpenAI Build Skills](https://learn.chatgpt.com/docs/build-skills.md)
