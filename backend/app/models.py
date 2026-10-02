from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class TestCaseType(StrEnum):
    POSITIVE = "positive"
    NEGATIVE = "negative"
    BOUNDARY = "boundary"
    EDGE = "edge"


class TestCasePriority(StrEnum):
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"


class TestCase(BaseModel):
    tc_id: str
    module: str
    scenario: str
    preconditions: str = ""
    steps: list[str] = Field(default_factory=list)
    test_data: str = ""
    expected_result: str
    priority: TestCasePriority = TestCasePriority.P2
    case_type: TestCaseType = TestCaseType.POSITIVE
    source_section: str = ""  # which chunk/section this was derived from — for traceability


class DocumentChunk(BaseModel):
    chunk_id: str
    document_name: str
    section_title: str = ""
    text: str
    page_or_sheet: str = ""
    embedding: list[float] | None = None


class JobStatus(StrEnum):
    PENDING = "pending"
    EXTRACTING = "extracting"
    EMBEDDING = "embedding"
    GENERATING = "generating"
    COMPLETED = "completed"
    FAILED = "failed"


class Job(BaseModel):
    job_id: str
    status: JobStatus = JobStatus.PENDING
    progress_percent: int = 0
    current_stage: str = ""
    error_message: str | None = None
    test_cases: list[TestCase] = Field(default_factory=list)
    document_names: list[str] = Field(default_factory=list)
    excel_path: str | None = None
