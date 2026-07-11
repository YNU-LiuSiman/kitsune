# Data Directory

This directory stores raw datasets used for Kitsune reproduction experiments.

**Policy:** Raw datasets are not committed to Git. They must be downloaded
separately using the instructions below.

## Dataset: UCI Kitsune Network Attack Dataset

This project reproduces the Kitsune (2018) network intrusion detection
framework using the UCI Kitsune Network Attack Dataset, which covers
nine types of network attacks:

| # | Attack Type | Description |
|---|---|---|
| 1 | Mirai | Mirai botnet malware infection |
| 2 | SSDP Flood | SSDP amplification DDoS attack |
| 3 | OS Scan | Operating system fingerprinting scan |
| 4 | SSL Renegotiation | SSL renegotiation DoS attack |
| 5 | ARP MitM | ARP man-in-the-middle attack |
| 6 | SYN DoS | SYN flood denial-of-service attack |
| 7 | Fuzzing | Protocol fuzzing attack |
| 8 | Active Wiretap | Active network wiretapping attack |
| 9 | Video Injection | Malicious video stream injection |

### Data Format

Each attack experiment expects:
- **Feature file:** `dataset.csv` (or compressed variant) — extracted
  packet-level features
- **Label file:** `labels.csv` (or compressed variant) — ground-truth
  labels for each record
- **Optional:** Raw PCAP captures of the attack traffic

### Expected Directory Layout

```
data/
├── README.md
├── .gitkeep
└── kitsune/
    ├── mirai/
    │   ├── dataset.csv
    │   └── labels.csv
    ├── ssdp_flood/
    ├── os_scan/
    ├── ssl_renegotiation/
    ├── arp_mitm/
    ├── syn_dos/
    ├── fuzzing/
    ├── active_wiretap/
    └── video_injection/
```

### Source

- **Dataset homepage:** https://archive.ics.uci.edu/dataset/516/kitsune+network+attack+dataset

> **Naming note:** Official UCI distribution uses `<Attack>_dataset.csv.gz` and `<Attack>_labels.csv.gz`. If the project renames these to `dataset.csv` / `labels.csv` internally, the preprocessing pipeline must document the rename explicitly.
- **Download URL and SHA-256:** To be confirmed during repository audit phase.
  Do not guess. Record actual values after manual verification.
