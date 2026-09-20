from __future__ import annotations

import datetime
import unicodedata
from decimal import Decimal

from database import (
    Policy,
    PolicyProspectorAssignment,
    Prospector,
    ProspectorCommissionAllocation,
    ProspectorOpeningBalance,
)


def _normalized_name(value: object) -> str:
    text = " ".join(str(value or "").strip().split()).upper()
    return "".join(
        character for character in unicodedata.normalize("NFKD", text)
        if not unicodedata.combining(character)
    )


def _move_allocation(db, allocation: ProspectorCommissionAllocation, target_id: str) -> None:
    collision = db.query(ProspectorCommissionAllocation).filter(
        ProspectorCommissionAllocation.line_id == allocation.line_id,
        ProspectorCommissionAllocation.prospector_id == target_id,
        ProspectorCommissionAllocation.id != allocation.id,
    ).first()
    if collision:
        raise ValueError(
            "No se puede consolidar automáticamente porque ambos prospectadores "
            "ya tienen comisión calculada sobre el mismo movimiento."
        )
    allocation.prospector_id = target_id


def cartera_assignment_window(policy: Policy):
    raw = (policy.metadata_json or {}).get("payment_start_date")
    if not raw:
        return datetime.date.min, None
    start = datetime.date.fromisoformat(str(raw))
    try:
        end = start.replace(year=start.year + 1)
    except ValueError:
        end = start.replace(year=start.year + 1, day=28)
    return start, end


def reassign_policy_to_named_prospector(db, policy: Policy, name: str) -> bool:
    """Keep a single-policy Cartera edit aligned with the master prospector catalog."""
    normalized = _normalized_name(name)
    if not normalized:
        return False
    targets = db.query(Prospector).filter(Prospector.normalized_name == normalized).all()
    assignments = db.query(PolicyProspectorAssignment).filter(
        PolicyProspectorAssignment.policy_id == policy.id,
        PolicyProspectorAssignment.is_active.is_(True),
    ).all()
    if len(targets) != 1 or len(assignments) > 1:
        return False
    target = targets[0]
    start, end = cartera_assignment_window(policy)
    if not assignments:
        rate = Decimal(str(policy.commission_percentage or 0))
        if rate > 1:
            rate /= 100
        db.add(PolicyProspectorAssignment(
            policy_id=policy.id, prospector_id=target.id, commission_rate=rate,
            effective_from=start, effective_to=end, source="cartera_edit",
            created_by=policy.responsible_user_id,
        ))
        return True
    assignment = assignments[0]
    rate = Decimal(str(policy.commission_percentage or 0))
    assignment.commission_rate = rate / 100 if rate > 1 else rate
    if assignment.source in {"cartera_migration", "cartera_edit"}:
        assignment.effective_from, assignment.effective_to = start, end
    if assignment.prospector_id == target.id:
        return False

    duplicate = db.query(PolicyProspectorAssignment).filter(
        PolicyProspectorAssignment.policy_id == assignment.policy_id,
        PolicyProspectorAssignment.prospector_id == target.id,
        PolicyProspectorAssignment.effective_from == assignment.effective_from,
        PolicyProspectorAssignment.source == assignment.source,
        PolicyProspectorAssignment.id != assignment.id,
    ).first()
    if duplicate:
        raise ValueError("La póliza ya tiene una asignación equivalente para el prospectador seleccionado.")
    for allocation in db.query(ProspectorCommissionAllocation).filter(
        ProspectorCommissionAllocation.assignment_id == assignment.id
    ).all():
        _move_allocation(db, allocation, target.id)
    assignment.prospector_id = target.id
    return True


def merge_prospectors(db, *, source_id: str, target_id: str, actor: str) -> dict:
    if source_id == target_id:
        raise ValueError("El prospectador duplicado y el principal deben ser distintos.")
    source = db.get(Prospector, source_id)
    target = db.get(Prospector, target_id)
    if not source or not target:
        raise ValueError("No se encontraron ambos prospectadores para consolidar.")

    moved_assignments = 0
    assignments = db.query(PolicyProspectorAssignment).filter(
        PolicyProspectorAssignment.prospector_id == source.id
    ).all()
    affected_policy_ids = {assignment.policy_id for assignment in assignments}
    for assignment in assignments:
        duplicate = db.query(PolicyProspectorAssignment).filter(
            PolicyProspectorAssignment.policy_id == assignment.policy_id,
            PolicyProspectorAssignment.prospector_id == target.id,
            PolicyProspectorAssignment.effective_from == assignment.effective_from,
            PolicyProspectorAssignment.source == assignment.source,
            PolicyProspectorAssignment.id != assignment.id,
        ).first()
        allocations = db.query(ProspectorCommissionAllocation).filter(
            ProspectorCommissionAllocation.assignment_id == assignment.id
        ).all()
        if duplicate:
            if (
                Decimal(str(duplicate.commission_rate)) != Decimal(str(assignment.commission_rate))
                or duplicate.effective_to != assignment.effective_to
                or duplicate.is_active != assignment.is_active
            ):
                raise ValueError(
                    "Hay asignaciones distintas para la misma póliza; revisa sus porcentajes y vigencias antes de consolidar."
                )
            for allocation in allocations:
                _move_allocation(db, allocation, target.id)
                allocation.assignment_id = duplicate.id
            db.delete(assignment)
        else:
            for allocation in allocations:
                _move_allocation(db, allocation, target.id)
            assignment.prospector_id = target.id
        moved_assignments += 1

    for allocation in db.query(ProspectorCommissionAllocation).filter(
        ProspectorCommissionAllocation.prospector_id == source.id
    ).all():
        _move_allocation(db, allocation, target.id)

    moved_balances = 0
    for balance in db.query(ProspectorOpeningBalance).filter(
        ProspectorOpeningBalance.prospector_id == source.id
    ).all():
        existing = db.query(ProspectorOpeningBalance).filter(
            ProspectorOpeningBalance.period_id == balance.period_id,
            ProspectorOpeningBalance.prospector_id == target.id,
        ).first()
        if existing:
            existing.amount = Decimal(str(existing.amount)) + Decimal(str(balance.amount))
            notes = [text for text in (existing.notes, balance.notes) if text]
            existing.notes = " | ".join(dict.fromkeys(notes)) or None
            db.delete(balance)
        else:
            balance.prospector_id = target.id
        moved_balances += 1

    for policy in db.query(Policy).filter(Policy.id.in_(affected_policy_ids)).all() if affected_policy_ids else []:
        metadata = dict(policy.metadata_json or {})
        metadata["prospector"] = target.name
        policy.metadata_json = metadata

    if not target.rfc and source.rfc:
        source_rfc = source.rfc
        source.rfc = None
        db.flush()
        target.rfc = source_rfc
    if not target.email and source.email:
        target.email = source.email
    target.additional_emails = sorted({
        *(target.additional_emails or []),
        *(source.additional_emails or []),
        *([source.email] if source.email and source.email != target.email else []),
    })
    metadata = dict(target.metadata_json or {})
    aliases = list(metadata.get("name_aliases") or [])
    if source.name not in aliases:
        aliases.append(source.name)
    merged_ids = list(metadata.get("merged_prospector_ids") or [])
    if source.id not in merged_ids:
        merged_ids.append(source.id)
    metadata.update({
        "name_aliases": aliases,
        "merged_prospector_ids": merged_ids,
        "last_merge_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "last_merge_by": actor,
    })
    target.metadata_json = metadata
    db.delete(source)
    db.flush()
    return {
        "target_id": target.id,
        "target_name": target.name,
        "removed_source_id": source_id,
        "moved_assignments": moved_assignments,
        "moved_balances": moved_balances,
    }
