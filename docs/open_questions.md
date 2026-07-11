# Open Questions — Phase 00

## 100-Dim vs 115-Dim

### Confirmed

1. **Source of 100-dim:** `netStat.py:103` concatenates 4 feature groups (MIstat, HHstat, HH_jit, HpHpstat), each with 5 Lambdas. No Hstat. Total = 15 + 35 + 15 + 35 = **100**.
2. **Source of 115-dim:** The paper defines 115 features. The difference is `Hstat` (Host BW: source IP general sender statistics) = 3 stats × 5 Lambdas = **15 features**, commented out in `netStat.py:74-77`.
3. **get_num_features behaviour:** Returns 100 (not 115), because `getNetStatHeaders` (netStat.py:105-118) never populates `Hstat_headers` in the loop.
4. **UCI dataset:** The official dataset distribution describes 115 statistical features (matching the paper).

### Open

1. **Why was Hstat commented out?** Was it for speed, or because the source-host BW is redundant with other features? The comment "Host BW: Stats on the srcIP's general Sender Statistics" suggests it tracked sender-side bandwidth. Needs paper cross-reference.
2. **C++ vs Python discrepancy:** The paper's results (and C++ impl) may use the full 115. The Python impl uses 100. Does this affect the reported metrics?
3. **UCI CSV column count:** The exact column layout of the official UCI CSV needs to be verified. Does it have:
   - 115 feature columns + 1 label column = 116 total?
   - 115 feature columns including or excluding an index column?
   - The same feature ordering as the Python code's header list?
4. **Feature ordering map:** If UCI features are in a different order than the Python code's internal ordering, direct feed to KitNET would produce incorrect results even after dimension matching.

## UCI Dataset Availability

1. **Download reliability:** Is the UCI dataset currently accessible at the published URL? Need to verify before writing download scripts.
2. **SHA-256 checksums:** Need to record actual checksums after download.
3. **Attack sub-directory assignment:** Can we definitively assign each UCI CSV to one of the 9 attack types? The UCI page mentions 9 attacks but the exact file-to-attack mapping needs verification.
4. **Labels column semantics:** Confirm label encoding (0=benign, 1=attack) and verify no multi-class labels.

## KitNET Input Compatibility

KitNET's input dimension `n` is a **dynamic constructor parameter**
(`KitNET(n, ...)`). The 100-dim and 115-dim are two **separate experiment
tracks**, not a compatibility issue:

- **Track A (PCAP path):** KitNET(n=100) — matches Python AfterImage output
- **Track B (UCI path):** KitNET(n=actual_feature_count) — matches UCI CSV column count

No dimension conversion, padding, or stripping is required.

1. **Normalization compatibility:** dA.py does per-AE online 0-1 norm. UCI CSV may already be normalized or may need pre-normalization. Will the internal normalization handle CSV inputs correctly?
2. **Feature ordering:** Is the UCI column order the same as the Python internal order? Need cross-reference between UCI documentation and `getNetStatHeaders` output.
3. **Label file format:** UCI distributes labels as separate files. Need to verify encoding (0/1 binary) and row-alignment with feature files.

## Paper Parameters

1. **Fixed grace periods:** Exploratory runs use FMgrace=5000, ADgrace=50000 across all 9 attacks (matching example.py). Grace period tuning (if needed) deferred until after baseline results are collected.
2. **maxAE parameter sensitivity:** Paper uses m=10. Deferred to parameter sensitivity analysis phase.
3. **Threshold (phi):** The paper's log-normal threshold method (example.py:55-57) uses RMSEs from the first execution samples. For UCI data where attack may start early, threshold determination method needs clarification from paper.
4. **EER calculation:** The paper reports EER. Exact method (threshold sweep? fixed FPR?) needs extraction from paper.

## Log and Evidence

1. **Previous experiment logs:** The file `Kitsune/初次冒烟测试终端日志.txt` contains the local test run output. It should be sanitized and used as reference for dimension analysis.
2. **Scapy vs tshark:** The previous local test used which parser? The log mentions "100 features to 16 autoencoders", confirming 100-dim from the Scapy path.

## Reproduction Plan

1. **Repository structure completeness:** The `docx/` target directory doesn't exist yet. When should reports be migrated from `docs/`?
2. **Git LFS for results:** The LFS rules are defined but not active until files land in `results/**/raw/`. Should we set up LFS tracking now or on first experiment run?
