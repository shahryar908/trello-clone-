from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from ..auth import get_current_user
from ..database import get_session
from ..deps import require_admin, require_membership
from ..models import Membership, Org, User
from ..schemas import MemberAdd, MemberRead, OrgCreate, OrgRead, OrgReadWithRole

router = APIRouter(prefix="/orgs", tags=["orgs"])


@router.post("", response_model=OrgRead, status_code=201)
def create_org(
    body: OrgCreate,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    org = Org(name=body.name, description=body.description)
    session.add(org)
    session.flush()  # assigns org.id without committing yet
    session.add(Membership(user_id=user.id, org_id=org.id, role="admin"))
    session.commit()
    session.refresh(org)
    return org


@router.get("", response_model=List[OrgReadWithRole])
def list_my_orgs(
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    rows = session.exec(
        select(Org, Membership.role)
        .join(Membership, Membership.org_id == Org.id)
        .where(Membership.user_id == user.id)
    ).all()
    return [
        OrgReadWithRole(id=org.id, name=org.name, description=org.description, role=role)
        for org, role in rows
    ]


@router.get("/{org_id}/members", response_model=List[MemberRead])
def list_members(
    org_id: int,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    require_membership(org_id, user, session)
    rows = session.exec(
        select(User, Membership.role)
        .join(Membership, Membership.user_id == User.id)
        .where(Membership.org_id == org_id)
    ).all()
    return [MemberRead(user_id=u.id, email=u.email, role=role) for u, role in rows]


@router.post("/{org_id}/members", response_model=MemberRead, status_code=201)
def add_member(
    org_id: int,
    body: MemberAdd,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    require_admin(org_id, user, session)
    if body.role not in ("member", "admin"):
        raise HTTPException(status_code=422, detail="Role must be 'member' or 'admin'")
    target = session.exec(select(User).where(User.email == body.email)).first()
    if target is None:
        raise HTTPException(status_code=404, detail="No user with that email")
    existing = session.exec(
        select(Membership).where(
            Membership.org_id == org_id, Membership.user_id == target.id
        )
    ).first()
    if existing is not None:
        raise HTTPException(status_code=409, detail="Already a member of this organization")
    membership = Membership(user_id=target.id, org_id=org_id, role=body.role)
    session.add(membership)
    session.commit()
    return MemberRead(user_id=target.id, email=target.email, role=membership.role)
