from typing import List

from fastapi import APIRouter, Depends, Response
from sqlmodel import Session, select

from ..auth import get_current_user
from ..database import get_session
from ..deps import (
    delete_section_cascade,
    get_board_for_member,
    get_board_or_404,
    require_admin,
    require_membership,
)
from ..models import Board, Issue, IssueLabel, Label, Section, User, utcnow
from ..schemas import (
    BoardCreate,
    BoardDetail,
    BoardRead,
    BoardUpdate,
    IssueReadWithLabelIds,
    LabelRead,
    SectionWithIssues,
)

router = APIRouter(tags=["boards"])


@router.get("/orgs/{org_id}/boards", response_model=List[BoardRead])
def list_boards(
    org_id: int,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    require_membership(org_id, user, session)
    return session.exec(select(Board).where(Board.organization_id == org_id)).all()


@router.post("/orgs/{org_id}/boards", response_model=BoardRead, status_code=201)
def create_board(
    org_id: int,
    body: BoardCreate,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    require_membership(org_id, user, session)
    board = Board(title=body.title, organization_id=org_id)
    session.add(board)
    session.commit()
    session.refresh(board)
    return board


@router.get("/boards/{board_id}", response_model=BoardDetail)
def get_board_detail(
    board_id: int,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    board = get_board_for_member(board_id, user, session)
    sections = session.exec(
        select(Section).where(Section.board_id == board_id).order_by(Section.position)
    ).all()
    issues = session.exec(
        select(Issue).where(Issue.board_id == board_id).order_by(Issue.position)
    ).all()
    labels = session.exec(select(Label).where(Label.board_id == board_id)).all()

    issue_ids = [i.id for i in issues]
    label_ids_by_issue: dict[int, list[int]] = {i: [] for i in issue_ids}
    if issue_ids:
        for link in session.exec(
            select(IssueLabel).where(IssueLabel.issue_id.in_(issue_ids))
        ):
            label_ids_by_issue[link.issue_id].append(link.label_id)

    return BoardDetail(
        id=board.id,
        title=board.title,
        organization_id=board.organization_id,
        sections=[
            SectionWithIssues(
                id=s.id,
                title=s.title,
                board_id=s.board_id,
                position=s.position,
                issues=[
                    IssueReadWithLabelIds(
                        **i.model_dump(), label_ids=label_ids_by_issue[i.id]
                    )
                    for i in issues
                    if i.section_id == s.id
                ],
            )
            for s in sections
        ],
        labels=[LabelRead(id=lb.id, name=lb.name, color=lb.color) for lb in labels],
    )


@router.patch("/boards/{board_id}", response_model=BoardRead)
def update_board(
    board_id: int,
    body: BoardUpdate,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    board = get_board_for_member(board_id, user, session)
    if body.title is not None:
        board.title = body.title
    board.updated_at = utcnow()
    session.add(board)
    session.commit()
    session.refresh(board)
    return board


@router.delete("/boards/{board_id}", status_code=204)
def delete_board(
    board_id: int,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    board = get_board_or_404(board_id, session)
    require_admin(board.organization_id, user, session)
    for section in session.exec(select(Section).where(Section.board_id == board_id)):
        delete_section_cascade(section, session)
    for label in session.exec(select(Label).where(Label.board_id == board_id)):
        session.delete(label)
    session.delete(board)
    session.commit()
    return Response(status_code=204)
