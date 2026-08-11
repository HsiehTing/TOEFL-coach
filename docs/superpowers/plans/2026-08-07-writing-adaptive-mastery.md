# TOEFL 寫作自適應精熟與修訂鏈實作計畫

## 目標

實作三項直接對應 learner 現有弱點的功能：

1. `GRAM-CLAUSE` 的 targeted drill 與新題遷移驗證。
2. 完整 revision lineage 分析與兩輪後切換建議。
3. `IDEA-DEVELOPMENT` 能力群組與因果展開訓練。

先讀：[設計規格](../specs/2026-08-07-writing-adaptive-mastery-design.md)。

## 全域限制

- 在新的 `codex/` feature branch 與 worktree 實作；不得清理或覆寫主工作區的 learner tracker。
- 維持 2026 ETS 標準版本，所有 writing score 仍是 simulated task score，不換算 section band。
- 不改寫既有 attempt、feedback、event 或 `historical_status`。
- 所有新 derived 檔案必須可由 canonical attempts/events/drills 重建。
- 先寫失敗測試，再實作；每個 task 結束要跑 focused tests、完整 tests、rebuild 與 validator。

## Task 1：建立 revision lineage 核心

**檔案**

- Create: `tools/toefl_tracker/lineage.py`
- Create: `tests/test_lineage.py`
- Modify: `tools/toefl_tracker/reports.py`
- Modify: `tools/toefl_tracker/audit.py`

**RED tests**

- 直接 revision、revision-of-revision 與七輪鏈都能找到 root formal original。
- 遺失 parent、cycle、cross-modality parent、非 revision parent 與時間倒流都被拒絕。
- 對 learner fixture 的 Discussion chain，摘要包含 R1–R7，而不是只有 R1。
- 報告分別顯示 first-round outcome 與 latest-round outcome；不可將多輪 outcomes 合成單一 resolution rate。

**實作**

1. 建立 immutable attempt graph 與 `lineage_summary()`。
2. 讓 audit 用同一個 graph 檢查鏈結。
3. 在 report 中新增 `Revision chains` 區塊。
4. 保留舊 report 格式的其他欄位；替換具誤導性的 direct-child-only revision statistic。

**驗證**

```bash
python3 -m pytest tests/test_lineage.py tests/test_reports.py tests/test_audit.py -q
python3 -m pytest -q
python3 tools/rebuild_reports.py --root <fixture-root> --modality writing
python3 tools/validate_tracker.py --root <fixture-root>
```

## Task 2：建立能力群組與 Discussion 因果鏈練習規格

**檔案**

- Create: `standards/ets-2026/writing-skill-families.yaml`
- Create: `tools/toefl_tracker/families.py`
- Create: `tests/test_writing_families.py`
- Modify: `tools/toefl_tracker/reports.py`
- Modify: `.agents/skills/toefl-writing-coach/SKILL.md`
- Modify: `.agents/skills/toefl-writing-coach/references/discussion-feedback.md`

**RED tests**

- `IDEA-DEVELOPMENT` 由 `DISCUSSION-ELABORATION` 與 `DISCUSSION-SUPPORT` 組成。
- family summary 對每個 hit 保留 atomic code、attempt ID 與 exact excerpt。
- 相同 family 的不同 member 出現在兩篇 formal originals 時，報告顯示 recurring family signal。
- Email 專屬 family 不會出現在 Discussion-only training plan。
- discussion skill 的 drill assignment 要求 claim → mechanism → outcome → link，且不提供完整範文。

**實作**

1. 加入版本化 family mapping；不修改 `writing-error-taxonomy.md` 的 atomic codes。
2. 建立 pure family aggregation function。
3. 在 reports 新增 `Skill families` 區塊。
4. 在 Discussion reference 加入 bounded causal-chain drill contract。

**驗證**

```bash
python3 -m pytest tests/test_writing_families.py tests/test_reports.py tests/test_writing_skill_contract.py -q
python3 /Users/twinb00599242/.codex/skills/.system/skill-creator/scripts/quick_validate.py .agents/skills/toefl-writing-coach
```

## Task 3：targeted drill 註冊與 mastery engine

**檔案**

- Create: `tools/toefl_tracker/mastery.py`
- Create: `tools/register_writing_drill.py`
- Create: `tests/test_writing_mastery.py`
- Create: `tests/test_register_writing_drill.py`
- Modify: `tools/toefl_tracker/validation.py`
- Modify: `tools/toefl_tracker/register.py`
- Modify: `tools/toefl_tracker/reports.py`
- Modify: `tools/toefl_tracker/audit.py`

**RED tests**

- 有效 drill 必須有 source formal original、target code/family、item totals、correct count 與 evidence。
- drill 不增加 formal count，不出現在 score dashboard，也不觸發三篇 milestone。
- 未達兩組各 80% 的 drill 不得標記 `provisional`。
- 至少 3 個機會、0 個目標事件的新 formal original 才能標記 `transferred`。
- 兩篇合格新 formal originals 才能標記 `controlled`；之後再犯改為 `relapsed`。
- 0 opportunities 不能視為成功控制。

**實作**

1. 為 `targeted_drill` 實作獨立 registration gate 與 CLI；不可假借 formal writing CLI。
2. 在 attempt artifact 中寫入 drill metadata 與 learner evidence。
3. 實作純 mastery calculator；輸出 `mastery.md`。
4. Audit 驗證 drill reference、分數範圍、evidence binding 與 derived mastery。

**驗證**

```bash
python3 -m pytest tests/test_writing_mastery.py tests/test_register_writing_drill.py tests/test_audit.py -q
python3 -m pytest -q
python3 tools/rebuild_reports.py --root <fixture-root> --modality writing
python3 tools/validate_tracker.py --root <fixture-root>
```

## Task 4：training plan 與 coach workflow

**檔案**

- Create: `tools/toefl_tracker/training_plan.py`
- Create: `tests/test_training_plan.py`
- Modify: `tools/toefl_tracker/reports.py`
- Modify: `.agents/skills/toefl-writing-coach/SKILL.md`
- Modify: `.agents/skills/toefl-writing-coach/references/writing-error-taxonomy.md`
- Modify: `tests/test_writing_skill_contract.py`
- Create: `tests/skill-evals/writing/adaptive-mastery-scenarios.md`
- Create: `tests/skill-evals/writing/adaptive-mastery-evaluation.md`

**RED tests**

- current learner fixture ranks `GRAM-CLAUSE` first.
- it exposes `IDEA-DEVELOPMENT` with both Discussion evidence records.
- after two unresolved revisions, plan recommends a bounded drill plus a new formal transfer test, not another compulsory full revision.
- output has at most two active targets and retains task-route isolation.
- a coach first-round response still has at most three priorities and no complete model answer.

**實作**

1. 以 status、formal-record coverage、severity、family signal、lineage length 產生 deterministic rank。
2. 產生 derived `tracker/writing/training-plan.md`。
3. 增加 skill 指令：progress request 讀 plan；revision round 2 後推薦切換；discussion drill 使用因果鏈格式。
4. 加入 fresh-context skill evaluation，確認不洩漏完整範文或把 drill 當正式分數。

**驗證**

```bash
python3 -m pytest tests/test_training_plan.py tests/test_writing_skill_contract.py tests/test_reports.py -q
python3 /Users/twinb00599242/.codex/skills/.system/skill-creator/scripts/quick_validate.py .agents/skills/toefl-writing-coach
python3 -m pytest -q
```

## Task 5：安全套用到現有資料並驗收

**檔案**

- Create: `tests/test_real_writing_adaptive_tracker.py`
- Modify: generated derived files under `tracker/writing/` only after fixture rehearsal succeeds
- Create: ignored process note under `.superpowers/sdd/` recording commands and results

**步驟**

1. 複製目前 tracker 到 temporary fixture；不得先修改主工作區資料。
2. 執行 rebuild 與 validator，檢查新 reports、`mastery.md`、`training-plan.md`。
3. 斷言 learner tracker 的既有 4 formal originals、13 revisions、原始分數與 events 完全不變。
4. 斷言計畫第一名為 `GRAM-CLAUSE`，並列出 `IDEA-DEVELOPMENT` 的兩筆 formal evidence。
5. 在使用者同意後才將「可重建的衍生檔」套用到主工作區；原始紀錄不 staged、不覆寫。

**最終驗證**

```bash
python3 -m pytest -q
python3 tools/rebuild_reports.py --root . --modality writing
python3 tools/validate_tracker.py --root .
git diff --check
git status --short
```

## 完成條件

- 現有數據能正確顯示 clause 與 idea-development 的優先原因。
- 多輪 revision 不再被 direct-parent-only 的報表邏輯截斷。
- drill、mastery 與 training plan 均可重建、可驗證、不可偽造 formal progress。
- 第一輪寫作回饋的 ETS 邊界與迭代規則完全維持。
