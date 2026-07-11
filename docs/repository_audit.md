# Repository Audit — Phase 00

## 1. Call Chain Overview

```
example.py
  → Kitsune (Kitsune.py)
    → FE (FeatureExtractor.py) — packet parsing + feature extraction
      → netStat (netStat.py) — network statistics computation
        → incStatDB (AfterImage.py) — damped incremental statistics
    → KitNET (KitNET/KitNET.py) — anomaly detection ensemble
      → corClust (KitNET/corClust.py) — feature correlation clustering
      → dA (KitNET/dA.py) — denoising autoencoder
```

## 2. Detailed Call Chain

### 2.1 example.py

| Aspect | Detail |
|---|---|
| File | `Kitsune/Kitsune-py/example.py` |
| Entry point | Line 34: `K = Kitsune(path, packet_limit, maxAE, FMgrace, ADgrace)` |
| Grace periods | Lines 30-31: `FMgrace=5000`, `ADgrace=50000` |
| maxAE | Line 29: `maxAE=10` |
| Packet source | Line 20-21: Unzips `mirai.zip`, uses `mirai.pcap` |
| RMSE collection | Lines 37-49: Loop calls `K.proc_next_packet()`, appends rmse until -1 |
| Stats | Lines 55-57: Fits log-normal to post-grace RMSEs |
| Plot | Lines 61-71: Scatter plot of RMSEs colored by log-probability |

### 2.2 Kitsune (Kitsune.py)

| Aspect | Detail |
|---|---|
| Constructor | Line 27-32: Creates `FE(file_path, limit)` and `KitNET(n, maxAE, FMgrace, ADgrace, lr, hr)` |
| n (feature count) | Line 32: `self.FE.get_num_features()` returns header count from `netStat.getNetStatHeaders()` |
| proc_next_packet | Lines 34-41: Gets `x = self.FE.get_next_vector()`, returns `self.AnomDetector.process(x)` |
| -1 signal | Line 38: Returns -1 when no packets left |

### 2.3 FeatureExtractor (FeatureExtractor.py)

| Aspect | Detail |
|---|---|
| Parsing modes | Lines 64-79: TSV (via tshark, fast) or Scapy (slow) |
| tshark path | Lines 42-51: Windows: `C:\Program Files\Wireshark\tshark.exe` |
| Scapy fallback | Line 76: If tshark not found, uses `rdpcap()` |
| get_next_vector | Lines 109-207: Parses next packet, extracts fields, calls `netStat.updateGetStats(...)` |
| Field extraction | Lines 116-193: Extracts timestamp, frame len, src/dst IP, ports, MACs per protocol |
| get_num_features | Lines 217-218: Returns `len(self.nstat.getNetStatHeaders())` |

### 2.4 netStat (netStat.py)

| Aspect | Detail |
|---|---|
| Feature groups | Lines 80-103: Four stat groups concatenated into one vector |
| MIstat | Lines 80-82: MAC-IP relationship stats — **3 × 5 = 15 features** (weight, mean, std per Lambda) |
| HHstat | Lines 85-87: Host-Host BW stats — **7 × 5 = 35 features** (1D2D: weight, mean, std, radius, mag, cov, pcc per Lambda) |
| HHstat_jit | Lines 90-92: Host-Host jitter — **3 × 5 = 15 features** (weight, mean, std per Lambda, diff type) |
| HpHpstat | Lines 95-101: Host-Port BW stats — **7 × 5 = 35 features** (same structure as HHstat) |
| Total | Line 103: `np.concatenate((MIstat, HHstat, HHstat_jit, HpHpstat))` = **100 features** |
| Hstat (commented out) | Lines 74-77: Source Host BW stats — **3 × 5 = 15 features**, not computed |
| Lambdas | Line 42: `[5, 3, 1, .1, .01]` (5 decay factors) |
| getNetStatHeaders | Lines 105-118: Returns header names; includes `Hstat_headers` (empty []) in concatenation but never populated, so also returns **100** |

### 2.5 KitNET (KitNET/KitNET.py)

| Aspect | Detail |
|---|---|
| Constructor | Lines 20-46: Stores n, m, FM_grace, AD_grace, lr, hr |
| Feature Mapper (FM) | Line 46: `self.FM = CC.corClust(self.n)` |
| process() | Lines 51-56: If trained > FM+AD grace → execute(), else train() |
| train() | Lines 60-80: FM phase (first FM_grace instances): updates corClust, at FM_grace calls `self.FM.cluster(self.m)` to get feature map. AD phase: trains ensemble AEs and output AE |
| execute() | Lines 83-95: Feeds sub-vectors to each ensemble AE, feeds ensemble outputs to output AE |
| RMSE per sample | Returns `self.outputLayer.execute(S_l1)` which is the RMSE of the output AE's reconstruction |
| createAD() | Lines 97-105: Creates ensemble AEs (one per cluster) + output AE |

### 2.6 corClust (KitNET/corClust.py)

| Aspect | Detail |
|---|---|
| Constructor | Lines 8-16: Initializes correlation matrix `C` of size n×n |
| update(x) | Lines 19-25: Incrementally updates correlation matrix with new observation |
| cluster(maxClust) | Lines 37-45: Computes distance matrix, builds dendrogram, breaks into clusters ≤ maxClust |
| Feature map output | List of lists: each sub-list contains feature indices for one autoencoder |

### 2.7 dA (KitNET/dA.py)

| Aspect | Detail |
|---|---|
| train(x) | Lines 80-106: 0-1 normalization, encode-decode, backprop, returns RMSE |
| execute(x) | Lines 114-122: Same normalization + reconstruction, returns RMSE |
| Grace period | Lines 115-116: Returns 0.0 during grace |
| Normalization | Lines 86-87: Online 0-1 normalization (tracking running min/max) |

## 3. Grace Periods and Mode Switching

| Phase | Internal n_trained | 1-indexed instance | KitNET State | Process Behavior |
|---|---|---|---|---|
| FM grace | 0 — 5000 (inclusive) | 1 — 5001 | FM training, AD off | train(): FM.update(x); at n_trained==FMgrace (5000) → cluster → createAD |
| AD grace | 5001 — 55000 | 5002 — 55001 | FM execute, AD training | train(): ensemble AEs train, output AE trains |
| Execute | ≥ 55001 | ≥ 55002 | FM execute, AD execute | execute(): ensemble → output AE → RMSE |

Note: The FM grace processes 5001 instances (internal n_trained 0..5000). The 5001st instance (n_trained=5000) triggers feature-map clustering before the AD is created. AD grace then covers 50000 instances (n_trained 5001..55000).

## 4. RMSE Generation

Each call to `proc_next_packet()` produces:
- During FM+AD grace (n_trained 0..55000): returns 0.0 (from process → train)
- After grace (n_trained ≥ 55001): returns the RMSE from the output autoencoder
- RMSE at line 121 in dA.py: `numpy.sqrt(((x - z) ** 2).mean())`
- No packets left: returns -1

## 5. Key Design Properties

1. **Online/streaming**: Exactly one packet processed at a time; no batch storage
2. **Incremental correlation matrix**: O(n²) memory, updated per-packet
3. **Dynamic feature mapping**: Learned from first FMgrace packets, fixed afterward
4. **Online normalization**: Per-AE running min/max tracking
5. **Output AE as voting mechanism**: Non-linear combination of ensemble outputs

## 6. File Paths Summary

All paths relative to `<GIT_ROOT>`:

| Purpose | Path |
|---|---|
| Entry point | `Kitsune/Kitsune-py/example.py` |
| Kitsune wrapper | `Kitsune/Kitsune-py/Kitsune.py` |
| Feature extraction | `Kitsune/Kitsune-py/FeatureExtractor.py` |
| Incremental stats | `Kitsune/Kitsune-py/AfterImage.py` |
| Network statistics | `Kitsune/Kitsune-py/netStat.py` |
| Dataset sample | `Kitsune/Kitsune-py/mirai.zip` |
| Dependencies | `Kitsune/Kitsune-py/requirements-reproduction.txt` |
| KitNET ensemble | `Kitsune/Kitsune-py/KitNET/KitNET.py` |
| Correlation clust | `Kitsune/Kitsune-py/KitNET/corClust.py` |
| Denoising AE | `Kitsune/Kitsune-py/KitNET/dA.py` |
| Utilities | `Kitsune/Kitsune-py/KitNET/utils.py` |
