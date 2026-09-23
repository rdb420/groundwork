"""Starter process catalogue. These are working names to give staff something to link to.
Confirm, rename or retire them after the first stakeholder interviews."""
from sqlalchemy import select
from sqlalchemy.orm import Session as DB

from .models import Process

SEED = {
    "Tenancy": ["Enquiry and application", "Onboarding and agreements", "Rent collection and arrears",
                "Exits and bond"],
    "Property operations": ["Maintenance and repairs", "Inspections and compliance", "Cleaning and supplies"],
    "Portfolio": ["Acquisition and due diligence", "Property setup"],
    "Lending": ["Loan enquiry and origination", "Loan servicing and repayments"],
    "Business support": ["Finance and reporting", "Payroll and people", "IT and systems"],
}


def seed_processes(db: DB) -> None:
    if db.scalar(select(Process.id).limit(1)):
        return
    for area, children in SEED.items():
        parent = Process(name=area, status="proposed")
        db.add(parent)
        db.flush()
        for c in children:
            db.add(Process(name=c, parent_id=parent.id, status="proposed"))
    db.commit()
