from __future__ import annotations

import json

from services.cotizaciones import list_quotes, load_agent_directory
from services.gestion_comercial import ensure_opportunity_for_quote


def main() -> None:
    agents = load_agent_directory()
    quotes = list_quotes()
    created = existing = unmatched = 0
    details = []
    for quote in quotes:
        agent = next((item for item in agents if (
            item["promotoria"] == quote.get("promotoria")
            and item["key"] == quote.get("clave_agente")
        )), None)
        if not agent:
            unmatched += 1
            details.append({"quote_id": quote["id"], "status": "agent_not_found"})
            continue
        from services.gestion_comercial import opportunity_id_for_quote

        before = opportunity_id_for_quote(quote["id"])
        opportunity_id = ensure_opportunity_for_quote(
            quote,
            actor="backfill@taiico-crm.local",
            agent_rfc=agent["rfc"],
        )
        if before:
            existing += 1
        else:
            created += 1
        details.append({"quote_id": quote["id"], "opportunity_id": opportunity_id})
    print(json.dumps({
        "quotes": len(quotes),
        "created": created,
        "existing": existing,
        "unmatched": unmatched,
        "details": details,
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
