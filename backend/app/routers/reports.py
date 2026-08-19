import io
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from openpyxl import Workbook
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer

from app.database import get_db
from app import models
from app.models import UserRole
from app.services.auth_service import require_roles

router = APIRouter(prefix="/reports", tags=["Reports & Export"])

REPORT_TYPES = {
    "fleet_utilization", "fuel_consumption", "driver_performance",
    "delivery_performance", "maintenance",
}


def _fleet_utilization_rows(db: Session):
    vehicles = db.query(models.Vehicle).all()
    header = ["Vehicle ID", "Registration No.", "Type", "Status", "Total Trips", "Completed Trips"]
    rows = []
    for v in vehicles:
        trips = db.query(models.Trip).filter(models.Trip.deleted == "false").filter(models.Trip.vehicle_id == v.id)
        rows.append([
            v.id, v.registration_number, v.vehicle_type, v.status.value,
            trips.count(), trips.filter(models.Trip.status == TripStatus.COMPLETED).count(),
        ])
    return header, rows


def _fuel_consumption_rows(db: Session):
    records = db.query(models.FuelRecord).order_by(models.FuelRecord.fuel_date.desc()).all()
    header = ["Record ID", "Vehicle ID", "Driver ID", "Liters", "Cost", "Odometer", "Date", "Station"]
    rows = [[
        r.id, r.vehicle_id, r.driver_id, r.fuel_quantity_liters, r.fuel_cost,
        r.odometer_reading, r.fuel_date.strftime("%Y-%m-%d"), r.fuel_station or "-",
    ] for r in records]
    return header, rows


def _driver_performance_rows(db: Session):
    drivers = db.query(models.Driver).all()
    header = ["Driver ID", "Name", "License No.", "Status", "Total Trips", "Completed", "Active", "Cancelled"]
    rows = []
    for d in drivers:
        trips = db.query(models.Trip).filter(models.Trip.deleted == "false").filter(models.Trip.driver_id == d.id)
        rows.append([
            d.id, d.name, d.license_number, d.status, trips.count(),
            trips.filter(models.Trip.status == TripStatus.COMPLETED).count(),
            trips.filter(models.Trip.status.in_([TripStatus.SCHEDULED, TripStatus.IN_PROGRESS])).count(),
            trips.filter(models.Trip.status == TripStatus.CANCELLED).count(),
        ])
    return header, rows


def _delivery_performance_rows(db: Session):
    shipments = db.query(models.Shipment).filter(models.Shipment.deleted == "false").order_by(models.Shipment.created_at.desc()).all()
    header = ["Shipment ID", "Tracking No.", "Origin", "Destination", "Status", "ETA", "Created"]
    rows = [[
        s.id, s.tracking_number, s.origin, s.destination, s.status.value,
        s.eta.strftime("%Y-%m-%d %H:%M") if s.eta else "-",
        s.created_at.strftime("%Y-%m-%d %H:%M") if s.created_at else "-",
    ] for s in shipments]
    return header, rows


def _maintenance_rows(db: Session):
    records = db.query(models.Maintenance).filter(models.Maintenance.is_archived == "false").all()
    header = ["Record ID", "Vehicle ID", "Category", "Service Date", "Next Service", "Cost", "Status"]
    rows = [[
        m.id, m.vehicle_id, m.category.value, m.service_date.strftime("%Y-%m-%d"),
        m.next_service_date.strftime("%Y-%m-%d") if m.next_service_date else "-",
        m.service_cost or 0, m.status.value,
    ] for m in records]
    return header, rows


_BUILDERS = {
    "fleet_utilization": _fleet_utilization_rows,
    "fuel_consumption": _fuel_consumption_rows,
    "driver_performance": _driver_performance_rows,
    "delivery_performance": _delivery_performance_rows,
    "maintenance": _maintenance_rows,
}


def _get_rows(report_type: str, db: Session):
    if report_type not in REPORT_TYPES:
        raise HTTPException(status_code=400, detail=f"Unknown report type. Choose one of: {sorted(REPORT_TYPES)}")
    return _BUILDERS[report_type](db)


@router.get("/{report_type}/pdf")
def export_pdf(report_type: str, db: Session = Depends(get_db), current_user: models.User = Depends(require_roles(UserRole.ADMIN, UserRole.FLEET_MANAGER))):
    header, rows = _get_rows(report_type, db)

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4)
    styles = getSampleStyleSheet()
    title = report_type.replace("_", " ").title() + " Report"

    elements = [
        Paragraph("FleetFlow — " + title, styles["Title"]),
        Paragraph(f"Generated {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}", styles["Normal"]),
        Spacer(1, 12),
    ]

    table_data = [header] + [[str(c) for c in row] for row in rows] if rows else [header, ["No data available"]]
    table = Table(table_data, repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e3a5f")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f2f5f9")]),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    elements.append(table)
    doc.build(elements)
    buf.seek(0)

    return StreamingResponse(
        buf, media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="fleetflow_{report_type}_report.pdf"'},
    )


@router.get("/{report_type}/excel")
def export_excel(report_type: str, db: Session = Depends(get_db), current_user: models.User = Depends(require_roles(UserRole.ADMIN, UserRole.FLEET_MANAGER))):
    header, rows = _get_rows(report_type, db)

    wb = Workbook()
    ws = wb.active
    ws.title = report_type[:31]
    ws.append(header)
    for cell in ws[1]:
        cell.font = cell.font.copy(bold=True)
    for row in rows:
        ws.append(row)
    for col in ws.columns:
        width = max((len(str(c.value)) for c in col if c.value is not None), default=10)
        ws.column_dimensions[col[0].column_letter].width = min(max(width + 2, 10), 40)

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)

    return StreamingResponse(
        buf, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="fleetflow_{report_type}_report.xlsx"'},
    )
