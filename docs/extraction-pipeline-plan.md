# AI Extraction Pipeline Refactor Plan

Goal: split the current single prompt into focused extraction stages while keeping the existing review queue and canonical wiki models.

## Pipeline

Chapter text and wiki memory flow through focused extractors:

1. Characters and aliases
2. Progression and cultivation
3. Progression audit pass
4. Skills
5. Items
6. Character-skill relationships
7. Character-item relationships
8. Life events

The multi-stage implementation keeps these stages inside one OpenAI-compatible client call sequence and one persistence path. This limits UI/API disruption while letting each extractor use a smaller prompt.

The runtime mode is controlled by:

```text
AI_EXTRACTION_PIPELINE=legacy|multi_stage
```

The default is `legacy` so existing deployments keep the single broad extraction call unless `multi_stage` is explicitly enabled.

## Validation

Backend validation computes confidence and risk flags. The model output is not trusted for confidence.

Records can be auto-approved only when:

- confidence score is at least 90
- no serious risk flags are present
- the entity origin is safe enough for the fact being saved

Brand-new entities are treated more conservatively than entities that existed before extraction. They can still be saved, but auto-approval requires stronger direct evidence.

Serious flags include missing evidence, database conflicts, ambiguous ownership, speculative statements, and future statements.

## Review Compatibility

Existing `review_status` values remain:

- `approved` means auto-approved or manually approved
- `pending` means needs review
- `rejected` remains manual/review rejection

Records also store:

- `confidence_score`
- `risk_flags`
- `source_extractor`
- `auto_approved`

Ambiguous relationships that cannot be represented safely, such as a character-item relationship with no resolvable owner, are skipped with a `skipped_extractions` summary entry instead of being silently discarded.

The admin review UI can continue using existing records while gaining access to validation metadata.
