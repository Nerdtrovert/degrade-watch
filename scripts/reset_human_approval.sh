#!/bin/bash
echo "Resetting Scenario H back to PENDING state..."
docker compose exec -T backend python -c "
import sys; sys.path.insert(0, '/app/backend')
from app.database import SessionLocal
from app.models.recovery import Recovery
from app.models.incident import Incident
import uuid
from datetime import datetime, timezone
db = SessionLocal()
inc = db.query(Incident).filter(Incident.incident_id == 'scenario_h_merchant_20260822_120000').first()
if inc:
    recs = db.query(Recovery).filter(Recovery.incident_id == inc.id).all()
    for r in recs:
        db.delete(r)
    db.commit()
    r = Recovery(
        id=uuid.uuid4(),
        incident_id=inc.id,
        action_type='PAYMENT_LINK',
        amount_paise=15000,
        currency='INR',
        state='PENDING',
        recovered_amount_paise=0,
        created_at=datetime.now(timezone.utc),
        idempotency_key='seed_' + str(uuid.uuid4())
    )
    db.add(r)
    db.commit()
    print('✅ Successfully reset Scenario H back to PENDING!')
"
