from extensions import db
from models.compliance_models import ComplianceRequirement, REQUIRED_DOCUMENT_TYPES, READINESS_THRESHOLDS
from models.document import Document


class ComplianceService:

    # ------------------------------------------------------------------ #
    #  seed_compliance_requirements                                        #
    # ------------------------------------------------------------------ #
    @staticmethod
    def seed_compliance_requirements(project_id: int):
        """
        Creates a ComplianceRequirement row for every required document type
        for the given project.  Idempotent — skips types that already exist.
        Also attempts to auto-link any existing Document rows by document_type.
        """
        existing_types = {
            r.document_type
            for r in ComplianceRequirement.query.filter_by(project_id=project_id).all()
        }

        new_rows = []
        for doc_type in REQUIRED_DOCUMENT_TYPES:
            if doc_type in existing_types:
                continue

            matched_doc = Document.query.filter_by(
                project_id=project_id,
                document_type=doc_type,
            ).order_by(Document.id.desc()).first()

            new_rows.append(
                ComplianceRequirement(
                    project_id=project_id,
                    document_type=doc_type,
                    document_id=matched_doc.id if matched_doc else None,
                )
            )

        if new_rows:
            db.session.add_all(new_rows)
            db.session.commit()

    # ------------------------------------------------------------------ #
    #  get_missing_documents                                               #
    # ------------------------------------------------------------------ #
    @staticmethod
    def get_missing_documents(project_id: int) -> list:
        """
        Returns list of document_type strings that are missing or outdated.
        """
        reqs = ComplianceRequirement.query.filter_by(project_id=project_id).all()
        missing = []
        for req in reqs:
            if req.document_id is None:
                missing.append(req.document_type)
            elif req.document and req.document.is_outdated:
                missing.append(req.document_type)
        return missing

    # ------------------------------------------------------------------ #
    #  calculate_readiness_score                                           #
    # ------------------------------------------------------------------ #
    @staticmethod
    def calculate_readiness_score(project_id: int) -> dict:
        reqs = ComplianceRequirement.query.filter_by(project_id=project_id).all()
        total = len(REQUIRED_DOCUMENT_TYPES)

        uploaded = sum(
            1 for r in reqs
            if r.document_id is not None
            and r.document is not None
            and not r.document.is_outdated
        )

        score = round((uploaded / total) * 100) if total > 0 else 0

        return {
            "total_required":  total,
            "uploaded":        uploaded,
            "readiness_score": score,
        }

    # ------------------------------------------------------------------ #
    #  _resolve_status                                                     #
    # ------------------------------------------------------------------ #
    @staticmethod
    def _resolve_status(score: int) -> str:
        for status, (lo, hi) in READINESS_THRESHOLDS.items():
            if lo <= score <= hi:
                return status
        return "NOT_READY"

    # ------------------------------------------------------------------ #
    #  check_project_compliance  (main entry point)                        #
    # ------------------------------------------------------------------ #
    @staticmethod
    def check_project_compliance(project_id: int) -> dict:
        """
        Full compliance report for a project.
        Seeds requirements first so the call is always safe.
        """
        ComplianceService.seed_compliance_requirements(project_id)

        score_data = ComplianceService.calculate_readiness_score(project_id)
        score      = score_data["readiness_score"]
        status     = ComplianceService._resolve_status(score)
        missing    = ComplianceService.get_missing_documents(project_id)

        reqs = ComplianceRequirement.query.filter_by(project_id=project_id).all()
        checklist = []
        for req in reqs:
            if req.document_id is None:
                doc_status = "Missing"
            elif req.document and req.document.is_outdated:
                doc_status = "Outdated"
            else:
                doc_status = "Uploaded"

            checklist.append({
                "document_type": req.document_type,
                "status":        doc_status,
                "document_id":   req.document_id,
            })

        return {
            "project_id":      project_id,
            "total_required":  score_data["total_required"],
            "uploaded":        score_data["uploaded"],
            "missing":         missing,
            "readiness_score": score,
            "status":          status,
            "checklist":       checklist,
        }