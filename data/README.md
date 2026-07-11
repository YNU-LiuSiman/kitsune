# Data Directory

This directory stores raw datasets used for experiments.

**Policy:** Raw datasets are not committed to Git. They must be downloaded
separately using the instructions below.

## Datasets Used

### UCI BotIoT (UNSW)

- **Source:** https://www.unsw.adfa.edu.au/unsw-canberra-cyber/cybersecurity/ADFA-NB15-Datasets/bot_iot.php
- **Files required:** `UNSW_2018_IoT_Botnet_Full5percent.csv` (or similar)
- **Place under:** `data/botiot/`
- **Expected SHA-256:** (to be recorded after download)

### CIC-IDS-2017

- **Source:** https://www.unb.ca/cic/datasets/ids-2017.html
- **Files required:** PCAPs and CSV label files
- **Place under:** `data/cic-ids-2017/`
- **Expected SHA-256:** (to be recorded after download)

## Download Instructions

```powershell
# Example: download BotIoT dataset
# (URL to be updated with actual download link)
# Invoke-WebRequest -Uri <URL> -OutFile data/botiot/raw.csv
```

## Directory Layout After Download

```
data/
├── README.md
├── .gitkeep
├── botiot/
│   └── UNSW_2018_IoT_Botnet_Full5percent.csv
└── cic-ids-2017/
    ├── Monday.pcap
    ├── Tuesday.pcap
    └── ...
```
