import io
import json
import zipfile
from datetime import datetime
from backend.dxf_generator import generate_compliance_shell_dxf


def generate_submission_package(compliance_result: dict,
                                 params: dict,
                                 owner_name: str = "Owner") -> bytes:
    """
    Generates a ZIP containing everything an architect needs
    to certify and submit to eDCR in 20 minutes.

    ZIP contents:
    1. compliance_report.json  - full compliance check results
    2. document_checklist.txt  - what documents to collect
    3. DRAFT_shell.dxf         - eDCR-ready plot + building boundary
    4. fee_estimate.txt        - government fee breakdown
    5. README.txt              - instructions for the architect
    """
    zip_buffer = io.BytesIO()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")

    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:

        # 1. Compliance report
        report = {
            "generated_by": "BuildIQ v1.0",
            "generated_at": datetime.now().isoformat(),
            "owner": owner_name,
            "verified_rules": "TNCDBR 2019 + G.O.Ms.No.70 (Mar 2024)",
            "disclaimer": "DRAFT — Architect must verify all values before submission",
            "compliance": compliance_result
        }
        zf.writestr(
            f"BuildIQ_Package_{timestamp}/compliance_report.json",
            json.dumps(report, indent=2)
        )

        # 2. Document checklist
        checklist = """BUILDIQ DOCUMENT CHECKLIST
Generated: {timestamp}
Authority: {authority}
===============================

REQUIRED DOCUMENTS — Collect ALL before visiting architect:

[ ] Sale Deed / Title Deed
    → Must be registered. Owner name must match application.

[ ] Patta / Chitta
    → Must reflect current owner. Name must match Sale Deed.

[ ] Encumbrance Certificate (EC)
    → ⚠️  CRITICAL: Must be issued within 30 days of submission.
    → If older than 25 days — apply for fresh EC NOW.

[ ] FMB Sketch (Field Measurement Book)
    → Obtain from Taluk office. Must match plot boundaries.

[ ] Site Plan (eDCR-compliant DXF format)
    → ✅ DRAFT shell included in this package (DRAFT_shell.dxf)
    → Architect must complete room layouts, elevations, sections.

[ ] Architect Certificate
    → Must be TNCA registered architect.

[ ] Property Tax Receipt
    → Latest paid receipt. Property ID must match survey number.

[ ] Aadhaar / ID Proof
    → Self-attested. Name must match all other documents.

===============================
DISCLAIMER: This checklist is advisory only.
Verify current requirements with CCMC: 0422-2390261
Rules verified: {today}
""".format(
            timestamp=timestamp,
            authority=params.get("authority", "CCMC"),
            today=datetime.now().strftime("%d %B %Y")
        )
        zf.writestr(
            f"BuildIQ_Package_{timestamp}/document_checklist.txt",
            checklist
        )

        # 3. DXF shell (only if compliance is not FAIL)
        status = compliance_result.get("overall_status", "FAIL")
        if status in ["PASS", "MARGINAL"]:
            dxf_bytes = generate_compliance_shell_dxf(params)
            zf.writestr(
                f"BuildIQ_Package_{timestamp}/DRAFT_shell.dxf",
                dxf_bytes
            )
        else:
            note = """DXF NOT GENERATED

Reason: Compliance check shows FAIL status.
Fix the following issues first, then re-run BuildIQ:

{summary}

Once all checks show PASS or MARGINAL, re-run BuildIQ
to get the DXF compliance shell.
""".format(summary=compliance_result.get("summary", "See compliance_report.json"))
            zf.writestr(
                f"BuildIQ_Package_{timestamp}/DXF_NOT_GENERATED.txt",
                note
            )

        # 4. Fee estimate
        plot_sqm = params.get("plot_area_sqm", 100)
        builtup_sqm = params.get("proposed_builtup_sqm", 150)
        authority = params.get("authority", "CCMC")
        scrutiny = 750 if builtup_sqm <= 150 else (1500 if builtup_sqm <= 300 else 3000)
        permit = round(builtup_sqm * 45)
        devcharges = round(builtup_sqm * 120)
        total_govt = scrutiny + permit + devcharges

        fee_text = """BUILDIQ FEE ESTIMATE
Authority: {authority}
Built-up Area: {builtup} sq.m
Generated: {today}
===============================

GOVERNMENT FEES (approximate):
  Scrutiny Fee:           ₹{scrutiny:,}
  Building Permit Fee:    ₹{permit:,}
  Development Charges:    ₹{dev:,}
  ─────────────────────────────
  Total Government Fee:   ₹{total:,}

AGENCY FEE BENCHMARK (Coimbatore 2026):
  Market range:  ₹15,000 – ₹40,000
  With BuildIQ:  ₹999 (architect certification only)
  You save:      ₹14,000 – ₹39,000

⚠️  Fee estimates are approximate. Verify with CCMC before paying.
    Call CCMC: 0422-2390261
""".format(
            authority=authority,
            builtup=builtup_sqm,
            today=datetime.now().strftime("%d %B %Y"),
            scrutiny=scrutiny,
            permit=permit,
            dev=devcharges,
            total=total_govt
        )
        zf.writestr(
            f"BuildIQ_Package_{timestamp}/fee_estimate.txt",
            fee_text
        )

        # 5. README for architect
        readme = """README — FOR THE ARCHITECT
==========================
This package was prepared by BuildIQ, a Tamil Nadu building
plan pre-submission compliance advisor.

WHAT IS IN THIS PACKAGE:
  compliance_report.json  — Full TNCDBR 2019 compliance check
  document_checklist.txt  — Documents the owner must bring
  DRAFT_shell.dxf         — Plot boundary + building footprint
  fee_estimate.txt        — Government fee breakdown

YOUR TASKS (estimated 20 minutes):
  1. Open DRAFT_shell.dxf in AutoCAD
  2. Verify all dimensions against site survey
  3. Add room layouts, elevations, sections
  4. Run PreDCR verification
  5. Certify with your TNCA registration number
  6. Submit to eDCR portal

DISCLAIMER:
  BuildIQ outputs are DRAFT and advisory only.
  You are responsible for verifying all dimensions
  and certifying compliance before submission.
  BuildIQ is not liable for eDCR rejection.

Rule reference: TNCDBR 2019 | G.O.Ms.No.70 (Mar 2024)
Verified: {today}

Built with BuildIQ — buildiq.app
""".format(today=datetime.now().strftime("%d %B %Y"))
        zf.writestr(
            f"BuildIQ_Package_{timestamp}/README_FOR_ARCHITECT.txt",
            readme
        )

    zip_buffer.seek(0)
    return zip_buffer.read()
