from datetime import date, datetime
from typing import List, Optional

from sqlmodel import SQLModel


# --- auth ---

class SignupRequest(SQLModel):
    email: str
    password: str


class LoginRequest(SQLModel):
    email: str
    password: str


class UserRead(SQLModel):
    id: int
    email: str


class TokenResponse(SQLModel):
    access_token: str
    token_type: str = "bearer"


# --- orgs / members ---

class OrgCreate(SQLModel):
    name: str
    description: Optional[str] = None


class OrgRead(SQLModel):
    id: int
    name: str
    description: Optional[str] = None


class OrgReadWithRole(OrgRead):
    role: str


class MemberAdd(SQLModel):
    email: str
    role: str = "member"


class MemberRead(SQLModel):
    user_id: int
    email: str
    role: str


# --- boards ---

class BoardCreate(SQLModel):
    title: str


class BoardUpdate(SQLModel):
    title: Optional[str] = None


class BoardRead(SQLModel):
    id: int
    title: str
    organization_id: int
    created_at: datetime
    updated_at: datetime


# --- sections ---

class SectionCreate(SQLModel):
    title: str


class SectionUpdate(SQLModel):
    title: Optional[str] = None
    position: Optional[float] = None


class SectionRead(SQLModel):
    id: int
    title: str
    board_id: int
    position: float


# --- issues ---

class IssueCreate(SQLModel):
    title: str
    description: Optional[str] = None
    due_date: Optional[date] = None


class IssueUpdate(SQLModel):
    title: Optional[str] = None
    description: Optional[str] = None
    due_date: Optional[date] = None


class IssueMove(SQLModel):
    section_id: int
    position: float


class IssueRead(SQLModel):
    id: int
    title: str
    description: Optional[str] = None
    board_id: int
    section_id: int
    position: float
    due_date: Optional[date] = None
    created_at: datetime
    updated_at: datetime


class IssueReadWithLabelIds(IssueRead):
    label_ids: List[int] = []


# --- labels ---

class LabelCreate(SQLModel):
    name: str
    color: str


class LabelRead(SQLModel):
    id: int
    name: str
    color: str


class LabelAttach(SQLModel):
    label_id: int


class IssueDetail(IssueRead):
    labels: List[LabelRead] = []


# --- board detail (the big GET /boards/{id} payload) ---

class SectionWithIssues(SectionRead):
    issues: List[IssueReadWithLabelIds] = []


class BoardDetail(SQLModel):
    id: int
    title: str
    organization_id: int
    sections: List[SectionWithIssues] = []
    labels: List[LabelRead] = []


# --- comments ---

class CommentAuthor(SQLModel):
    id: int
    email: str


class CommentRead(SQLModel):
    id: int
    body: str
    created_at: datetime
    author: CommentAuthor
