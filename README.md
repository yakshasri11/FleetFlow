# FleetFlow

Fleet Management & Logistics Tracking Platform — a centralized backend system for monitoring vehicles, managing drivers, optimizing routes, and tracking shipments in real time.

## Overview

FleetFlow helps logistics companies, delivery services, and fleet operators manage:
- Vehicle tracking and fleet monitoring
- Driver management and trip assignment
- Real-time shipment tracking
- Route optimization
- Vehicle maintenance scheduling
- Fleet utilization and analytics

## Tech Stack

**Backend:** Python, FastAPI, SQLAlchemy, Pydantic, Alembic, Uvicorn
**Database:** PostgreSQL
**Auth:** JWT, OAuth2, Role-Based Access Control

## Project Structure

\`\`\`
FleetFlow/
├── backend/
│   ├── app/
│   │   ├── main.py          # FastAPI entrypoint
│   │   ├── config.py        # App settings
│   │   ├── database.py      # SQLAlchemy engine/session
│   │   ├── models.py        # Database models
│   │   └── routers/         # API route modules
│   └── requirements.txt
\`\`\`

## Setup

\`\`\`bash
# Clone the repository
git clone https://github.com/<your-username>/FleetFlow.git
cd FleetFlow

# Create and activate virtual environment
python -m venv venv
source venv/Scripts/activate    # Windows (Git Bash)

# Install dependencies
cd backend
pip install -r requirements.txt

# Run the server
uvicorn app.main:app --reload
\`\`\`

Server runs at \`http://127.0.0.1:8000\`
API docs available at \`http://127.0.0.1:8000/docs\`

## Status

🚧 In development — Week 1-2 milestone (project setup, core structure)

## License

This project is developed as part of an Infosys Springboot Virtual Intership 7.0.
