from datetime import date, datetime
from typing import Optional

from sqlmodel import Field, SQLModel, UniqueConstraint


def utcnow() -> datetime:
    return datetime.utcnow()


class User(SQLModel, table=True):
    __tablename__ = "users"

    id: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(unique=True, index=True)
    password: str  # bcrypt hash, never plain text


class Org(SQLModel, table=True):
    __tablename__ = "orgs"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    description: Optional[str] = None


class Membership(SQLModel, table=True):
    __tablename__ = "memberships"
    __table_args__ = (UniqueConstraint("user_id", "org_id"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id")
    org_id: int = Field(foreign_key="orgs.id")
    role: str = "member"  # "member" | "admin"


class Board(SQLModel, table=True):
    __tablename__ = "boards"

    id: Optional[int] = Field(default=None, primary_key=True)
    title: str
    organization_id: int = Field(foreign_key="orgs.id")
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class Section(SQLModel, table=True):
    __tablename__ = "sections"

    id: Optional[int] = Field(default=None, primary_key=True)
    title: str
    board_id: int = Field(foreign_key="boards.id")
    position: float


class Issue(SQLModel, table=True):
    __tablename__ = "issues"

    id: Optional[int] = Field(default=None, primary_key=True)
    title: str
    description: Optional[str] = None
    # denormalized on purpose: always equals its section's board_id
    board_id: int = Field(foreign_key="boards.id")
    section_id: int = Field(foreign_key="sections.id")
    position: float
    due_date: Optional[date] = None
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class Label(SQLModel, table=True):
    __tablename__ = "labels"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    color: str  # hex string like "#ef4444"
    board_id: int = Field(foreign_key="boards.id")


class IssueLabel(SQLModel, table=True):
    __tablename__ = "issue_labels"
    __table_args__ = (UniqueConstraint("issue_id", "label_id"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    issue_id: int = Field(foreign_key="issues.id")
    label_id: int = Field(foreign_key="labels.id")


class Comment(SQLModel, table=True):
    __tablename__ = "comments"

    id: Optional[int] = Field(default=None, primary_key=True)
    body: str
    issue_id: int = Field(foreign_key="issues.id")
    user_id: int = Field(foreign_key="users.id")
    created_at: datetime = Field(default_factory=utcnow)
