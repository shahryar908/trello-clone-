from typing import List

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlmodel import Session, func, select

from ..auth import get_current_user
from ..database import get_session
from ..deps import delete_issue_cascade, get_issue_for_member, get_section_for_member
from ..models import Comment, Issue, IssueLabel, Label, Section, User, utcnow
from ..schemas import (
    CommentAuthor,
    CommentRead,
    IssueCreate,
    IssueDetail,
    IssueMove,
    IssueRead,
    IssueUpdate,
    LabelRead,
)

router = APIRouter(tags=["issues"])


@router.post("/sections/{section_id}/issues", response_model=IssueRead, status_code=201)
def create_issue(
    section_id: int,
    body: IssueCreate,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    section = get_section_for_member(section_id, user, session)
    max_pos = session.exec(
        select(func.max(Issue.position)).where(Issue.section_id == section_id)
    ).first()
    issue = Issue(
        title=body.title,
        description=body.description,
        due_date=body.due_date,
        board_id=section.board_id,
        section_id=section.id,
        position=(max_pos or 0) + 1,
    )
    session.add(issue)
    session.commit()
    session.refresh(issue)
    return issue


@router.get("/issues/{issue_id}", response_model=IssueDetail)
def get_issue(
    issue_id: int,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    issue = get_issue_for_member(issue_id, user, session)
    labels = session.exec(
        select(Label)
        .join(IssueLabel, IssueLabel.label_id == Label.id)
        .where(IssueLabel.issue_id == issue_id)
    ).all()
    return IssueDetail(
        **issue.model_dump(),
        labels=[LabelRead(id=lb.id, name=lb.name, color=lb.color) for lb in labels],
    )


@router.patch("/issues/{issue_id}", response_model=IssueRead)
def update_issue(
    issue_id: int,
    body: IssueUpdate,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    issue = get_issue_for_member(issue_id, user, session)
    data = body.model_dump(exclude_unset=True)
    for field, value in data.items():
        setattr(issue, field, value)
    issue.updated_at = utcnow()
    session.add(issue)
    session.commit()
    session.refresh(issue)
    return issue


@router.patch("/issues/{issue_id}/move", response_model=IssueRead)
def move_issue(
    issue_id: int,
    body: IssueMove,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    issue = get_issue_for_member(issue_id, user, session)
    target = session.get(Section, body.section_id)
    if target is None:
        raise HTTPException(status_code=404, detail="Target section not found")
    if target.board_id != issue.board_id:
        raise HTTPException(status_code=400, detail="Cannot move issue to another board")
    issue.section_id = body.section_id
    issue.position = body.position
    issue.updated_at = utcnow()
    session.add(issue)
    session.commit()
    session.refresh(issue)
    return issue


@router.delete("/issues/{issue_id}", status_code=204)
def delete_issue(
    issue_id: int,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    issue = get_issue_for_member(issue_id, user, session)
    delete_issue_cascade(issue, session)
    session.commit()
    return Response(status_code=204)


@router.get("/issues/{issue_id}/comments", response_model=List[CommentRead])
def list_comments(
    issue_id: int,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    get_issue_for_member(issue_id, user, session)
    rows = session.exec(
        select(Comment, User)
        .join(User, User.id == Comment.user_id)
        .where(Comment.issue_id == issue_id)
        .order_by(Comment.created_at, Comment.id)
    ).all()
    return [
        CommentRead(
            id=c.id,
            body=c.body,
            created_at=c.created_at,
            author=CommentAuthor(id=u.id, email=u.email),
        )
        for c, u in rows
    ]
