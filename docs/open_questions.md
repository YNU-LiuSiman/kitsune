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

1. **Dimension mismatch:** UCI features = 115, Python KitNET expects 100. Options:
   - Strip 15 UCI columns to match 100 (which 15?)
   - Expand KitNET to accept 115 (modify source = forbidden currently)
   - Add external wrapper that pads/selects dimensions
   - Feasibility analysis needed.
2. **Normalization compatibility:** dA.py does per-AE online 0-1 norm. UCI CSV may already be normalized or may need pre-normalization. Will the internal normalization handle CSV inputs correctly?
3. **Feature ordering:** Is the UCI column order the same as the Python internal order? Need cross-reference between UCI documentation and `getNetStatHeaders` output.

## Paper Parameters

1. **Grace periods for 9 attacks:** example.py uses FMgrace=5000, ADgrace=50000 for Mirai. Do other attacks need different grace periods? The paper mentions dataset-specific tuning for attack density.
2. **maxAE parameter sensitivity:** Paper uses m=10. Is this optimal for all 9 attacks?
3. **Threshold (phi):** The paper's log-normal threshold method (example.py:55-57) uses RMSEs from the first 100k instances. For other attacks with different dataset sizes, how should phi be determined?
4. **EER calculation:** The paper reports EER, but the exact calculation method (threshold sweep? fixed FPR?) needs extraction from the paper.

## Log and Evidence

1. **Previous experiment logs:** The file `Kitsune/初次冒烟测试终端日志.txt` contains the local test run output. It should be sanitized and used as reference for dimension analysis.
2. **Scapy vs tshark:** The previous local test used which parser? The log mentions "100 features to 16 autoencoders", confirming 100-dim from the Scapy path.

## Reproduction Plan

1. **Repository structure completeness:** The `docx/` target directory doesn't exist yet. When should reports be migrated from `docs/`?
2. **Git LFS for results:** The LFS rules are defined but not active until files land in `results/**/raw/`. Should we set up LFS tracking now or on first experiment run?
