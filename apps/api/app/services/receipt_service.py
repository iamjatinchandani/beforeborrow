import json
import uuid
from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status

from app.models.decisions import DecisionReceipt, Analysis
from app.models.finance import Profile
from app.repositories.receipts import ReceiptRepository
from app.schemas.decisions import ReceiptIn, ReceiptOut, ReceiptDetailOut

class ReceiptService:
    @staticmethod
    async def create_receipt(
        db: AsyncSession,
        owner_id: uuid.UUID,
        data: ReceiptIn,
    ) -> ReceiptOut:
        # Check analysis exists and belongs to owner
        stmt = select(Analysis).where(Analysis.id == data.analysis_id, Analysis.owner_id == owner_id)
        res = await db.execute(stmt)
        analysis = res.scalar_one_or_none()
        if not analysis:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Analysis not found",
            )

        # Check if receipt already exists for this analysis (immutability)
        existing = await ReceiptRepository.get_by_analysis_id(db, data.analysis_id, owner_id)
        if existing:
            return ReceiptOut(
                id=existing.id,
                analysis_id=existing.analysis_id,
                chosen_option=existing.chosen_option,
                created_at=existing.created_at,
            )

        reflection_json = json.dumps(data.reflection_answers) if data.reflection_answers else None

        receipt = await ReceiptRepository.create(
            db=db,
            owner_id=owner_id,
            analysis_id=data.analysis_id,
            chosen_option=data.chosen_option,
            reflection_json=reflection_json,
        )

        return ReceiptOut(
            id=receipt.id,
            analysis_id=receipt.analysis_id,
            chosen_option=receipt.chosen_option,
            created_at=receipt.created_at,
        )

    @staticmethod
    async def get_receipt(
        db: AsyncSession,
        receipt_id: uuid.UUID,
        owner_id: uuid.UUID,
    ) -> ReceiptDetailOut:
        receipt = await ReceiptRepository.get_by_id(db, receipt_id, owner_id)
        if not receipt:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Receipt not found",
            )

        analysis = receipt.analysis
        if not analysis:
            # Load analysis
            stmt = select(Analysis).where(Analysis.id == receipt.analysis_id)
            res = await db.execute(stmt)
            analysis = res.scalar_one_or_none()

        # Check staleness
        prof_stmt = select(Profile).where(Profile.owner_id == owner_id)
        prof_res = await db.execute(prof_stmt)
        profile = prof_res.scalar_one_or_none()

        is_stale = False
        if profile and profile.data_version > analysis.source_data_version:
            is_stale = True

        input_data = json.loads(analysis.input_json)
        result_data = json.loads(analysis.result_json)

        # Find chosen offer in result_data
        chosen_offer = None
        for off in result_data.get("offers", []):
            if off.get("offer_id") == receipt.chosen_option or off.get("offer_name") == receipt.chosen_option:
                chosen_offer = off
                break

        context = {
            "emergency_amount_paise": result_data.get("expense_amount_paise", 0),
            "expense_date": result_data.get("expense_date", ""),
            "allowed_savings_paise": input_data.get("allowed_savings_paise", 0),
            "chosen_option": receipt.chosen_option,
            "offer_details": chosen_offer,
            "calculated_at": analysis.calculated_at.isoformat(),
            "snapshot_hash": analysis.snapshot_hash,
            "model_version": analysis.model_version,
            "source_data_version": analysis.source_data_version,
        }

        consequences = {
            "total_credit_cost_paise": chosen_offer.get("financing_cost_paise", 0) if chosen_offer else 0,
            "total_repayment_paise": chosen_offer.get("total_repayment_paise", 0) if chosen_offer else 0,
            "monthly_installment_paise": chosen_offer.get("monthly_installment_paise", 0) if chosen_offer else 0,
            "cash_trough_paise": chosen_offer.get("trough_paise", 0) if chosen_offer else 0,
            "cash_trough_date": chosen_offer.get("trough_date", "") if chosen_offer else "",
            "first_reserve_breach": chosen_offer.get("first_reserve_breach") if chosen_offer else None,
            "first_negative_date": chosen_offer.get("first_negative") if chosen_offer else None,
            "repayment_term_months": chosen_offer.get("term_months", 0) if chosen_offer else 0,
            "status": chosen_offer.get("status", "feasible") if chosen_offer else "feasible",
            "causes": chosen_offer.get("causes", []) if chosen_offer else [],
        }

        uncertainty = {
            "named_stress_cases": input_data.get("stress_cases", ["income_delay_30d", "expense_spike_20pct"]),
            "stress_outcomes": result_data.get("stress_results", {}),
            "same_day_settlement_rule": "Assumes merchant receives funds on expense date; repayment deductions trigger at midnight.",
            "assumptions": [
                "Income timing conforms to registered monthly schedule.",
                "Existing scheduled debt payments maintain non-default status.",
                "Disclosed loan fees remain unadjusted by provider prior to disbursement.",
            ],
        }

        reflection_answers = None
        if receipt.reflection_json:
            try:
                reflection_answers = json.loads(receipt.reflection_json)
            except Exception:
                reflection_answers = None

        return ReceiptDetailOut(
            id=receipt.id,
            analysis_id=receipt.analysis_id,
            chosen_option=receipt.chosen_option,
            reflection_answers=reflection_answers,
            created_at=receipt.created_at,
            stale=is_stale,
            context=context,
            consequences=consequences,
            uncertainty=uncertainty,
        )

    @staticmethod
    async def export_receipt(
        db: AsyncSession,
        receipt_id: uuid.UUID,
        owner_id: uuid.UUID,
    ) -> dict:
        receipt_detail = await ReceiptService.get_receipt(db, receipt_id, owner_id)
        # Exclude any sensitive identifiers (passwords, raw bank numbers, tokens)
        return {
            "title": "BeforeBorrow Decision Receipt",
            "receipt_id": str(receipt_detail.id),
            "created_at": receipt_detail.created_at.isoformat(),
            "stale": receipt_detail.stale,
            "context": receipt_detail.context,
            "consequences": receipt_detail.consequences,
            "uncertainty": receipt_detail.uncertainty,
            "reflection": receipt_detail.reflection_answers,
            "verified_hash": receipt_detail.context.get("snapshot_hash"),
            "disclaimer": "This decision receipt is an immutable rehearsal record produced by BeforeBorrow. It does not constitute a loan offer, commitment, or legal advice.",
        }
