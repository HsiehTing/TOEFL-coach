# Writing Coach Forward-Test Results

## Provenance

- Three initial ephemeral Codex agents received only their assigned scenario, its raw artifact, and the writing skill. They were denied the evaluation contract and baseline results.
- A fourth fresh ephemeral Codex agent reran only Scenario C after the minimal, evidence-driven skill correction below.

## Initial Scenario A — Raw output

```text
作答條件：完整 Academic Discussion 作答；時間與協助情況未提供。  
結果標示：**模擬任務分數**（非完整 Writing section band）。

**模擬分數：3/5（信心：中等）**  
你的立場大致清楚，並有相關例子；但開頭的雙重否定讓核心觀點與後文衝突，且論證還可以更具體。

你目前做到的地方：

- 有回應題目，也提出「個人作業有時更好」的立場。
- 有說明小組合作的優點與缺點。
- 有使用個人經驗支持觀點。

為什麼還沒到 4 分：

- 最關鍵問題是立場不一致。第一句的意思其實是「我認為小組合作總是有效」，但後面卻在論證它並非總是有效。
- 例子提到「不公平」，但沒有具體說明發生了什麼、如何影響學習或評量。
- 有一個明顯的連接詞結構錯誤，影響句子控制。

| 原文證據 | 問題 | 類別 | 優先度 |
|---|---|---|---|
| “I do not think group work is not always effective.” | 雙重否定使論點變成「小組合作總是有效」，與後文相衝突。 | `DISCUSSION-POSITION`, `GRAM-NEGATION` | must-fix |
| “Although group projects can teach communication, but some students do most of the work.” | `Although` 不能和 `but` 同時用來連接這個句子。 | `GRAM-CLAUSE` | should-fix |
| “It was useful, but the experience was not fair.” | 「不公平」太籠統；請說明哪位成員做了什麼，以及這如何影響學習或成績。 | `DISCUSSION-ELABORATION` | should-fix |

本輪三個重點：

1. 先把第一句改成與全文一致的立場：小組合作**不一定**總是有效。  
2. 修正 `Although ... but ...` 結構。  
3. 把你的團隊報告例子補成 1–2 句具體細節與結果。

請改寫為 **100–120 字**：保留「小組合作有價值，但不應用於每一個重大成績」這個立場；修正第一句；並具體說明上學期報告中不公平分工如何影響學習或教師評量。先完成你的版本，我再逐句檢查並給你高分範例。
```

## Initial Scenario B — Raw output

```text
作答條件：正式原始作答；計時與協助情況未知。  
結果標示：模擬任務分數（依 ETS Email rubric）— **2/5**，信心高。

你的目的和生病原因清楚，但缺少兩個必要資訊，且語氣對教授不合適。

目前程度：你有說明原因（“I was sick this weekend”），也表達需要延期；句子大致清楚。  
尚未達下一級的主因：沒有提出具體新截止日期或補進度計畫，而且 “You must give me more time” 太命令式。

| 證據 | 問題 | 優先度 |
|---|---|---|
| “I will finish it when I can.” | 沒有提出明確的新繳交日期，也沒有說明如何趕上進度。`EMAIL-MISSING-POINT` | must-fix |
| “Hey professor,” | 對教授的稱呼過於隨意。`EMAIL-REGISTER` | should-fix |
| “You must give me more time” | 命令式語氣不禮貌，請求方式無效。`EMAIL-POLITENESS`、`EMAIL-ACTION` | must-fix |

改善重點：

1. 寫出原截止日後兩天的**確切日期**，不要只說 “when I can”。
2. 加入具體補進度計畫，例如完成哪些部分、何時交稿。
3. 用正式稱呼與禮貌請求語氣。

請改寫成 60–90 字的 email 給 Professor Lee：保留生病原因，明確請求兩天延期、提出新日期與補進度方法，並維持尊重且不命令的語氣。
```

## Initial Scenario C — Raw output

```text
作答條件與結果標示

- 紀錄類型：`formal_original`（第 3 次正式作答）
- 計時／協助：未知
- 結果標示：`diagnostic_only`；提供的資料不足以評定模擬任務分數。

追蹤結果

`GRAM-ARTICLE`：正式作答共 3 次、3 個機會、3 次錯誤（100%）。

| 類型 | 證據 | 判定 |
|---|---|---|
| should-fix | `a effective method` | 應為 `an effective method`。這是冠詞選擇錯誤。 |

你能在 Formal 2 的 revision 寫出 `an important reason`，表示你知道規則；但 Formal 3 又出現相同錯誤，代表規則尚未穩定地用在正式作答中。該 revision 會保留並連結至 Formal 2，但不計入正式作答次數或錯誤率。

已達三筆正式作答門檻：建立 `GRAM-ARTICLE` 的共同語言問題報告。

本輪唯一優先目標：名詞片語開頭先判斷下一個「聲音」是否為母音音，`effective` / `important` / `useful` 分別使用 `an` / `an` / `a`。

改寫練習：請各寫一句，分別正確使用 `a useful …`、`an important …`、`an effective …`。
```

## Witnessed failure and correction

Initial Scenario C counted the three formal originals, excluded the clean revision, and preserved the exact excerpt, but it never emitted a `historical_status`; therefore it did not meet the required `persistent` classification criterion.

The minimal correction added this binding output instruction to `SKILL.md`:

> For a recurrence or progress request, classify each counted code from ordered `formal_original` records with the deterministic tracker status rules. Explicitly output the resulting `historical_status`; revisions and targeted drills do not change it.

This makes the missing tracker-derived field mandatory without weakening conditional route loading or encoding Scenario C's article example.

## Rerun Scenario C — Raw output

```text
結果標示：diagnostic_only  
歷史狀態：`persistent`

`GRAM-ARTICLE` 在三次 `formal_original` 中皆出現（3/3）；第二次作答的 revision 不計入正式紀錄，不能消除重複錯誤狀態。

- should-fix｜`a effective method` → `an effective method`

下一次正式作答前，先檢查每個可數單數名詞前的冠詞：母音「音」開頭用 `an`，例如 `an effective method`。
```

## Final evaluation

### Scenario A

- PASS — Labels the 0–5 result as a simulated task score: says「模擬任務分數」and 3/5.
- PASS — Explains current and next level: states current strengths and why the work has not reached 4.
- PASS — Gives no more than three priorities: provides exactly three numbered priorities.
- PASS — Does not provide a full model answer before revision: gives bounded revision instructions only.
- PASS — Separates must-fix, should-fix, and polish: the evidence table labels the applicable must-fix and should-fix levels; no unsupported polish issue is invented.

### Scenario B

- PASS — Uses the Email route: evaluates an email to Professor Lee rather than discussion contribution.
- PASS — Evaluates purpose, missing content, register, politeness, and action formulation: covers extension purpose, date and plan omissions, greeting, command tone, and request wording.
- PASS — Does not evaluate contribution to classmates: no discussion-contribution judgment appears.

### Scenario C

- PASS — Counts only formal originals: rerun identifies 3/3 `formal_original` records.
- PASS — Classifies the article issue as persistent: rerun explicitly outputs `historical_status` as `persistent`.
- PASS — Does not use the clean revision to mark the issue controlled: says the revision does not erase the repeated-error status.
- PASS — Adds an exact source excerpt to every counted event: records `a effective method` with its exact revision.
