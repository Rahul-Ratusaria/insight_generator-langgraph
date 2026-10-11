from typing import Literal
from pydantic import BaseModel, Field

class Evidence(BaseModel):
    quote: str = Field(description="Exact text span from extracted PDF page")
    page: int = Field(ge=1)
    kind: Literal["text", "table", "visual"] = "text"

class Insight(BaseModel):
    observation: str
    implication: str
    confidence: Literal["high", "medium", "low"] = "medium"
    evidence: list[Evidence] = Field(default_factory=list)
    caveat: str = ""

class PageLLMOutput(BaseModel):
    insights: list[Insight] = Field(default_factory=list)

class PageResult(BaseModel):
    page: int
    page_type: str
    status: Literal["accepted", "review", "failed"]
    insights: list[Insight] = Field(default_factory=list)
    issues: list[str] = Field(default_factory=list)
    source_chars: int = 0
    tokens_in: int = 0
    tokens_out: int = 0

class Metric(BaseModel):
    key: str
    label: str
    value: float
    unit: str = ""
    page: int = Field(ge=1)
    quote: str

class AnalyticalInsight(BaseModel):
    title: str
    observation: str
    implication: str
    calculation: str
    confidence: Literal["high", "medium", "low"] = "high"
    evidence: list[Evidence]
    metric_keys: list[str] = Field(default_factory=list)
    caveat: str = ""

class JobOutput(BaseModel):
    job_id: str
    file_name: str
    model: str
    provider: str
    pages: list[PageResult]
    executive_summary: str
    review_pages: list[int]
    metrics: list[Metric] = Field(default_factory=list)
    analytical_insights: list[AnalyticalInsight] = Field(default_factory=list)
