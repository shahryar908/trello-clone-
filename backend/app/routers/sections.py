from fastapi import APIRouter, Depends, Response
from sqlmodel import Session, func, select

from ..auth import get_current_user
from ..database import get_session
from ..deps import delete_section_cascade, get_board_for_member, get_section_for_member
from ..models import Section, User
from ..schemas import SectionCreate, SectionRead, SectionUpdate

router = APIRouter(tags=["sections"])


@router.post("/boards/{board_id}/sections", response_model=SectionRead, status_code=201)
def create_section(
    board_id: int,
    body: SectionCreate,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    get_board_for_member(board_id, user, session)
    max_pos = session.exec(
        select(func.max(Section.position)).where(Section.board_id == board_id)
    ).first()
    section = Section(title=body.title, board_id=board_id, position=(max_pos or 0) + 1)
    session.add(section)
    session.commit()
    session.refresh(section)
    return section


@router.patch("/sections/{section_id}", response_model=SectionRead)
def update_section(
    section_id: int,
    body: SectionUpdate,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    section = get_section_for_member(section_id, user, session)
    data = body.model_dump(exclude_unset=True)
    for field, value in data.items():
        setattr(section, field, value)
    session.add(section)
    session.commit()
    session.refresh(section)
    return section


@router.delete("/sections/{section_id}", status_code=204)
def delete_section(
    section_id: int,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    section = get_section_for_member(section_id, user, session)
    delete_section_cascade(section, session)
    session.commit()
    return Response(status_code=204)
