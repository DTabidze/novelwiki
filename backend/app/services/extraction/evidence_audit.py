from app.models import AIEvidenceAudit, db
from app.services.extraction.evidence import verify_evidence_text


def ai_evidence_verification_status(chapter_text, evidence_text):
    if evidence_text is None or evidence_text == "":
        return "missing", "missing", None

    verification = verify_evidence_text(chapter_text or "", evidence_text)

    if verification.verified:
        return "verified", None, verification.evidence_text

    if verification.ambiguous:
        return "ambiguous", "ambiguous", None

    return "failed", "not_exact", None


def audit_match_value(value):
    return "" if value is None else str(value)


def existing_ai_evidence_audit(
    novel_id,
    chapter_id,
    entity_type,
    entity_id,
    source_extractor,
    ai_proposed_evidence,
):
    rows = AIEvidenceAudit.query.filter_by(
        novel_id=novel_id,
        chapter_id=chapter_id,
        entity_type=entity_type,
        entity_id=entity_id,
        source_extractor=source_extractor,
    ).all()

    proposed_key = audit_match_value(ai_proposed_evidence)

    for row in rows:
        if audit_match_value(row.ai_proposed_evidence) == proposed_key:
            return row

    return None


def record_ai_evidence_audit(
    novel,
    chapter,
    entity_type,
    entity_id,
    ai_proposed_evidence,
    source_extractor=None,
    canonical_evidence_text=None,
    recovery_method=None,
    canonical_start_offset=None,
    canonical_end_offset=None,
    canonical_match_type=None,
):
    if not novel or not entity_type:
        return False

    chapter_text = chapter.content if chapter else ""
    verification_status, failure_reason, verified_evidence = ai_evidence_verification_status(
        chapter_text,
        ai_proposed_evidence,
    )
    canonical_verification = verify_evidence_text(
        chapter_text,
        canonical_evidence_text,
        start_offset=canonical_start_offset,
        end_offset=canonical_end_offset,
        match_type=canonical_match_type,
    )
    canonical_text = canonical_verification.evidence_text if canonical_verification.verified else None

    if verification_status == "verified" and not recovery_method:
        if not canonical_text or canonical_text == verified_evidence:
            return False

    evidence_source = None

    if verification_status == "verified":
        evidence_source = "ai_verified"
    elif canonical_text:
        evidence_source = "backend_recovered"
    else:
        evidence_source = "unverified_ai"

    source = source_extractor or None
    existing = existing_ai_evidence_audit(
        novel.id,
        chapter.id if chapter else None,
        entity_type,
        entity_id,
        source,
        ai_proposed_evidence,
    )

    if existing:
        existing.verification_status = verification_status
        existing.failure_reason = failure_reason
        existing.evidence_source = evidence_source
        existing.canonical_evidence_text = canonical_text
        existing.recovery_method = recovery_method or existing.recovery_method
        return False

    db.session.add(
        AIEvidenceAudit(
            novel_id=novel.id,
            chapter_id=chapter.id if chapter else None,
            entity_type=entity_type,
            entity_id=entity_id,
            source_extractor=source,
            ai_proposed_evidence=ai_proposed_evidence,
            verification_status=verification_status,
            failure_reason=failure_reason,
            evidence_source=evidence_source,
            canonical_evidence_text=canonical_text,
            recovery_method=recovery_method,
        )
    )
    return True


def record_ai_evidence_audit_for_candidate(
    novel,
    chapter,
    entity_type,
    entity_id,
    candidate,
    source_extractor=None,
):
    if candidate is None:
        return False

    original_evidence = getattr(candidate, "original_evidence", None)
    ai_proposed_evidence = (
        original_evidence
        if original_evidence is not None
        else getattr(candidate, "evidence", None)
    )
    canonical_evidence = getattr(candidate, "evidence", None)

    return record_ai_evidence_audit(
        novel,
        chapter,
        entity_type,
        entity_id,
        ai_proposed_evidence,
        source_extractor=source_extractor,
        canonical_evidence_text=canonical_evidence,
        recovery_method=getattr(candidate, "evidence_recovery_method", None),
        canonical_start_offset=getattr(candidate, "evidence_start_offset", None),
        canonical_end_offset=getattr(candidate, "evidence_end_offset", None),
        canonical_match_type=getattr(candidate, "evidence_match_type", None),
    )
