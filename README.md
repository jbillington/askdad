# Ask Dad for Mac
*by DadWare*

**Website, download and a sample report: [justaskdad.app](https://justaskdad.app)**

## About the program
Ask Dad is a free tool for kids and adults who need to know why their Mac is running slow or why they are out of storage.  It is both a learning tool for the file system and a way to get a detailed report about your system performance and available storage. 

Use Ask Dad to scan your Mac's file system, measure available space and provide a HTML report card with letter grades and advice. The report card lets you visually see what folders are taking up space, highlights the largest files, and tells you what to clean up. The scan program is similar but provides an overview of memory pressure and CPU hogging processes for quick diagnoses.  

Under the hood Ask Dad is a python program that scans your hard drive and measures file sizes.  It is lightweight and doesn't have dependencies other than python.  It was made by a Dad who is an engineer. The code was written by AI but it contains no calls to AI services. The program is Read-Only so it never deletes your files, we leave that to you. 


## 📄 License and Trademarks

Ask Dad and DadWare are trademarks of John Billington.

You are free to use, modify, and distribute the open source code in this repository under the terms of the MIT License. However, you may not use the names Ask Dad, DadWare, or any associated branding (including logos) to market or distribute derivative works without prior written permission.

If you fork or build on this project, please use a different name for your version.

This project is licensed under the MIT License. 

## Install

**The easiest way: download the app.** Go to [justaskdad.app](https://justaskdad.app) and click Download. Open `AskDad.dmg`, drag Ask Dad into Applications, and double-click it. A Terminal window opens, the scan runs, and your report opens in your browser. The website also has a sample report and answers to common questions.

After the first scan, Dad asks if you want the `askdad` command in every Terminal window. Say yes to use the commands below. Say no to keep using only the app.

The app is signed and notarized by Apple, and it runs on Apple silicon and Intel Macs.

**For Terminal users: run it from GitHub.** Ask Dad is plain Python with no dependencies, so you can run this repository directly:

```bash
git clone https://github.com/jbillington/askdad.git
cd askdad
python3 askdad.py
```

It needs `python3`, which comes with Apple's Command Line Tools. If your Mac doesn't have it yet, macOS offers to install it the first time you type `python3`. Run this way, use `python3 askdad.py` wherever this page says `askdad`, and reports are saved in the `test-reports` folder inside `askdad`. To update, run `git pull` in that folder.

## Commands

```bash
askdad          # Scan storage (default)
askdad cpu      # Scan CPU and RAM
askdad all      # Scan both
```

A report opens in your browser automatically. After a storage scan in Terminal, Ask Dad offers to run the CPU scan too (`[y/N]`, default no).

Feedback welcome: john@dadware.net.

## Options

```bash
askdad --volume /Volumes/External    # Scan a specific drive (default: asks you)
askdad --all-volumes                 # Also offer disk images, network shares, read-only mounts
askdad --top 100                     # How many top files to report (default: 500)
askdad --min-size 500MB              # Ignore files smaller than this
askdad --terminal                    # Terminal report only, skip the HTML report
askdad --no-color                    # Plain terminal output, no colors
askdad --skip-protected              # Skip protected libraries (Photos, Messages, Mail)
askdad --no-mac-libraries            # Skip app library scanning entirely (faster)
askdad --timings                     # Print how long each phase of the scan took
askdad cpu --export-memory mem.csv   # Export every process's memory use to CSV
askdad export memory report.json     # Export CSV from a previously saved report
```

## Permissions (Optional)

To scan Photos, Messages, and Mail: **System Settings** → **Privacy & Security** → **Full Disk Access** → add **Terminal.app**.

Without it, the scan still works. The libraries it can't open, and the Trash, are marked "needs Full Disk Access" in the report and left out of the grade, rather than counted as empty.

## Troubleshooting

| Problem | Fix |
|---------|-----|
| macOS asks "Are you sure you want to open it?" | This is normal for any downloaded app. Click **Open**. |
| `askdad: command not found` | Open a new Terminal window. If you said no to Dad's question, run the app again from Applications. Running from a GitHub copy? Use `python3 askdad.py` in that folder. |
| Dad didn't offer the `askdad` command | Drag the app into Applications first. Dad doesn't ask when the app runs from the DMG, or when `askdad` is already installed. |

## Safety

This tool only scans and reports. It does not delete files, and it does not advise you what to delete. Any cleanup decisions are yours.

---

MIT License — Copyright (c) 2025 John Billington. See [LICENSE](LICENSE).
