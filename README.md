# TOEFL iBT 2026 Coaching System

這是一套在 Codex 中使用的 TOEFL iBT 2026 寫作與口說教練系統。它會依專案內固定版本的評分標準提供可追溯的回饋，並把正式練習、修訂、錯誤事件與進步報告保存在本機。

> 這個專案不是需要啟動伺服器的 App。主要使用方式是：用 Codex 開啟專案後，直接貼上題目與答案，或附上口說錄音。

## 你可以用它做什麼

- 練習 2026 TOEFL Writing：`Write an Email`、`Academic Discussion`
- 練習 2026 TOEFL Speaking：`Listen and Repeat`、`Take an Interview`
- 取得有原文或時間戳證據的分級回饋
- 追蹤完整修訂鏈、修訂解決率與重複錯誤
- 將原子錯誤歸納為 `SENTENCE-CONTROL`、`LEXICAL-NATURALNESS`、`IDEA-DEVELOPMENT` 等能力群組
- 以不計分的 targeted drill 練習特定弱點，並追蹤 transfer 與 mastery 狀態
- 兩輪修訂仍未解決時，自動產生限定範圍的訓練計畫
- 每累積三次相關正式練習，自動產生階段性報告
- 在本機完成錄音檢查與轉錄，不上傳原始音檔

## 快速開始

### 1. 準備環境

需求：

- Python 3.11 以上
- Codex（用來載入專案內的教練規則）

在專案根目錄執行：

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install 'PyYAML>=6,<7' 'pytest>=8,<9'
```

目前不需要把專案安裝成 Python 套件；測試設定會直接從 `tools/` 載入 tracker 模組。

### 2. 確認專案正常

```bash
python3 -m pytest
python3 tools/validate_tracker.py
```

- 測試全部通過，代表程式與專案契約正常。
- `validate_tracker.py` 沒有輸出且結束碼為 `0`，代表現有追蹤資料通過完整性檢查。

### 3. 開始第一次寫作練習

用 Codex 開啟本專案，直接輸入：

```text
這是一題 TOEFL Academic Discussion，請評估並記錄為正式練習。

[完整題目與其他學生的回答]

My response:
[你的完整英文回答]

作答時間：10 分鐘
使用輔助：無
```

完整題目加完整答案預設會記為 `formal_original`。如果只想討論、不想留下正式紀錄，請明確加上「不要記錄這次練習」。

第一輪回饋會包含模擬任務分數、判分理由、未達下一級的原因、逐段證據、最多三個改善重點與限定範圍的改寫任務。系統不會在你自行修訂前直接給完整範文。

### 4. 提交修訂

保留第一次回饋提供的 attempt ID，接著輸入：

```text
這是 W-AD-YYYYMMDD-NNN 的修訂版，請比較上次指定的三個重點。

[修訂後的英文回答]
```

修訂會連回原始作答，不會增加正式練習次數，也不會覆蓋舊版本。

修訂可以接續前一版形成完整 lineage。階段報告會顯示分數軌跡、最新一輪解決率、首次完全解決的輪次，以及修訂過程中新產生的錯誤。

如果同一條修訂鏈經過兩輪仍未完全解決，系統會建議先切換至 targeted drill，再用全新題目檢查 transfer，避免只在同一篇文章上反覆局部修補。

## Targeted drill 與 mastery

Targeted drill 是針對一至數個錯誤碼的限定練習，不是 TOEFL 正式題，也不提供模擬任務分數。每筆 drill 會保存：

- drill set ID 與目標錯誤碼
- 題目數、答對數與正確率
- 提供問題證據的正式 attempt ID
- 練習內容、作答與回饋

Mastery 是獨立的衍生狀態，不會改寫既有 error event 的 `historical_status`：

```text
identified → practised → provisional → transferred → controlled
                                                        ↓
                                                     relapsed
```

目前的基本門檻是：至少兩組 drill 且整體正確率達 `80%` 才能進入 `provisional`。現有 mastery 層屬於診斷基礎版；「只計算 drill 之後的新題 opportunity」與明確的 transfer chain 將在下一個 P0 milestone 補齊，因此目前的 `transferred`／`controlled` 不應單獨視為最終掌握證明。

## 口說功能（選用）

口說轉錄完全在本機執行，另外需要：

- `ffmpeg` 與 `ffprobe`
- `whisper-cli`（whisper.cpp）
- 英文模型 `ggml-small.en.bin`

macOS 可先安裝工具：

```bash
brew install ffmpeg whisper-cpp
```

將模型放在專案目錄外，再設定其絕對路徑：

```bash
export TOEFL_WHISPER_MODEL="/absolute/path/to/ggml-small.en.bin"
python3 tools/inspect_audio.py --preflight
```

前置檢查成功時會輸出工具版本、模型名稱與模型雜湊。基於隱私與完整性規則，模型與原始錄音都必須放在 repository 外。

準備一段錄音供教練確認說話者：

```bash
python3 tools/prepare_speaking_session.py \
  --audio "/absolute/path/to/recording.m4a" \
  --task-type take_an_interview \
  --output-dir "/absolute/path/to/private-review"
```

`--task-type` 可用：

- `listen_and_repeat`：完整 7 題
- `take_an_interview`：完整 4 題

接著在 Codex 附上錄音並說明練習類型。正式評估前，教練會先請你確認 examiner／learner 的片段配對；不確定的配對不會被默認為正確。

專案預設不複製原始音檔，只保存來源參照、檢查結果、逐段轉錄、角色配對、評估與時間戳事件。

## 評分與紀錄原則

- Writing 單題使用 ETS 公開 rubric，提供 `0–5` 的模擬任務分數。
- Speaking 練習目前只提供 `diagnostic_only` 診斷結果。
- 單題或單組練習不會被宣稱為完整 Writing／Speaking section band。
- 每個問題都必須連到確切英文摘錄或音訊時間戳。
- 第一輪最多三個改善目標，並區分 `must-fix`、`should-fix`、`polish`。
- 原始作答、修訂與既有評估都是不可覆寫紀錄。
- 評分標準版本與最後查核日期以 `standards/ets-2026/manifest.yaml` 為準。

## 常用維護指令

```bash
# 執行全部測試
python3 -m pytest

# 檢查 tracker 的資料完整性
python3 tools/validate_tracker.py

# 審核舊資料（只讀；預設不寫入 tracker）
python3 tools/review_legacy_tracker.py --modality writing

# 重建全部衍生報告
python3 tools/rebuild_reports.py

# 重建兩輪修訂後的 adaptive training plan
python3 tools/rebuild_training_plan.py

# 產生目前可執行的 Writing drill → transfer 練習順序
python3 tools/rebuild_practice_queue.py

# 顯示每輪修訂保留、消失與新出現的錯誤碼
python3 tools/rebuild_revision_learning.py

# 只重建單一類型
python3 tools/rebuild_reports.py --modality writing
python3 tools/rebuild_reports.py --modality speaking

# 查看各資料登錄工具的必要參數
python3 tools/register_writing_attempt.py --help
python3 tools/register_writing_drill.py --help
python3 tools/register_speaking_session.py --help
```

一般練習不需要手動執行 registration CLI；Codex 教練流程會建立資料、重建報告並執行驗證。這些指令主要供維護、除錯或資料稽核使用。

如果 `review_legacy_tracker.py` 找到舊資料的狀態或摘錄不一致，請先逐筆查看輸出。只有在 `legacy-compat.yaml` 明確記錄 event ID、前後值與原因的人工核准例外，完整性檢查才會接受該筆舊資料；原始作答與事件不會被改寫。

## 資料放在哪裡

```text
.
├── AGENTS.md                  # 全專案教練、評分與隱私規則
├── .agents/skills/            # Writing / Speaking 的 Codex 技能與參考資料
├── standards/ets-2026/        # 固定版本的評分標準、任務規則與錯誤分類
├── tracker/
│   ├── writing/               # 寫作紀錄、dashboard、錯誤事件與 profile
│   └── speaking/              # 口說紀錄、dashboard、錯誤事件與 profile
├── tools/                     # 登錄、驗證、報表、音訊檢查與本機轉錄工具
├── tests/                     # 單元、整合、完整性與技能契約測試
└── docs/superpowers/          # 系統設計與實作計畫
```

重要輸出：

- `tracker/<類型>/dashboard.csv`：每次正式練習摘要
- `tracker/<類型>/profile.md`：目前常見問題狀態
- `tracker/<類型>/error-events.jsonl`：可追溯的逐項錯誤事件
- `tracker/<類型>/attempts/<attempt-id>/`：單次作答的不可覆寫資料
- `tracker/<類型>/reports/`：依練習節奏產生的階段報告
- `tracker/writing/mastery.md`：各錯誤碼的 drill、transfer 與控制狀態
- `tracker/writing/mastery.yaml`：供程式使用的 mastery 結構化資料
- `tracker/writing/training-plan.md`：兩輪修訂未解決時產生的下一步訓練計畫

## 開發狀態與下一階段

目前已完成 Writing／Speaking 基礎教練、不可覆寫 tracker、三篇報告、完整 revision lineage、Writing skill families、targeted drill 紀錄、mastery 狀態與 adaptive training plan。

接下來依照「能否形成穩定的弱點改善閉環」排序：

1. **個人化 drill pack 產生器**：根據真實錯誤摘錄與 task route，產生限定題數的練習包、作答模板與延後顯示的答案說明。
2. **Transfer check lifecycle**：明確連結來源正式作答、drill、全新題目與 mastery transition，並補強 opportunity 的紀錄與確認流程。
3. **整合式 Writing progress overview**：把三篇窗口、錯誤密度、能力群組、修訂效率與 mastery 集中在單一可讀報告。
4. **回饋校準與回歸樣本**：加入匿名化固定樣本，檢查相同文章在相同 rubric 下的評分與錯誤分類是否穩定。
5. **Speaking progress parity**：將 revision lineage、能力群組、targeted drill 與 transfer tracking 延伸到兩種 2026 Speaking 任務。

詳細範圍、驗收條件與開發順序見 `docs/superpowers/plans/2026-08-07-toefl-next-feature-roadmap.md`。

## 常見問題

### 為什麼沒有直接給我完整高分範文？

專案刻意要求先完成一次修訂或重錄，避免回饋變成被動閱讀。第一輪會給具體、有限範圍的修改任務；完成後才能取得完整高分示範。

### 為什麼我的單題分數不是 1–6 band？

`1–6` 是完整 section 的成績尺度。Writing 單題只能標示模擬 `0–5` 任務分數，Speaking 單組練習則是診斷；兩者都不能直接換算成完整 section band。

### Targeted drill 的正確率可以當成 TOEFL 分數嗎？

不可以。Drill 正確率只用來判斷特定能力是否值得進入新題 transfer check；它不是 ETS task score，也不能換算成 Writing section band。

### `inspect_audio.py --preflight` 為什麼失敗？

依錯誤訊息依序確認 `ffmpeg`、`ffprobe`、`whisper-cli` 是否在 `PATH` 中，以及 `TOEFL_WHISPER_MODEL` 是否指向 repository 外、檔名完全為 `ggml-small.en.bin` 的可讀檔案。

### 可以把錄音放進專案嗎？

不可以。音訊流程會拒絕 repository 內的原始錄音；常見音訊格式與 `tracker/**/media/` 也已加入 `.gitignore`，降低誤提交風險。

## 延伸閱讀

- 系統規則：`AGENTS.md`
- 評分標示政策：`standards/ets-2026/score-policy.md`
- 標準來源與版本：`standards/ets-2026/manifest.yaml`
- 系統設計：`docs/superpowers/specs/2026-07-31-toefl-coaching-system-design.md`
- 下一階段 roadmap：`docs/superpowers/plans/2026-08-07-toefl-next-feature-roadmap.md`
