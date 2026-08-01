# TOEFL 追蹤完整性與逐字稿優先口說流程硬化設計

日期：2026-08-01
狀態：待使用者書面審閱
適用分支：`codex/toefl-coaching-system`
基礎版本：`84419d4`

## 1. 目的

本階段修正 2026 TOEFL Writing／Speaking 教練系統中仍會影響長期追蹤可信度的結構問題。完成後，系統必須保證：

1. 一筆已發布練習永遠同時包含其不可變作答、回饋、錯誤事件與評分版本。
2. 程序在任何發布邊界中斷，都不會造成 attempt 與錯誤事件分離。
3. Writing 與 Speaking 無法繞過各自的正式評估閘門。
4. 每個 counted event 都能由原始作答或 learner 音訊片段重新驗證。
5. Aggregate ledger、dashboard、profile 與三次練習報告皆可由 canonical attempts 確定性重建。
6. 口說角色辨識採逐字稿與 TOEFL 題型結構優先，不引入不必要的通用聲紋辨識。
7. 現有正式資料保持 Writing 1 筆、7 個 counted events；Speaking 0 筆。

本設計延續 `docs/superpowers/specs/2026-07-31-toefl-coaching-system-design.md`。兩者衝突時，本文件只在資料發布、驗證、重建與音訊入口範圍內優先。

## 2. 已確認的設計決策

### 2.1 Canonical attempt directory

採用「每個 attempt 目錄是唯一真實來源」：

- 每個 attempt 自己保存 `events.jsonl`。
- `tracker/<modality>/error-events.jsonl` 改為衍生檔案。
- 發布 attempt 只需要一次原子目錄 rename。
- 未發布 staging 可安全清除；不需要由 aggregate ledger 猜測是否完成。

不採用以下方案：

- 雙寫加 write-ahead log：交易狀態與復原路徑較複雜。
- SQLite：會破壞現有 Git 可讀、每次練習一個目錄的架構。

### 2.2 Transcript-first speaker mapping

口說角色推斷不使用聲紋 enrollment，也不要求通用 speaker diarization。流程為：

1. 檢查音檔技術品質。
2. 本機產生帶時間戳逐字稿。
3. 依 TOEFL 題型、交替順序與文字內容推斷 examiner／learner。
4. 只有結構或文字證據不足的片段需要使用者確認。

音訊訊號仍用於片段時間邊界與品質判斷，不用於辨認使用者身分。

### 2.3 Local-only transcription

允許安裝：

- Homebrew `ffmpeg`，提供 `ffmpeg` 與 `ffprobe`。
- Homebrew `whisper-cpp`，在 Apple Silicon 本機執行 transcription。
- workspace 外的 `ggml-small.en.bin`；以 `TOEFL_WHISPER_MODEL` 指向該檔，model 不可提交 Git。

`whisper.cpp` 在 Apple Silicon 支援 Metal，本機執行時不需上傳音檔。CLI 只接受 16-bit WAV，因此入口先以 `ffmpeg` 轉成 16 kHz mono PCM WAV，再交給 `whisper-cli`。

安裝來源：

- https://formulae.brew.sh/formula/ffmpeg
- https://formulae.brew.sh/formula/whisper-cpp
- https://github.com/ggml-org/whisper.cpp

## 3. Canonical 資料模型

### 3.1 Attempt 目錄

除 re-evaluation 外，每筆已發布紀錄至少包含：

```text
tracker/<modality>/attempts/<attempt-id>/
├── attempt.yaml
├── prompt.md
├── response-original.md | response-revision.md
│   | transcript-original.md | transcript-revision.md
├── feedback-round-1.md
└── events.jsonl
```

Speaking formal original 另外包含：

```text
├── audio-inspection.json
├── transcript-segments.yaml
├── segments.yaml
└── source-reference.txt
```

`events.jsonl` 可為空檔，但不得缺少。每一行必須是屬於該 attempt 的完整 event mapping。

### 3.2 Aggregate derived files

以下檔案均為衍生資料：

- `tracker/<modality>/error-events.jsonl`
- `tracker/<modality>/dashboard.csv`
- `tracker/<modality>/profile.md`
- `tracker/<modality>/reports/*.md`

重建順序固定為：

1. 依 `submitted_at` 排序。
2. 相同時間依 `attempt_id` 排序。
3. 同 attempt 中依 sidecar 原始行序；若需產生新檔，依 `event_id` 排序。

Aggregate ledger 必須逐位元等於 canonical sidecars 的確定性串接結果。

### 3.3 Re-evaluation

`re_evaluation` 是連結既有 `formal_original` 的 schema version 2 非 cadence 紀錄。其目錄固定包含：

```text
tracker/<modality>/attempts/<re-evaluation-id>/
├── attempt.yaml
├── feedback-round-1.md
└── events.jsonl
```

`events.jsonl` 必須存在且為空；同一份 learner evidence 不重複建立語言錯誤事件。`attempt.yaml` 必須包含：

```yaml
schema_version: 2
record_type: re_evaluation
parent_attempt_id: "<formal-original-id>"
evaluated_at: "<ISO-8601 timestamp>"
supersedes_evaluation_id: "<parent-id>@<old-rubric-version>"
rubric_version: "<new-rubric-version>"
standard_verified_at: "<ISO date>"
source_hash: "<same digest as parent>"
```

並保存所屬 modality/task type、`result_type`、新 `task_score` 或診斷結果及新 `task_metrics`。另外：

- 必須具有 `parent_attempt_id`。
- parent 必須為相同 modality、task type 的 formal original。
- `supersedes_evaluation_id` 必須等於 parent 原評估或同 parent 前一筆 re-evaluation 的穩定 ID。
- 不重複保存或改寫 parent 的原始證據。
- 不增加 formal attempt/session 數。
- 報告若選用 re-evaluation，必須同時呈現原評估與新評估版本，不得靜默取代。

舊 schema version 1 仍可讀且不遷移。Schema version 2 只用於新 re-evaluation；不得用它覆寫既有正式紀錄。

## 4. 原子發布與復原

### 4.1 Registration bundle

底層發布 API 不再接受散落的未驗證參數。它只接受已完成 modality gate 的 registration bundle：

```python
@dataclass(frozen=True)
class ValidatedPracticeRegistration:
    attempt: dict
    prompt: str
    response: str
    feedback: str
    events: tuple[dict, ...]
    extra_files: Mapping[str, str]

@dataclass(frozen=True)
class ValidatedReevaluationRegistration:
    attempt: dict
    feedback: str
```

兩個型別只能由 Writing 或 Speaking gate 建立。Re-evaluation publisher 固定建立空 `events.jsonl`，並由 parent 驗證其 evidence digest。Publisher 仍執行不依賴 AI 判斷的防禦性驗證，但不負責評估語意。

### 4.2 發布步驟

在跨程序 registration lock 內：

1. 重新讀取 canonical attempts 與 events。
2. 執行 duplicate source hash、attempt ID、event ID 與 parent 驗證；practice record 不得重複 source hash，re-evaluation 則必須與指定 parent 的 source hash 相同。
3. 建立同一檔案系統內的 staging 目錄。
4. 寫入完整 bundle，包括 `events.jsonl`。
5. 對每個檔案 flush 並 `fsync`。
6. 對 staging directory `fsync`。
7. 將 staging rename 成正式 attempt ID 目錄。
8. 對 attempts parent directory `fsync`。
9. 完成後才回傳 destination。

Aggregate ledger 不在 registration transaction 內雙寫。正式發布後可呼叫 derived rebuild；即使 rebuild 被中斷，canonical attempt 仍完整存在。

### 4.3 中斷復原

- 沒有完成 rename 的 staging 一律不是正式紀錄。
- 啟動 registration 或 audit 時，可刪除符合本系統命名規則的未發布 staging。
- 已 rename 的 attempt 必須完整；缺檔時 audit 報告 corruption，不猜測或補造內容。
- 不再使用 `.ready` 推斷跨檔案交易狀態。

### 4.4 Kill-boundary tests

以 subprocess 與可控 failpoint 測試至少以下邊界：

- 寫入 `attempt.yaml` 後。
- 寫入 `events.jsonl` 後。
- staging directory `fsync` 後。
- rename 前。
- rename 後、derived rebuild 前。

每個中斷點重啟後只能有兩種合法結果：

- attempt 完全不存在，aggregate 不含其 events；或
- attempt 完整存在，重建後 aggregate 完整包含其 events。

不得出現半筆 attempt、orphan events 或 events 遺失。

## 5. Modality-specific registration gates

### 5.1 Writing

新增 `tools/register_writing_attempt.py`，順序為：

1. 讀取 attempt、prompt、response、feedback 與 events。
2. 建立並驗證 canonical source hash。
3. 執行 `validate_attempt`。
4. 執行 `validate_writing_assessment`。
5. 執行 contextual event validation。
6. 建立 `ValidatedPracticeRegistration` 或 `ValidatedReevaluationRegistration`。
7. 發布 canonical attempt。
8. 重建 Writing derived files。
9. 執行 tracker audit。

### 5.2 Speaking

`tools/register_speaking_session.py` 保留為唯一正式 Speaking 入口，必須完成：

- technical inspection contract。
- transcript-first role mapping。
- 完整七題 Listen and Repeat 或四題 Interview mapping。
- `usable` 與 `reliable_dimensions` 判斷。
- feedback、timestamp 與 contextual event validation。

### 5.3 Generic CLI

`tools/register_attempt.py` 不得成為繞過 modality gate 的入口：

- Writing formal original、revision 與 re-evaluation：轉交 Writing gate，要求完整 Writing feedback evidence。
- Speaking：拒絕並明確指向 `register_speaking_session.py`。
- `discussion_only` 不寫入 formal tracker。
- `targeted_drill` 若持久化，仍必須走對應 modality gate，但不計 cadence。

直接呼叫 publisher 並傳入普通 dict 的舊 API 移除或改成 private。

## 6. Contextual event integrity

每個 event 除了 schema 驗證，還必須在 registration lock 內與現有歷史共同驗證。

版本化 taxonomy 的唯一機器可讀來源為 `standards/ets-2026/taxonomy.yaml`。每個 code 必須明列：

```yaml
GRAM-ARTICLE:
  taxonomy_version: 1
  modality: writing
  scope: common
  task_types: [email, academic_discussion]
  dimension: grammar
LR-OMISSION:
  taxonomy_version: 1
  modality: speaking
  scope: route
  task_types: [listen_and_repeat]
  dimension: reconstruction
```

Writing／Speaking skill 中的人類可讀 taxonomy reference 由此檔同步或驗證，不得另外維護互相衝突的 code scope。

### 6.1 共用規則

- `event_id` 在同 modality 全域唯一。
- `attempt_id` 等於 bundle attempt ID。
- `code` 存在於版本化 taxonomy。
- `opportunity_present` 為 `true`。
- `attempt.opportunities[code]` 為正整數。
- `task_specific` 與 taxonomy scope 相符。
- route-specific code 只允許出現在對應 task type。
- `historical_status` 等於加入當次 attempt 後的確定性計算結果。
- `polish` 不得進入 counted rate；若保存為 event，必須明確標記為非 counted。

### 6.2 Writing evidence

- counted event 必須有非空 `source_excerpt`。
- excerpt 必須以 Unicode normalization 後的 exact substring 存在於 immutable response。
- 建議修改與 reason 必須非空。
- Email code 不得出現在 Academic Discussion；Discussion code 不得出現在 Email。

### 6.3 Speaking evidence

- counted event 必須有合法 timestamp。
- timestamp 必須完整落在 confirmed learner segment。
- event code 所需 dimension 必須包含在 `reliable_dimensions`。
- reconstruction code 只允許 Listen and Repeat。
- Interview content/elaboration code 只允許 Take an Interview。

### 6.4 UNCLASSIFIED

`UNCLASSIFIED` 可以保存，但必須：

- `task_specific: false`。
- 帶有 `taxonomy_review_required: true`。
- 不參與 recurring/persistent 排行、錯誤率或 controlled 判定。
- Audit 在 profile 中列出待分類數量。

## 7. Deterministic rebuild and audit

### 7.1 Rebuild

`rebuild_modality(root, modality)` 從 canonical attempts 執行：

1. 驗證每個 attempt 與 sidecar。
2. 生成 aggregate ledger。
3. 生成 dashboard。
4. 生成 profile。
5. 生成所有已跨越的 cadence reports。
6. 將 `reports/` 調整為精確預期集合；移除過期的本系統產生報告。

Writing 與 Speaking 即使零筆紀錄，也必須具有：

- 有 header 的空 dashboard。
- 有標題與 formal count 0 的 profile。
- 空或不存在但經 audit 認可的 reports 目錄；實作統一採存在的空目錄。

只移除符合本系統 report filename schema 的衍生檔案，不刪除未知使用者文件。

### 7.2 Report content

每份 cadence report 至少包含：

- modality、route 與報告邊界。
- formal record total 與涵蓋 attempt IDs。
- 每筆 `timed`／`untimed`／`unknown`。
- 每筆 `official_basis`／`simulated_task_score`／`diagnostic_only`。
- rubric ID 與 `standard_verified_at`。
- 跨 rubric 版本警告。
- 每筆 score/diagnostic 結果序列，不跨不同 task score 取平均。
- 每筆 severe counted event 數形成的實際趨勢。
- recurring、persistent、controlled、relapsed。
- revision resolution rate。
- 下一階段最多兩個訓練重點。

Common report 只使用 taxonomy scope 為 common 的 codes。Route report 使用 common codes 加上該 route codes。

下一階段訓練重點採固定順序選出最多兩項：先 `relapsed`，再 `persistent`，再依最近三筆 counted event 數降冪、code 名稱升冪。`UNCLASSIFIED` 不得成為自動訓練重點。

### 7.3 Audit

Audit 必須：

- 捕捉 `UnicodeDecodeError`、YAML／JSON／CSV parsing error 並回報檔案路徑。
- 驗證 manifest 與 score-policy contract。
- 驗證 canonical attempt、sidecar、parent、source hash 與 global event uniqueness。
- 重新計算 historical status 並比對 stored value。
- 對 Speaking 重新執行 inspection、transcript mapping 與 assessment validation。
- 在 temporary directory 重建兩個 modalities，包括零筆 modality。
- 逐位元比較 aggregate ledger、dashboard、profile 與 reports 的精確集合及內容。

Audit 不得因單一損毀檔案 traceback 終止；應累積 findings 並回傳非零狀態。

## 8. Transcript-first speaking pipeline

### 8.1 Preflight

在讀取正式音檔前一次檢查：

- `ffmpeg` 可執行。
- `ffprobe` 可執行。
- `whisper-cli` 可執行。
- `TOEFL_WHISPER_MODEL` 已設定，basename 為 `ggml-small.en.bin`，檔案存在且不位於 repository 內。

缺少任一項時停止 transcription，輸出精確安裝或設定指示，不建立 formal speaking attempt。

### 8.2 Technical inspection

Inspection 保存：

- duration、codec、sample rate、channels。
- mean dBFS、peak dBFS、clipping、decodable。
- `usable`。
- `reliable_dimensions`。
- 工具版本與 model identifier，不保存私人絕對路徑。

所有 dBFS 判斷在 inferred learner segments 上個別計算。版本 1 quality policy 的固定規則為：

- undecodable：`usable: false`。
- 任一 learner segment peak `>= -0.1 dBFS`：視為 clipping，`usable: false`，不得註冊完整 formal session。
- 任一 learner segment peak `<= -35 dBFS` 或 mean `<= -45 dBFS`：視為 effectively inaudible，`usable: false`。
- 未達上述阻擋條件，但任一 learner segment mean `< -35 dBFS` 或 peak `< -20 dBFS`：`usable: true`，只保留文字可支持的 `content`、`grammar`、`vocabulary`，Listen and Repeat 可另保留 `reconstruction`；移除 `fluency`、`intelligibility`、`pronunciation`、`stress`、`rhythm`、`intonation`。
- 其餘清楚片段：`usable: true`，依題型保存所有實際評估的可靠面向。

這些是內部錄音品質門檻，不是 ETS 評分標準。閾值與 clipping 判斷集中於版本化 quality policy，測試固定邊界；不得散落在多個函式。

### 8.3 Local transcription

1. 在系統 temporary directory 建立 16 kHz mono PCM WAV。
2. 呼叫 `whisper-cli` 產生帶時間戳輸出。
3. 將輸出正規化為：

```yaml
- start: 0.0
  end: 3.8
  text: "Please describe a place where you like to study."
```

4. 刪除 temporary WAV 與 Whisper 中間檔。
5. 保存正規化 transcript segments，不保存 model 絕對路徑。

### 8.4 TOEFL role inference

Role inference 的輸入只有 task type 與 timestamped transcript。每個推斷保存 `role_reason` 與 confidence。

Listen and Repeat：

- 預期七組 examiner source → learner repeat。
- 使用 item order、alternation 與 source/learner token similarity。
- source 與 learner 不必完全相同；遺漏或替換仍可形成一組。

Take an Interview：

- 預期四組 examiner question → learner answer。
- 使用 item order、alternation、question form、answer discourse 與相對長度。
- 不以聲音性別、音高或既有聲紋判斷角色。

只有下列情況標為 ambiguous：

- 缺少預期 prompt 或 answer。
- 片段重疊或無法可靠切分。
- 多人插話。
- 轉錄內容無法符合題型結構。
- item count 不等於七或四。

High-confidence 完整 mapping 可自動確認；medium/low confidence 只列出歧義片段請使用者確認，不重問整包音檔。

## 9. Migration

新增一次性、可重複執行的 migration CLI，具備 `--dry-run` 與 `--apply`。

對每個既有 attempt：

1. 讀取 aggregate ledger 中相同 `attempt_id` 的 events。
2. 驗證沒有 orphan、duplicate event ID 或跨 attempt event。
3. 計算預期 sidecar content。
4. `--dry-run` 只輸出將新增的 sidecars 與前後 event count。
5. `--apply` 以 atomic write 建立缺少的 `events.jsonl`。
6. 已存在且內容相同時不變更。
7. 已存在但內容不同時停止，不覆寫。
8. 完成後由 canonical sidecars 重建 aggregate ledger。

現有正式資料的必要 invariant：

- Writing formal count：1。
- Writing attempt ID：`W-AD-20260731-001`。
- Writing counted event count：7。
- Writing word count：183。
- Speaking formal count：0。
- 原始 prompt、response、feedback 與 attempt metadata 雜湊不變。

## 10. Testing strategy

所有 production behavior 變更遵循 RED → GREEN → REFACTOR。

### 10.1 Storage and migration

- subprocess kill-boundary tests。
- 空 events sidecar。
- duplicate attempt/source/event rejection。
- migration dry-run、idempotency、conflict stop。
- canonical → aggregate deterministic byte comparison。

### 10.2 Registration gates and contextual events

- Generic CLI 拒絕 Speaking。
- Writing CLI 必須通過 Writing feedback gate。
- 假 excerpt、零 opportunity、錯誤 route code、重複 ID、錯誤 historical status 被拒絕。
- UNCLASSIFIED 不污染 rates/status。
- revision 與 re-evaluation parent 關係完整驗證。

### 10.3 Reports and audit

- 第 3、6 個 formal 邊界。
- Common/route code isolation。
- Formal totals、attempt IDs、timing、result labels、rubric boundaries 與真正逐筆趨勢 snapshot。
- stale generated report removal。
- 零筆 Speaking derived artifacts。
- invalid UTF-8、invalid YAML/JSON/CSV 不造成未處理例外。

### 10.4 Audio and role inference

- preflight 缺少各工具或 model 的獨立錯誤。
- 音量、削波與 reliable-dimensions 邊界。
- 七組 Listen and Repeat transcript mapping。
- 四組 Interview transcript mapping。
- 缺題、插話、重疊與 ambiguous confirmation。
- counted timestamp 必須落在 learner segment 且 dimension reliable。
- 使用真實 `.m4a` 執行解碼、轉錄與 mapping smoke。
- 確認 repository 不新增原始 media 或私人來源路徑。

## 11. Error handling and privacy

- 原始音檔預設留在使用者提供位置。
- Workspace 只保存 opaque source ID、inspection、transcript、segments 與 feedback。
- Temporary WAV 與 ASR intermediate files 無論成功或失敗都清除。
- Credential-bearing URL 不得寫入 tracked file。
- 不可靠音訊不轉換成 learner language error。
- Derived rebuild 失敗不回滾 canonical attempt；audit 會報告 derived stale，下一次可重建。
- Migration 或 audit 遇到矛盾資料時停止自動修復並列出精確檔案與原因。

## 12. Acceptance criteria

本階段只有在以下全部成立時才可進入合併選項：

1. Kill-boundary tests 證明已發布 attempt 與 events 不會分離。
2. 每個 attempt 具有 canonical `events.jsonl`，aggregate ledger 可完全重建。
3. Writing 與 Speaking formal registration 無繞過路徑。
4. Contextual event validation 與 audit 使用相同規則。
5. Common report 不包含 route-specific codes。
6. 每份 cadence report 具有 formal totals、conditions、result labels、rubric/version 與逐筆趨勢。
7. Rebuild 精確調整 derived file set，包括零筆 Speaking。
8. Invalid UTF-8 只產生 audit findings，不造成 traceback。
9. Re-evaluation 保存新舊評估並排除 cadence。
10. `ffmpeg`、`ffprobe`、`whisper-cli` 與本機 model preflight 明確。
11. 真實 `.m4a` 完成 local transcription 與 TOEFL structure role inference。
12. 無原始音檔、temporary WAV、私人絕對路徑或 credential URL 進入 Git。
13. 現有 Writing 仍為 1 筆、183 字、7 個 counted events；Speaking 仍為 0 筆。
14. 完整測試、skill validation、tracker audit、rebuild idempotency 與 whole-branch review 全部通過。

## 13. 非目標

- 不建立通用多人 speaker diarization。
- 不保存或辨識使用者聲紋。
- 不上傳音檔至雲端 transcription service。
- 不建立官方未公開的 Speaking task score。
- 不改動既有作文內容或以新 rubric 覆寫舊評分。
- 不加入 Reading／Listening 追蹤。
- 不建立網站、App 或外部資料庫。
