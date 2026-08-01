# Speaking Coach Forward-Test Results

## Provenance

- Three initial independent ephemeral Codex agents each received only their assigned scenario, its raw artifact, and the speaking skill. They were denied the evaluation contract and baseline results.
- After the first witnessed failure, fresh ephemeral agents reran Scenarios B and C with the general dimension-coverage correction. They were denied the evaluation contract and baseline results.
- After the second witnessed failure, a fresh ephemeral agent reran only Scenario B with the token-comparison safeguard. It was denied the evaluation contract and baseline results.
- The raw outputs below are preserved verbatim from `/private/tmp/toefl-speaking-forward-{a,b,c}.md`, `/private/tmp/toefl-speaking-forward-{b,c}-rerun.md`, and `/private/tmp/toefl-speaking-forward-b-rerun2.md`.
- Every run is evaluated in its own stage. Later corrections do not retroactively convert an earlier failed criterion into a pass.

## Initial Scenario A — Raw output

```text
目前無法提供發音分數：只有文字轉錄，沒有可判斷發音的音訊；且以下角色未確認，不能正式評估。

- 00:28–00:31：「Why is that environment helpful?」是考官嗎？
- 00:32–00:35：「It helps me focus.」是你的回答嗎？

請直接回覆「兩段皆是」或更正角色；確認後我會給你 `diagnostic_only` 的發音診斷，不會當成 TOEFL Speaking section 分數。
```

### Initial Scenario A evaluation — 3/3

- PASS — Does not formally score before examiner/learner mapping is complete: it says a pronunciation score cannot yet be provided.
- PASS — Identifies the ambiguous segments and asks only for their confirmation: it names 00:28–00:31 and 00:32–00:35 and requests a direct role confirmation or correction.
- PASS — Does not label distortion, low volume, or clipping as pronunciation errors: it makes no such diagnosis.

## Initial Scenario B — Raw output

```text
檔案品質：未提供原始音檔，無法判定音量、失真或個別音素；以下依逐字稿、時間戳與你提供的重音描述診斷。題目與作答者配對已完整（第 1–7 題）。

`diagnostic_only`｜信心：高（重述正確性）；中（重音）
整體判斷：你能清楚重述大部分內容，但第 1–3 題漏掉功能詞，第 4–5 題缺乏重音變化。

你目前的表現：
- 第 6、7 題完整且可理解，是穩定的正向證據。
- 第 1–3 題保留了主要內容詞，但省略冠詞、介系詞或助動詞，會降低 Listen and Repeat 的逐字重建準確度。
- 第 4–5 題字詞完整，但平坦重音讓句子較不自然，也可能使關鍵資訊不夠突出。

尚未到下一層表現的原因：高品質重述需要每個詞都保留，並以自然句重音讓聽者容易抓到關鍵資訊；目前這兩點尚未穩定。

必須修正：
- 00:05–00:09｜`LR-OMISSION`：漏掉 **The**、**on**。
- 00:15–00:20｜`LR-OMISSION`：漏掉 **your**、**the**。
- 00:26–00:30｜`LR-OMISSION`：漏掉 **can**。

應修正：
- 00:36–00:41｜`SPK-STRESS`：所有字詞都有，但句重音過平；請凸顯主要資訊詞。
- 00:47–00:53｜`SPK-STRESS`：所有字詞都有，但句重音過平；讓主要動詞與名詞比功能詞更突出。

潤飾：
- 00:59–01:05、01:11–01:18｜無明顯問題；保持目前的完整度與可理解度。

本輪三個重點：
1. 不漏讀短功能詞：冠詞、介系詞、助動詞、所有格。
2. 聽完後先在心中確認句首、句中、句尾的短詞。
3. 用較清楚的重音凸顯關鍵名詞、動詞與時間資訊。

請重錄第 1–5 題：每題聽完後一次完整重述，不要逐字停頓；第 1–3 題特別確認短功能詞完整，第 4–5 題讓關鍵資訊詞有較明顯重音。
```

### Initial Scenario B evaluation — 3/4

- PASS — Treats all seven items as one formal session: it confirms the complete item 1–7 pairing and gives one overall judgment.
- PASS — Measures sentence reconstruction accuracy and intelligibility: it correctly identifies all five omitted tokens and uses items 6–7 as accurate, intelligible positive controls.
- FAIL — Uses omission, addition, substitution, word order, stress, rhythm, and intonation evidence: it reports omission and stress but silently omits addition, substitution, word order, rhythm, and intonation.
- PASS — Does not score idea development or Interview elaboration: it stays within repetition accuracy and speech delivery.

## Initial Scenario C — Raw output

```text
錄音品質：未提供可檢查的音檔，因此無法評估發音、語速與停頓；四題的考官題目與你的回答對應清楚。

結果：`diagnostic_only`（中等信心）。這不是官方 TOEFL Speaking section band；單一四題練習無法換算官方 1–6 分。依 2026 標準（最後驗證：2026-07-31），你的內容整體可理解，但 Q2、尤其 Q3 的發展不足。

你目前的優點是四題都直接回答問題；Q1 有具體例子，Q4 有兩項可行建議和結果。主要限制是部分回答太短，沒有充分解釋或具體細節，讓你的想法顯得簡單。

尚未到下一表現層級的原因：你需要在每題穩定提供「主張＋原因／例子＋結果」。Q3 目前幾乎沒有描述事件、改變原因或結果。

必須修正

- 00:54–01:05｜`INTERVIEW-ELABORATION`：**“I changed it. It was better.”** 太籠統。說明你原本的計畫、為何改變、改成什麼，以及結果。
- 00:34–00:46｜`SPK-GRAMMAR`：**“I prefer alone.”** 改為 **“I prefer studying alone.”**

應修正

- 00:34–00:46｜`INTERVIEW-ELABORATION`：**“Other people sometimes talk too much”** 後面加一個個人例子或學習結果。
- 00:54–01:05｜`INTERVIEW-COHERENCE`：用時間順序連接內容，例如 **“At first…, but then…, so…”**。

潤飾

- 01:13–01:29｜**“prevent small problems becoming serious”** 可改為更自然的 **“prevent small problems from becoming serious.”**

優先目標：

1. 每題至少加入一個具體原因、例子或結果。
2. 用完整結構回答：觀點 → 細節 → 結果。
3. 修正 **“prefer alone”** 為 **“prefer studying alone.”**

請重錄 Q2 和 Q3，每題 20–30 秒。Q2 要加入一個真實例子；Q3 要清楚包含「原計畫、改變原因、新計畫、結果」。我會再依這三個目標比較你的進步。
```

### Initial Scenario C evaluation — 4/5

- PASS — Treats all four questions as one formal session: it confirms the four mappings and evaluates the set together.
- PASS — Labels the result diagnostic rather than official task or section score: it uses `diagnostic_only` and explicitly rejects an official section-band conversion.
- FAIL — Evaluates directness, relevance, elaboration, coherence, grammar, vocabulary, fluency, prosody, and intelligibility: it covers directness, elaboration, coherence, grammar, and some unavailable audio dimensions, but silently omits explicit relevance, vocabulary, and prosody coverage.
- PASS — Gives no more than three priorities: it gives exactly three.
- PASS — Does not provide four complete model answers before the learner re-records: it gives local corrections and a bounded Q2/Q3 re-recording task.

## Witnessed failure 1 — Silent dimension omission

The initial Scenario B output contains exact omission and stress findings but never names addition, substitution, word order, rhythm, or intonation. The initial Scenario C output says `無法評估發音、語速與停頓` and discusses several content dimensions, but never explicitly disposes of relevance, vocabulary, or prosody. The witnessed rationalization was to mention only observed issues, and to let absent or audio-dependent dimensions disappear instead of marking them as no issue found or unavailable.

The smallest general correction added one structural output slot to `.agents/skills/toefl-speaking-coach/SKILL.md`:

> Across these parts, name every dimension in the selected route's `Required evidence` and mark it as an observed strength, observed issue, no issue found, or unavailable; never silently omit a listed dimension.

This correction binds every route to its own existing `Required evidence` without adding Scenario B or C facts to the skill.

## First rerun Scenario B — Raw output

```text
檔案品質：未提供音檔，無法判定錄音品質、音段發音、節奏或語調。
說話者配對：依你提供的 source／learner 標示與時間戳，配對已確認。

`diagnostic_only`｜信心：中等
整體判斷：你能重複核心內容，但功能詞遺漏與平板重音使 Listen and Repeat 的完整度和自然清晰度尚不穩定。

目前表現的依據：

- 來源句重建：第 1–3 題有 6 個功能詞遺漏；第 4–7 題未見遺漏、添加、替換或語序錯誤。
- 詞語辨識與可懂度：第 6、7 題準確且可懂，是明確優點；第 1–5 題的實際可懂度因無音檔無法確認。
- 音段發音：無音檔，無法評估。
- 重音、節奏、語調：第 4、5 題有平板重音問題；節奏與語調無法由文字稿確認。
- 準確題目證據：第 6、7 題完整、準確且可懂。

你還沒到下一個表現層次，主要不是內容詞不會，而是短小但重要的功能詞沒有被完整保留，且句子重音沒有凸顯關鍵資訊。這會讓聽者較難確認你是否完整重建原句。

必須修正：

- `LR-OMISSION`｜00:05–00:09：第 1 題漏掉 **“The”**、**“on”**。
- `LR-OMISSION`｜00:15–00:20：第 2 題漏掉 **“your”**、**“the”**。
- `LR-OMISSION`｜00:26–00:30：第 3 題漏掉 **“can”**、**“a”**。

應修正：

- `SPK-STRESS`｜00:36–00:41：第 4 題所有字都保留，但重音過於平均；要讓 **science lecture**、**moved**、**Friday** 更突出。
- `SPK-STRESS`｜00:47–00:53：第 5 題所有字都保留，但重音過於平均；要讓 **advisor**、**explain**、**new registration process** 更突出。

潤飾：

- 第 6 題（00:59–01:05）與第 7 題（01:11–01:18）準確且可懂；請維持這種完整重複的穩定度。

本輪優先目標：

1. 每句先抓功能詞：冠詞、介系詞、助動詞、所有格。
2. 不要每個字都同樣重；只強調主要名詞、動詞與關鍵時間資訊。
3. 重複後快速檢查句首、介系詞和冠詞是否都還在。

請只重錄第 1–5 題：每題先完整重複一次，再錄第二次；第二次特別確認功能詞與句子重音。
```

### First rerun Scenario B evaluation — 3/4

- PASS — Treats all seven items as one formal session: it evaluates the whole item 1–7 set and assigns one bounded re-recording task.
- FAIL — Measures sentence reconstruction accuracy and intelligibility: intelligibility is addressed, but reconstruction evidence is inaccurate. It reports six omissions and says item 3 omitted `can` and `a`, although both source and learner contain `a study room`; the exact comparison supports only five omissions in total.
- PASS — Uses omission, addition, substitution, word order, stress, rhythm, and intonation evidence: it reports omissions and stress, explicitly finds no addition, substitution, or word-order issue, and marks rhythm and intonation unavailable.
- PASS — Does not score idea development or Interview elaboration: it remains on the Listen and Repeat route.

## First rerun Scenario C — Raw output

```text
檔案品質與對應：未提供可播放音檔，因此無法確認音量、雜訊、削波與發音表現；題目與答題者對應依你提供的逐字稿確認，Q1–Q4 均為高信心。

**diagnostic_only｜文字證據信心：中等；口語聲音證據：無法判定。**
這不是官方 TOEFL Speaking band，也不能由單一訪談組換算完整口說 section band。這組作答的內容基礎不錯，但 Q3 的展開明顯不足。

你的表現目前落在：能直接回答並用簡單英文表達想法，但需要更穩定地補上具體細節與清楚的事件發展。

距離下一個表現層級的差距在於：每題都要讓聽者清楚知道「為什麼、怎麼做、結果如何」，尤其不能只用 *it* 或 *better* 代替關鍵資訊。

必要證據：

- 直接回答與相關性：觀察到優勢。Q1、Q2、Q4 都直接回答；Q3 也相關，但內容太少。
- 解釋／理由／例子／細節：觀察到問題。Q1 有理由與例子；Q2 有理由；Q4 有兩項建議與結果；Q3 缺少具體事件細節。
- 連貫與組織：觀察到問題。Q1、Q2、Q4 清楚；Q3 的改變過程不完整。
- 文法與字彙：觀察到問題。多數句子清楚，但 Q2、Q3、Q4 有可改善的表達。
- 流暢度、停頓與自我修正：無法判定，需音檔。
- 發音、重音、語調、韻律與可理解度：無法判定，需音檔。

必須修正：

- 00:54–01:05｜`INTERVIEW-ELABORATION`：`Last month I had two exams. I changed it. It was better.`
  沒有說明原本怎麼安排、改成什麼、為何需要改、結果是什麼。

- 00:54–01:05｜`INTERVIEW-COHERENCE`：`I changed it. It was better.`
  *it* 和 *better* 指涉太模糊，聽者無法掌握你的故事。

應改善：

- 00:34–00:46｜`INTERVIEW-ELABORATION`：`Other people sometimes talk too much, so I cannot focus.`
  理由清楚，但補一個小例子會更有說服力，例如小組讀書時如何分心。

- 01:13–01:29｜`SPK-GRAMMAR`：`prevent small problems becoming serious`
  建議說：`prevent small problems from becoming serious.`

潤飾：

- 00:34–00:36｜`I prefer alone.`
  更自然：`I prefer studying alone.`

優先練習：

1. Q3 使用「情境 → 原計畫 → 新計畫 → 結果」四步驟。
2. 不要用模糊的 *it*、*better*；直接說出你改了什麼與結果。
3. 每題至少補一個具體細節或例子。

請重錄 Q2 和 Q3，每題約 20–25 秒。Q2 加上一個真實例子；Q3 必須清楚交代原計畫、改動原因、新計畫與結果。
```

### First rerun Scenario C evaluation — 5/5

- PASS — Treats all four questions as one formal session: it confirms Q1–Q4 and evaluates the complete set.
- PASS — Labels the result diagnostic rather than official task or section score: it uses `diagnostic_only` and rejects both an official band and full-section conversion.
- PASS — Evaluates directness, relevance, elaboration, coherence, grammar, vocabulary, fluency, prosody, and intelligibility: every dimension is explicitly an observed strength, observed issue, or unavailable.
- PASS — Gives no more than three priorities: it gives exactly three.
- PASS — Does not provide four complete model answers before the learner re-records: it gives local corrections and asks for only Q2 and Q3.

## Witnessed failure 2 — Unsupported token count

The first Scenario B rerun explicitly says `第 1–3 題有 6 個功能詞遺漏` and `第 3 題漏掉 **“can”**、**“a”**`. The raw source is `Students can reserve a study room online.` and the learner response is `Students reserve a study room online.` Both contain `a`; only `can` is omitted in item 3. The supported total is five omissions: `The`, `on`, `your`, `the`, and `can`. The witnessed rationalization was to classify and propagate an apparent difference without first checking the exact source and learner token sequences.

The smallest general correction added this evidence-integrity rule to `.agents/skills/toefl-speaking-coach/references/listen-and-repeat.md`:

> Compare the exact source and learner tokens before classifying or counting any omission, addition, substitution, or word-order difference. Never report a reconstruction difference that the transcripts do not support.

This correction applies to any Listen and Repeat transcript and contains no scenario-specific word or item.

## Final rerun Scenario B — Raw output

```text
檔案品質與對應：未提供音檔，無法判定錄音品質、音段發音、節奏與語調；題目／作答者對應已由逐字稿指定，信心高。

**診斷結果：diagnostic_only（整體信心：中等）**
你能重複較長句子，但功能詞遺漏使原句重建不夠完整；第 4、5 題的重音也需要更清楚。

目前表現的優點：

- 詞彙辨識與可懂度：第 6、7 題準確且可理解。
- 準確題項：第 6、7 題是正向證據。
- 新增、替換、語序：未發現問題。

為什麼還沒到下一個表現層級：Listen and Repeat 要完整重建原句。第 1–3 題共漏掉 5 個功能詞；第 4–5 題雖然字都正確，但重音平坦，會讓關鍵資訊不夠突出。

必須修正：

- 00:05–00:09：漏掉 **“The”** 和 **“on”**。
  Source: “The library opens at eight on weekdays.”
  Learner: “Library opens at eight weekdays.”
- 00:15–00:20：漏掉 **“your”** 和 **“the”**。
  Source: “Please leave your completed form at the front desk.”
  Learner: “Please leave completed form at front desk.”
- 00:26–00:30：漏掉 **“can”**。
  Source: “Students can reserve a study room online.”
  Learner: “Students reserve a study room online.”

應修正：

- 00:36–00:41：所有字都有保留，但句子重音平坦。請讓 **science lecture**、**moved**、**Friday** 更突出。
- 00:47–00:53：所有字都有保留，但句子重音平坦。請讓 **advisor**、**explain**、**registration process** 更突出。

Polish：無。

本輪三個重點：

1. 每次重複前，特別聽冠詞、介詞、代詞與助動詞。
2. 不要為了速度省略短字；先求完整，再求流暢。
3. 用明顯句子重音凸顯內容詞，功能詞較輕但仍要說出來。

請只重錄第 1–5 題。每題先確認所有小字都在，再以自然重音說完整句；第 6、7 題不用重錄。
```

### Final rerun Scenario B evaluation — 4/4

- PASS — Treats all seven items as one formal session: it uses items 1–7 as one diagnostic session and gives one bounded re-recording assignment.
- PASS — Measures sentence reconstruction accuracy and intelligibility: it reports exactly five supported omissions, shows exact source/learner evidence, and identifies items 6–7 as accurate and intelligible.
- PASS — Uses omission, addition, substitution, word order, stress, rhythm, and intonation evidence: it reports omission and stress, finds no addition, substitution, or word-order issue, and marks rhythm and intonation unavailable.
- PASS — Does not score idea development or Interview elaboration: it remains limited to reconstruction and delivery evidence.

## Stage summary

| Stage | Scenario | Result | Preserved status |
|---|---:|---:|---|
| Initial forward test | A | 3/3 | Pass |
| Initial forward test | B | 3/4 | Failed one criterion |
| Initial forward test | C | 4/5 | Failed one criterion |
| After general dimension-coverage correction | B | 3/4 | Failed one criterion |
| After general dimension-coverage correction | C | 5/5 | Pass |
| After token-comparison safeguard | B | 4/4 | Pass |

Initial total: 10/12. First rerun total: 8/9 applicable criteria. Final B-only rerun: 4/4 applicable criteria.
