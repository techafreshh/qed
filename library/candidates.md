# Paper library: sourcing and vetting report (pre-freeze note)

QED validates and demos against a frozen library of pre-vetted papers with
recorded expected verdicts (PRD §10). The library is the validation set
**and** the demo set. This note records what was frozen, what was considered
and rejected, and the rules every manifest follows.

## Frozen set (4 manifests, all under `library/papers/`)

| # | Manifest | Paper | Expected verdict | Data | License note |
|---|----------|-------|------------------|------|--------------|
| 1 | `card_krueger_1994_minwage.yaml` | Card & Krueger (1994), minimum wage and fast-food employment in NJ/PA | REPLICATED | CSV, 25,960 bytes, commit-pinned GitHub raw URL | MIT (repo LICENSE; upstream: Card's Berkeley data page) |
| 2 | `manylabs2_hsee_less_is_better.yaml` | Hsee (1998), less-is-better effect, via Many Labs 2 Slate 2 | REPLICATED | CSV, 43,496,730 bytes, version-pinned OSF download | No machine-readable license on the OSF record; ML2 paper is open access |
| 3 | `manylabs2_zhong_macbeth.yaml` | Zhong & Liljenquist (2006), "Macbeth effect", via Many Labs 2 Slate 2 | FAILED (the famous failure) | Same Slate 2 CSV as #2 | Same as #2 |
| 4 | `reinhart_rogoff_2010_debt.yaml` | Reinhart & Rogoff (2010), as corrected by Herndon, Ash & Pollin (2013) | PARTIAL | CSV, 139,342 bytes, version-pinned Zenodo record file | AGPL-v3 as listed on the Zenodo record; authoritative package is HAP record 4017423 |

Verdict mix: 1 FAILED + 2 REPLICATED + 1 PARTIAL. Every dataset is a plain
CSV readable with `pandas.read_csv`, under 100MB, and every estimator is a
t-test/ANOVA/OLS or bucketed-means analysis re-implementable in statsmodels
in well under 5 minutes of sandbox time. Every manifest records its dataset
URL, sha256, license note, estimator spec, reported numbers, and the expected
verdict **with the source of that expectation** (original paper statistics
plus the recorded replication outcome, both cited in-manifest).

### Per-paper vetting

- **Card & Krueger (1994).** The canonical difference-in-differences study.
  Data ergonomics are ideal: 410 restaurants x 2 waves in long form
  (`nj`, `d`, `d_nj`, `fte`, `demp`, ...). The pinned CSV reproduces the
  headline exactly (NJ-minus-PA mean employment change +2.75 vs published
  +2.76, i.e. matching at reported rounding). Estimator: DiD via OLS.
  Runtime: seconds. This is the clean-replication anchor.
- **Hsee (1998), via Many Labs 2.** Famous judgment-and-decision-making
  effect with a textbook-simple estimator (two-sample t-test on generosity
  ratings, columns `hsee1.1`/`hsee2.1`). Original d=0.69 vs ML2 d=0.78
  (N=7,646) — same sign, same significance, closely matching magnitude.
  Second clean replication.
- **Zhong & Liljenquist (2006), via Many Labs 2.** The "Macbeth effect"
  (*Science*, 2006) is a canonical replication-crisis failure: original
  d=1.02 (N=27) vs ML2 d=0.00, p=0.91 (N=7,001). Estimator: ANOVA/OLS on
  cleansing-product desirability (`zhon.dv.*` by `zhon1.1`/`zhon2.1`).
  Shares the Slate 2 file with #2, so no new download is introduced.
- **Reinhart & Rogoff (2010) / Herndon-Ash-Pollin (2013).** The famous
  spreadsheet-error correction: headline -0.1% mean growth above 90%
  debt/GDP becomes +2.2% after fixing coding errors, selective exclusions,
  and unconventional weighting. Directional pattern across buckets survives
  while the headline magnitude does not — the rubric's PARTIAL case.
  Estimator: OLS / bucketed means of growth by debt ratio.

## Considered but rejected

- **Many Labs 2 "Stroop effect".** Many Labs 2 contains no Stroop study
  (verified against the project's Included Effects list: 13 Slate-1 + 15
  Slate-2 effects, none by Stroop). Replaced with the Hsee effect from the
  same verified Slate 2 file.
- **Bem (2011) precognition.** The famous failure of first choice, but no
  stable public CSV of the raw data could be located: the author's site is
  defunct, and searches across Rdatasets, JASP's data library, Zenodo,
  Dataverse, and GitHub found no verifiable host. A manifest whose bytes
  cannot be pinned is worse than a different failure whose bytes can, so
  Bem was replaced with the Zhong "Macbeth" failure, whose replication
  statistics are documented in the ML2 paper itself.
- **Tversky & Kahneman (1981) framing, via Many Labs 2.** Verified present
  in Slate 2 with a decisive same-direction replication (OR=2.06, N=7,228),
  but at less than half the original magnitude (OR=4.96) — a PARTIAL under
  the rubric's ±10% rule. Left out to keep the freeze at four crisp
  manifests; natural first addition for a later lap.
- **ML2 `OSFdata.zip` (577MB).** Over the 100MB cap; the per-slate CSVs are
  used instead.
- **Stata-only chains.** Excluded on sight per PRD §10 (e.g. the
  Herndon-Ash-Pollin `.dta` sources, Card's `public.dat` fixed-width
  bundle). Every frozen dataset is a plain CSV.
- **Datasets over 100MB, licensed software outputs, and anything needing
  redistribution.** Nothing is vendored into this repo.

## Repo-wide data policy (PRD §9-§10)

- **No dataset redistribution.** The repo stores URLs and hashes only, never
  data bytes. Every `license` field records what the host states (or that
  the host states nothing, with the date checked).
- **Fetch-and-cache with sha256 pinning.** A replay run downloads each
  `dataset_url` once, checks the sha256, then works from the local cache.
  A hash mismatch is a build error, never a silent substitution.
- **Pinning mechanics.** GitHub raw URLs are pinned by commit SHA
  (immutable even if the branch moves). OSF downloads are pinned with
  `?version=1` (both ML2 slates are single-version files). Zenodo files are
  addressed under a version-specific record. Hashes were computed from the
  exact bytes served on 2026-10-28 and cross-checked against host-reported
  checksums where available (OSF file metadata).
