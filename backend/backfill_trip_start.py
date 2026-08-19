import sys
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

if len(sys.argv) < 2:
    print("Usage: python backfill_trip_start.py <DATABASE_URL>")
    sys.exit(1)

url = sys.argv[1]
engine = create_engine(url)
Session = sessionmaker(bind=engine)
db = Session()

from app.models import Trip

trips = db.query(Trip).filter(Trip.scheduled_start.is_(None)).all()
print(f"Found {len(trips)} trip(s) missing scheduled_start")

for t in trips:
    t.scheduled_start = t.created_at or datetime.utcnow()
    print(f"  Trip {t.id}: set scheduled_start = {t.scheduled_start}")

db.commit()
print("Done.")
