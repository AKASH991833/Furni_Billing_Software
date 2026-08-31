"""Area and item suggestion services."""
from __future__ import annotations

from sqlalchemy import func

from app.database.database import get_session
from app.models.models import Area, Item


def list_areas(include_other: bool = True) -> list[Area]:
    session = get_session()
    try:
        q = session.query(Area).order_by(Area.sort_order, Area.name)
        return q.all()
    finally:
        session.close()


def add_area(name: str) -> Area:
    session = get_session()
    try:
        area = Area(name=name.strip().upper(), is_system=False)
        session.add(area)
        session.commit()
        session.refresh(area)
        return area
    finally:
        session.close()


def delete_area(name: str) -> bool:
    session = get_session()
    try:
        area = session.query(Area).filter_by(name=name).first()
        if area and not area.is_system:
            session.delete(area)
            session.commit()
            return True
        return False
    finally:
        session.close()


def rename_area(old_name: str, new_name: str) -> bool:
    """Rename an area (and its related items) to keep-dropdown options in sync."""
    session = get_session()
    try:
        area = session.query(Area).filter_by(name=old_name).first()
        if area is None or not new_name.strip():
            return False
        new_name = new_name.strip().upper()
        if session.query(Area).filter(Area.name == new_name, Area.id != area.id).first():
            return False
        area.name = new_name
        for it in session.query(Item).filter(Item.area == old_name).all():
            it.area = new_name
        session.commit()
        return True
    finally:
        session.close()


def list_items(area: str) -> list[Item]:
    """All items (system + custom) belonging to an area, ordered by name."""
    session = get_session()
    try:
        return (
            session.query(Item)
            .filter(Item.area == area)
            .order_by(Item.name)
            .all()
        )
    finally:
        session.close()


def update_item(item_id: int, name: str, area: str) -> bool:
    """Rename / move an existing item to a new area."""
    session = get_session()
    try:
        it = session.query(Item).filter_by(id=item_id).first()
        if it is None or not name.strip():
            return False
        it.name = name.strip()
        it.area = area.strip().upper()
        it.is_custom = True
        it.is_system = False
        session.commit()
        return True
    finally:
        session.close()


def delete_item(item_id: int) -> bool:
    session = get_session()
    try:
        it = session.query(Item).filter_by(id=item_id).first()
        if it is not None:
            session.delete(it)
            session.commit()
            return True
        return False
    finally:
        session.close()


def count_items(area: str) -> int:
    session = get_session()
    try:
        return session.query(Item).filter(Item.area == area).count()
    finally:
        session.close()


def items_for_area(area: str) -> list[Item]:
    session = get_session()
    try:
        return (
            session.query(Item)
            .filter(Item.area == area)
            .order_by(Item.name)
            .all()
        )
    finally:
        session.close()


def suggest_items(area: str, query: str = "", limit: int = 20) -> list[Item]:
    """Context-aware searchable suggestions for a given area."""
    session = get_session()
    try:
        q = session.query(Item).filter(Item.area == area)
        if query:
            pat = f"%{query}%"
            q = q.filter(Item.name.ilike(pat))
        return q.order_by(Item.name).limit(limit).all()
    finally:
        session.close()


def add_custom_item(name: str, area: str) -> Item:
    session = get_session()
    try:
        item = Item(name=name.strip(), area=area.strip().upper(), is_custom=True, is_system=False)
        session.add(item)
        session.commit()
        session.refresh(item)
        return item
    finally:
        session.close()


def get_or_create_item(name: str, area: str) -> Item:
    session = get_session()
    try:
        item = session.query(Item).filter_by(name=name.strip(), area=area.strip().upper()).first()
        if item is None:
            item = add_custom_item(name, area)
        return item
    finally:
        session.close()


def all_system_items() -> list[Item]:
    session = get_session()
    try:
        return session.query(Item).filter(Item.is_system == True).order_by(Item.area, Item.name).all()
    finally:
        session.close()
