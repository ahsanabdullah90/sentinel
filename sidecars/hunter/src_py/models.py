"""Models Module

Defines Pydantic models for configuration and scraped data validation.
"""

from typing import Optional, Literal
from pydantic import BaseModel, Field, ConfigDict

class PortalConfig(BaseModel):
    """Pydantic model representing portal configuration."""
    id: str
    name: str
    base_url: str = Field(alias="baseUrl")
    auth_method: str = Field(default="public", alias="authMethod")
    scraper_module: str = Field(default="generic_search", alias="scraperModule")
    active_window_start: Optional[str] = Field(default=None, alias="activeWindowStart")
    active_window_end: Optional[str] = Field(default=None, alias="activeWindowEnd")
    requests_per_minute: int = Field(default=15, alias="requestsPerMinute")
    keywords: Optional[str] = None
    selector_config: Optional[str] = Field(default=None, alias="selectorConfig")

    model_config = ConfigDict(populate_by_name=True)

class RFPOpportunity(BaseModel):
    """Pydantic model representing a scraped RFP Opportunity."""
    id: str
    portal_id: str = Field(alias="portalId")
    title: str = Field(default="Untitled Opportunity")
    description: str = ""
    url: str
    publish_date: str = Field(default="", alias="publishDate")
    due_date: str = Field(default="", alias="dueDate")
    agency: str = "Unknown"
    status: Literal["open", "closed", "archived"] = "open"

    model_config = ConfigDict(populate_by_name=True)

class OllamaExtraction(BaseModel):
    """Expected JSON shape returned from local Ollama model extraction."""
    title: str = "Untitled Opportunity"
    description: str = ""
    url: str = ""
    publishDate: str = ""
    dueDate: str = ""
    agency: str = "Unknown"
