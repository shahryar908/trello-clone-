from typing import List

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlmodel import Session, select

from ..auth import get_current_user
from ..database import get_session
from ..deps import get_board_for_member, get_issue_for_member
from ..models import IssueLabel, Label, User
from ..schemas import LabelAttach, LabelCreate, LabelRead

router = APIRouter(tags=["labels"])


@router.get("/boards/{board_id}/labels", response_model=List[LabelRead])
def list_labels(
    board_id: int,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    get_board_for_member(board_id, user, session)
    return session.exec(select(Label).where(Label.board_id == board_id)).all()


@router.post("/boards/{board_id}/labels", response_model=LabelRead, status_code=201)
def create_label(
    board_id: int,
    body: LabelCreate,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    get_board_for_member(board_id, user, session)
    label = Label(name=body.name, color=body.color, board_id=board_id)
    session.add(label)
    session.commit()
    session.refresh(label)
    return label


@router.post("/issues/{issue_id}/labels", response_model=LabelRead, status_code=201)
def attach_label(
    issue_id: int,
    body: LabelAttach,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    issue = get_issue_for_member(issue_id, user, session)
    label = session.get(Label, body.label_id)
    if label is None:
        raise HTTPException(status_code=404, detail="Label not found")
    if label.board_id != issue.board_id:
        raise HTTPException(status_code=400, detail="Label belongs to a different board")
    existing = session.exec(
        select(IssueLabel).where(
            IssueLabel.issue_id == issue_id, IssueLabel.label_id == body.label_id
        )
    ).first()
    if existing is not None:
        raise HTTPException(status_code=409, detail="Label already attached")
    session.add(IssueLabel(issue_id=issue_id, label_id=body.label_id))
    session.commit()
    return label


@router.delete("/issues/{issue_id}/labels/{label_id}", status_code=204)
def detach_label(
    issue_id: int,
    label_id: int,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    get_issue_for_member(issue_id, user, session)
    link = session.exec(
        select(IssueLabel).where(
            IssueLabel.issue_id == issue_id, IssueLabel.label_id == label_id
        )
    ).first()
    if link is None:
        raise HTTPException(status_code=404, detail="Label not attached to this issue")
    session.delete(link)
    session.commit()
    return Response(status_code=204)
