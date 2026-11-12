# Agent customization method

One sentence: **say what is wanted and what counts as passing before building; let programs do the numbers; test against real historical cases until everything matches before delivering.**

## Ten stages
Each stage has a deliverable; you may enter the next stage only after the pass criterion is met.

| # | Stage | Deliverable (in the project folder) | Pass criterion |
|---|---|---|---|
| 0 | Project brief | `deliver/0-brief.md` | Who the client is, the pain, what success looks like; the owner agrees to do it |
| 1 | Requirements | `deliver/1-requirements.md` | What to do and not to do, inputs, outputs, who uses it, how often; **the client confirms** |
| 2 | Acceptance criteria | `deliver/2-acceptance.md` | Every line can be checked by a test; the client confirms |
| 3 | Client environment | `deliver/3-environment.md` | Operating system, may they install software and run programs, which platform, may data leave the premises |
| 4 | Materials and confidentiality | `deliver/4-materials.md` | Materials gathered and sources logged; originals read-only; how sensitive data is handled |
| 5 | Test set | `tests/` + `deliver/5-test-set.md` | Historical inputs with known answers, covering at least a normal case, a changed-format case and an error case |
| 6 | Build | the delivery package (instructions + program + templates) | Numbers come only from the program; definitions locked; each adjustment has basis and arithmetic |
| 7 | Replay acceptance | `deliver/7-acceptance-record.md` | The program runs the whole test set by itself and all pass; rerun after every new version |
| 8 | Trial install at the client | `deliver/8-trial-install.md` | A real run on the client's computer (or an identical setup) |
| 9 | Delivery | version number, user guide, update notes | The client can use it alone |
| 10 | Operations | `deliver/10-operations.md` | Collect feedback, ship new versions, upgrade the lessons file, monthly review |

## Rules that run through every stage
1. Facts, inferences and open questions are written apart; an inference is locked only after the client's material confirms it.
2. Anything that goes outside never mentions AI, tools or models; a program checks before output.
3. Every adjustment, merge or reclassification produces a line of detail: original figure, result, arithmetic, basis (file + row). No basis, no output.
4. Log cost: owner time and number of sessions per stage in `deliver/hours.md`, for later pricing.
5. Stage status goes on the first line of the project README "Current status": `Stage: N-name`.
6. **Ask the client as little as possible.** Tag each open question: [self-answer] the client's own material can answer it, close before stage 4; [ask on use #id] the assistant asks in one sentence during use and records the answer; [ask before start] truly must be asked first, aim for zero. If a definition that changes the numbers is still open, the program must not issue a final result.
7. **Help-style projects** (do not chase the client for materials): stages 4-5 use what you already have; the assistant asks for the client's materials at first use and runs a "first calibration" - recompute the client's last month and compare line by line with their final version. Until it matches, output is marked "trial calculation". The assistant may change only its settings file (definitions, name lists, format mapping), and only with the client's nod. After delivery the client does not need to come back to the builder.

## Fictional case: "Maple Bakery stock helper"
Not a real client; shows what each stage produces.

- 0 Brief: Ms. Lin runs a small bakery and spends two evenings a month reconciling flour, butter and sugar stock. Success = the monthly stock sheet is ready in 10 minutes and matches her own final sheet. Owner agrees.
- 1 Requirements: input is the supplier's CSV and her count sheet (xlsx); output is one stock sheet plus a "differences" list. Not doing: ordering, prices. Open: [ask on use #1] what counts as spoiled stock. She confirms on 3 Nov.
- 2 Acceptance: "March replay: every line of the stock sheet equals her final March sheet"; "a wrong unit (kg vs g) is flagged, not guessed".
- 3 Environment: Windows laptop, may run Python, data may stay on the laptop, uses a shared online sheet.
- 4 Materials: three past months of CSVs and count sheets, logged with source; the originals are copied read-only.
- 5 Test set: March (normal), May (supplier changed column order), June (a missing count row = error case).
- 6 Build: `stock.py` computes; the assistant's instruction text only calls it; each adjustment appears in `differences.md` with arithmetic.
- 7 Replay: `python stock.py selftest` runs all three months, prints PASS/FAIL per line. Rerun after every change.
- 8 Trial install: run on Ms. Lin's laptop; record what she had to click.
- 9 Delivery: v1.0, one-page guide, update notes.
- 10 Operations: she reports the first real month; spoilage definition added to the lessons file with her nod; monthly review.

## Templates to copy into each new project
Brief, requirements, acceptance table, environment survey, test-set table (see the headings above); each file starts with the owner's confirmation record: "confirmed" + date.
