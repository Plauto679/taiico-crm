from fastapi import APIRouter, HTTPException, Query
from database import SessionLocal, Policy, Client

router = APIRouter(prefix="/cartera", tags=["cartera"])

@router.get("/data")
async def get_cartera_data(
    insurer: str = Query(..., description="Insurer name"),
    type: str = Query("ALL", description="Policy type: ALL, VIDA, GMM")
):
    db = SessionLocal()
    try:
        results = []
        
        # Load policies joining the client relationship
        query = db.query(Policy).join(Client)
        
        if insurer.lower() == "metlife":
            query = query.filter(Policy.insurer_id == "metlife")
            if type.upper() == "VIDA":
                query = query.filter(Policy.product_id == "prod_met_vida")
            elif type.upper() == "GMM":
                query = query.filter(Policy.product_id == "prod_met_gmm")
                
            policies = query.all()
            
            for pol in policies:
                prospectador = pol.client.metadata_json.get("prospectador", "") if pol.client else ""
                
                # Vida sheet specific headers vs GMM sheet headers
                if pol.product_id == "prod_met_vida":
                    results.append({
                        "Poliza": pol.policy_number,
                        "Contratante": pol.client.full_name if pol.client else "",
                        "PROSPECTADOR ": prospectador,
                        "PORCENTAJE ": float(pol.commission_percentage) if pol.commission_percentage is not None else None
                    })
                else:
                    results.append({
                        "POLIZA ": pol.policy_number,
                        "Poliza actual": pol.policy_number,
                        "Contratante": pol.client.full_name if pol.client else "",
                        "PROSPECTADOR ": prospectador,
                        "PORCENTAJE": float(pol.commission_percentage) if pol.commission_percentage is not None else None
                    })
                    
        elif insurer.lower() == "sura":
            query = query.filter(Policy.insurer_id == "sura")
            policies = query.all()
            
            for pol in policies:
                prospectador = pol.client.metadata_json.get("prospectador", "") if pol.client else ""
                results.append({
                    "PÓLIZA": pol.policy_number,
                    "PROSPECTADOR": prospectador,
                    "PORCENTAJE": float(pol.commission_percentage) if pol.commission_percentage is not None else None
                })
                
        return results

    except Exception as e:
        print(f"Error fetching cartera data: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()

@router.get("/search")
async def search_cartera(query: str = Query(..., min_length=1)):
    """Unified search over policies and clients."""
    db = SessionLocal()
    try:
        results = []
        term = f"%{query}%"
        policies = db.query(Policy).join(Client).filter(
            (Policy.policy_number.like(term)) | (Client.full_name.like(term))
        ).limit(50).all()
        
        for pol in policies:
            results.append({
                "poliza": pol.policy_number,
                "contratante": pol.client.full_name if pol.client else "",
                "aseguradora": pol.insurer_id.upper(),
                "estatus": pol.status,
                "ramo": pol.product.branch if pol.product else ""
            })
        return results
    except Exception as e:
        print(f"Search error: {e}")
        return []
    finally:
        db.close()
