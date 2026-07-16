# How to Continue Overnight Experiment

## Status
UCI dataset was not found at `data/kitsune/`. Only the Mirai PCAP baseline was run.

## To Continue

1. Download the UCI Kitsune Network Attack Dataset from:
   https://archive.ics.uci.edu/dataset/516/kitsune+network+attack+dataset

2. Place each attack's files in:
   data/kitsune/<attack_name>/
   Example: data/kitsune/mirai/mirai_dataset.csv, data/kitsune/mirai/mirai_labels.csv

3. Re-run:
   python scripts/run_experiment.py --output-dir results/overnight-20260712

## Expected Attack Directories
- mirai/
- ssdp_flood/
- os_scan/
- ssl_renegotiation/
- arp_mitm/
- syn_dos/
- fuzzing/
- active_wiretap/
- video_injection/

## Parameters (fixed for all attacks)
- FMgrace=5000, ADgrace=50000, maxAE=10, lr=0.1, hr=0.75
