import logging
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.tennis_prop_reasons import REASONS_VERSION
from app.db.pool import get_db
from app.repositories.props import get_prizepicks_prop, get_today_match_odds_as_props, get_today_props
from app.schemas.props import (
    PropReasonSchema,
    PropsAuditResponse,
    PropsResponse,
    RecentSummarySchema,
    RecentValueSchema,
    TennisPropReasonsResponse,
)
from app.services.tennis import prop_adoption
from app.services.tennis.prop_enrichment import audit_summary, enrich_props
from app.services.tennis.prop_reasons import build_prop_reasons

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/prizepicks/audit", response_model=PropsAuditResponse)
async def get_prizepicks_props_audit(db: AsyncSession = Depends(get_db)):
    try:
        props = await get_today_props(db, source="prizepicks")
        enriched = await enrich_props(db, props, now=datetime.now(UTC))
        return PropsAuditResponse(
            source="prizepicks",
            count=len(enriched),
            props=enriched,
            summary=audit_summary(enriched),
        )
    except Exception as e:
        logger.exception("PrizePicks audit failed")
        raise HTTPException(status_code=500, detail="The PrizePicks audit is temporarily unavailable.") from e


@router.get("/prizepicks", response_model=PropsResponse)
async def get_prizepicks_props(db: AsyncSession = Depends(get_db)):
    try:
        now = datetime.now(UTC)
        props = await get_today_props(db, source="prizepicks")
        enriched = await enrich_props(db, props, now=now)
        adopted = await prop_adoption.load_adopted(db)
        enriched = prop_adoption.apply_adoption(props, enriched, adopted, now)
        return PropsResponse(
            source="prizepicks",
            count=len(props),
            props=enriched,
        )
    except Exception as e:
        logger.exception("PrizePicks props failed")
        raise HTTPException(status_code=500, detail="PrizePicks props are temporarily unavailable.") from e


@router.get("/prizepicks/{prop_id:int}/reasons", response_model=TennisPropReasonsResponse)
async def get_prizepicks_prop_reasons(prop_id: int, db: AsyncSession = Depends(get_db)) -> TennisPropReasonsResponse:
    prop = await get_prizepicks_prop(db, prop_id)
    if prop is None:
        raise HTTPException(status_code=404, detail="PrizePicks line not found")
    if prop.line is None:
        raise HTTPException(status_code=422, detail="This line has no number to compare against")
    [line] = await enrich_props(db, [prop], now=datetime.now(UTC))
    result = await build_prop_reasons(db, prop, line)
    reasons = result.reasons
    return TennisPropReasonsResponse(
        prop_id=prop.id,
        player_id=prop.player_id,
        stat_type=prop.stat_type,
        line=float(prop.line),
        version=REASONS_VERSION,
        recent=[RecentValueSchema.model_validate(v) for v in result.chart],
        summary=RecentSummarySchema.model_validate(reasons.summary) if reasons.summary else None,
        over=[PropReasonSchema.model_validate(r) for r in reasons.over],
        under=[PropReasonSchema.model_validate(r) for r in reasons.under],
        caveats=[PropReasonSchema.model_validate(r) for r in reasons.caveats],
    )


@router.get("/dk", response_model=PropsResponse)
async def get_dk_props(db: AsyncSession = Depends(get_db)):
    props = await get_today_props(db, source="draftkings")
    odds_props = await get_today_match_odds_as_props(db, books=["draftkings"])
    props = [*props, *odds_props]
    enriched = await enrich_props(db, props, now=datetime.now(UTC))
    return PropsResponse(
        source="draftkings",
        count=len(props),
        props=enriched,
    )
