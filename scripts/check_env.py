"""Check what this machine can run, and what will degrade.

    python scripts/check_env.py

Core (required): Python 3.10+, openpyxl, matplotlib.  Report: weasyprint (PDF), python-docx (.docx).
Verification: LibreOffice `soffice` (Excel recalculation — the only proof the workbook's formulas equal the model),
pdftotext from poppler (pagination check of the PDF). Missing pieces do not stop a run; they remove a guarantee, and the
run must say so in the deliverable."""
import importlib
import shutil
import sys


def main():
    ok = True
    print(f"python {sys.version.split()[0]}", "ok" if sys.version_info >= (3, 10) else "TOO OLD (3.10+ needed)")
    for mod, what, need in (("openpyxl", "Excel workbook", "required"), ("matplotlib", "dashboard PNG / docx charts", "required"),
                            ("weasyprint", "PDF and HTML report", "recommended"), ("docx", "Word report (python-docx)", "optional")):
        try: importlib.import_module(mod); print(f"{mod:<11} ok        — {what}")
        except Exception as e:
            print(f"{mod:<11} MISSING   — {what} ({need}): pip install {'python-docx' if mod == 'docx' else mod} --break-system-packages" + (f"  [{e}]" if mod == "weasyprint" else ""))
            ok = ok and need != "required"
    for exe, what, fallback in (("soffice", "LibreOffice — recalculates the .xlsx so Python and Excel are proven equal", "without it: deliver the workbook with the note 'formulas not recalculated on this machine'; selftest reports INCOMPLETE"),
                                ("pdftotext", "poppler — verifies the PDF page order", "without it: build the PDF without --strict; pagination is not verified")):
        path = shutil.which(exe)
        print(f"{exe:<11} {'ok' if path else 'MISSING'}{'':8}— {what}" + ("" if path else f"\n            {fallback}"))
    print("\nenvironment:", "complete" if ok and shutil.which("soffice") and shutil.which("pdftotext") else "usable with the degradations listed above" if ok else "NOT usable until the required packages are installed")


if __name__ == "__main__":
    main()
