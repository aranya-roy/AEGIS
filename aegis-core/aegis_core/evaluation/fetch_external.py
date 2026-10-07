"""Download the public evaluation datasets into data/external/ (git-ignored).

Pinned to exact files; verifies they parse as CSV with the expected
columns. Nothing downloaded is ever executed or imported.
"""

from __future__ import annotations

import csv
import io
import urllib.request

from .run import ROOT

HF = "https://huggingface.co/datasets"
FILES = {
    "scam_dialogue/test.csv": (f"{HF}/BothBosu/scam-dialogue/resolve/main/scam-dialogue_test.csv",
                               {"dialogue", "type", "label"}),
    "hinglish_calls/data.csv": (f"{HF}/ysangam/Indian_Cyber_Scam_PhoneCall_Hinglish_Dataset/resolve/main/India_Cyber_Scam_Hinglish_Dataset.csv",
                                {"text", "label"}),
}
MAX_BYTES = 50 * 1024 * 1024


def main() -> None:
    for rel, (url, cols) in FILES.items():
        dest = ROOT / "data" / "external" / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        with urllib.request.urlopen(url, timeout=120) as r:
            data = r.read(MAX_BYTES + 1)
        if len(data) > MAX_BYTES:
            raise SystemExit(f"{rel}: larger than expected, refusing")
        header = next(csv.reader(io.StringIO(data.decode("utf-8", errors="strict"))))
        if not cols <= set(header):
            raise SystemExit(f"{rel}: unexpected columns {header}")
        dest.write_bytes(data)
        print(f"{rel}: {len(data):,} bytes")


if __name__ == "__main__":
    main()
