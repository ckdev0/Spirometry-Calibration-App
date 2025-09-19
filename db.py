# -*- coding: utf-8 -*-
"""
Created on Fri Sep 12 12:52:24 2025
@author: Tejaswini
db.py
Database models and helper functions for Calibration App.
Uses SQLite with SQLAlchemy ORM.
"""
from sqlalchemy import create_engine, Column, Integer, String, DateTime, JSON, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
import datetime

Base = declarative_base()
engine = create_engine("sqlite:///calibration.db", echo=False)  # set echo=True for SQL logs
Session = sessionmaker(bind=engine)
session = Session()

#Device Table
class Device(Base):
    __tablename__ = "devices"
    id = Column(Integer, primary_key=True, autoincrement=True)
    device_id = Column(String, unique=True, nullable=False)
    coefficients = Column(JSON)   # <--- store all coeffs here
    date_of_calibration = Column(DateTime, default=datetime.datetime.utcnow)
    calibrations = relationship("Calibration", back_populates="device")

class Calibration(Base):
    __tablename__ = "calibrations"
    id = Column(Integer, primary_key=True, autoincrement=True)
    device_id = Column(Integer, ForeignKey("devices.id"))
    date = Column(DateTime, default=datetime.datetime.utcnow)
    samples = Column(JSON)
    coefficients = Column(JSON)
    status = Column(String)
    device = relationship("Device", back_populates="calibrations")

    
#Create tables
Base.metadata.create_all(engine)

# Simple migration to add missing columns when upgrading schema
def _column_exists(table_name: str, column_name: str) -> bool:
    with engine.connect() as conn:
        res = conn.exec_driver_sql(f"PRAGMA table_info({table_name})")
        cols = [row[1] for row in res]
        return column_name in cols

def _add_column_if_missing(table_name: str, column_def_sql: str):
    col_name = column_def_sql.split()[0]
    if not _column_exists(table_name, col_name):
        with engine.begin() as conn:
            conn.exec_driver_sql(f"ALTER TABLE {table_name} ADD COLUMN {column_def_sql}")

def migrate_schema():
    # devices table: ensure 'coefficients' column exists
    try:
        _add_column_if_missing("devices", "coefficients TEXT")
    except Exception:
        pass
    # calibrations table: ensure 'coefficients' and 'status' exist
    try:
        _add_column_if_missing("calibrations", "coefficients TEXT")
    except Exception:
        pass
    try:
        _add_column_if_missing("calibrations", "status TEXT")
    except Exception:
        pass

migrate_schema()

#Helper functions
def add_device(device_id, coeffs=None):
    existing = session.query(Device).filter_by(device_id=device_id).first()
    if existing:
        return existing
    new_device = Device(device_id=device_id, coefficients=list(coeffs) if coeffs is not None else [])
    session.add(new_device)
    session.commit()
    return new_device

def update_device_coeffs(device_id, new_coeffs, samples=None, status="success"):
    device = get_device(device_id)
    if not device:
        raise ValueError("Device not found")

    device.coefficients = list(new_coeffs)
    device.date_of_calibration = datetime.datetime.utcnow()

    calib = Calibration(
        device=device,
        samples=samples or {},
        coefficients=list(new_coeffs),
        status=status,
    )
    session.add(calib)
    session.commit()
    return device

def get_device(device_id):
    return session.query(Device).filter_by(device_id=device_id).first()

def list_devices():
    return session.query(Device).order_by(Device.date_of_calibration.desc()).all()

def list_calibrations(device_id):
    device = get_device(device_id)
    if not device:
        return []
    return session.query(Calibration).filter_by(device_id=device.id).order_by(Calibration.date.desc()).all()

def get_last_successful_coeffs(device_id):
    device = get_device(device_id)
    if not device:
        return None
    last_success = (
        session.query(Calibration)
        .filter_by(device_id=device.id, status="success")
        .order_by(Calibration.date.desc())
        .first()
    )
    if last_success and last_success.coefficients:
        return last_success.coefficients
    # fallback to current stored coefficients on device
    return device.coefficients

def revert_to_last_success(device_id, samples=None):
    coeffs = get_last_successful_coeffs(device_id)
    if coeffs is None:
        raise ValueError("No previous successful coefficients found to revert to")
    return update_device_coeffs(device_id, coeffs, samples=samples, status="reverted")



                        