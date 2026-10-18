# Drug Safety Signal Triage Assistant

A Python tool that helps pharmacovigilance reviewers decide which drug-reaction pairs need a closer look. It reads FDA Adverse Event Reporting System (FAERS) quarterly data, calculates disproportionality statistics, checks the FDA drug label, and assigns each pair to one of three categories with a cited rationale.

**Please note - This tool generates hypotheses for human review. It does not establish causation or make a safety decision.**

## What it does

For a drug and a reaction term, the tool:

1. Loads FAERS quarterly extracts (2021 Q1 onwards) into DuckDB.
2. Keeps the latest version of each case, drops cases FDA has deleted, and counts cases for the pair as a 2x2 table.
3. Calculates the proportional reporting ratio (PRR) and reporting odds ratio (ROR), with 95% confidence intervals and a chi-square statistic.
4. Applies the Evans signal rule (at least 3 cases, PRR of at least 2, and chi-square of at least 4).
5. Fetches the drug's FDA label from the openFDA API (cached locally) and searches the warnings, adverse reactions, and contraindications sections for the reaction term.
6. Assigns one category:
   - **already labelled**: the label mentions the reaction.
   - **new candidate**: the label does not mention the reaction, and the pair meets the Evans rule.
   - **insufficient data**: neither of the above. The rationale states which criterion was not met.

The label check runs first. Every category comes with the statistics and the label passages it was based on.

## What it does not do

- It does not use a language model. Every category follows fixed rules, so each result can be traced to a count, a statistic, or a quoted label passage.
- It does not adjust for age, sex, or time. It does not estimate causation or incidence.
- It does not map brand names to generic names, and it does not handle synonyms. "Vomiting" will not match a label that only says "nausea".

## Requirements

- Python 3.10 or newer
- About 20 GB of free disk space for the full FAERS data and database
- At least 8 GB of RAM. The loader limits DuckDB to 2 GB and two threads.
- An openFDA API key (optional, but it avoids strict rate limits). Set it as the environment variable `OPENFDA_API_KEY`. Never commit the key.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
python -m pytest -q
```

## Usage

### 1. Download FAERS data

```bash
python scripts/download_faers.py
```

This saves each quarter to `data/faers/<quarter>/`. Quarters that are not yet published are reported as not found and skipped.

### 2. Triage one drug-reaction pair

```bash
python -m pharmsignal triage ibuprofen "Nausea"
```

The first run builds `data/faers.duckdb` from the text files, which takes a long time. Later runs reuse that database.

Options:

- `--data-dir` (default `data/faers`)
- `--db` (default `data/faers.duckdb`)
- `--cache` (default `data/openfda`)

### 3. Evaluate against a reference set

Create a CSV with the columns `drug`, `reaction`, and `expected`. The `expected` value must be one of the three categories above.

```bash
python -m pharmsignal.evaluate data/reference.csv
```

This prints overall accuracy and a confusion matrix, and writes the mismatches to `data/mismatches.csv`. Add `--rebuild` to rebuild the database from the text files.

## Project layout

```
pharmsignal/
  faers.py            load FAERS extracts, deleted-case lists, 2x2 counts
  disproportionality.py  PRR, ROR, chi-square, Evans rule
  labels.py           openFDA label fetch with local cache
  retrieval.py        search label sections for the reaction term
  classifier.py       three-way category with cited rationale
  cli.py              triage command
  evaluate.py         compare output with a reference CSV
  schema.py           expected FAERS column layout
scripts/
  download_faers.py   download and unpack FAERS quarters
tests/                unit tests (run without network access)
```

Data files live in `data/`, which is excluded from git.

## Limitations

- **Reporting bias.** FAERS collects spontaneous reports. Counts depend on who reports, and a high count does not mean a drug is more dangerous.
- **Duplicates.** The tool keeps the latest version of each case, but it does not detect duplicate reports from different sources.
- **Name matching.** Drugs are matched by the names in the FAERS `prod_ai` and `drugname` fields. Brand names, misspellings, and combination products may be missed.
- **Reaction matching.** Reactions are matched by exact MedDRA preferred term.
- **Label check.** The label search is a text match. It can miss a mention written differently, and it can count a mention that is only a warning about something else.
- **Thresholds.** The Evans rule thresholds are fixed. The tool does not account for multiple comparisons across many pairs.
- **Rationale text.** The rationale is generated from templates, not written by a person. It describes the rule that was applied, not clinical judgement.

## Evaluation

_To be added: results on the reference set, with the number of pairs and the confusion matrix._

## Status

- [x] FAERS loading and deletion handling
- [x] Disproportionality statistics and Evans rule
- [x] openFDA label fetch with cache
- [x] Label section search
- [x] Three-way classifier with rationale
- [x] Command-line triage
- [ ] Evaluation against reference set
- [ ] Optional MCP server

## Data sources

- FAERS quarterly data: U.S. Food and Drug Administration
- Drug labels: openFDA drug label API

## Disclaimer

This is only a portfolio project. It is not validated for regulatory or clinical use. 

Email - sn.ritika18@gmail.com for any queries!