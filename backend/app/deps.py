from fastapi import HTTPException
from sqlmodel import Session, select

from .models import Board, Comment, Issue, IssueLabel, Membership, Org, Section, User


def require_membership(org_id: int, user: User, session: Session) -> Membership:
    org = session.get(Org, org_id)
    if org is None:
        raise HTTPException(status_code=404, detail="Organization not found")
    membership = session.exec(
        select(Membership).where(Membership.org_id == org_id, Membership.user_id == user.id)
    ).first()
    if membership is None:
        raise HTTPException(status_code=403, detail="Not a member of this organization")
    return membership


def require_admin(org_id: int, user: User, session: Session) -> Membership:
    membership = require_membership(org_id, user, session)
    if membership.role != "admin":
        raise HTTPException(status_code=403, detail="Admin role required")
    return membership


def get_board_or_404(board_id: int, session: Session) -> Board:
    board = session.get(Board, board_id)
    if board is None:
        raise HTTPException(status_code=404, detail="Board not found")
    return board


def get_board_for_member(board_id: int, user: User, session: Session) -> Board:
    board = get_board_or_404(board_id, session)
    require_membership(board.organization_id, user, session)
    return board


def get_section_for_member(section_id: int, user: User, session: Session) -> Section:
    section = session.get(Section, section_id)
    if section is None:
        raise HTTPException(status_code=404, detail="Section not found")
    board = get_board_or_404(section.board_id, session)
    require_membership(board.organization_id, user, session)
    return section


def get_issue_for_member(issue_id: int, user: User, session: Session) -> Issue:
    issue = session.get(Issue, issue_id)
    if issue is None:
        raise HTTPException(status_code=404, detail="Issue not found")
    board = get_board_or_404(issue.board_id, session)
    require_membership(board.organization_id, user, session)
    return issue


def delete_issue_cascade(issue: Issue, session: Session) -> None:
    for comment in session.exec(select(Comment).where(Comment.issue_id == issue.id)):
        session.delete(comment)
    for link in session.exec(select(IssueLabel).where(IssueLabel.issue_id == issue.id)):
        session.delete(link)
    session.delete(issue)


def delete_section_cascade(section: Section, session: Session) -> None:
    for issue in session.exec(select(Issue).where(Issue.section_id == section.id)):
        delete_issue_cascade(issue, session)
    session.delete(section)
