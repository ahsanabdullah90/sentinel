from src_py.models import PortalConfig, RFPOpportunity, OllamaExtraction
from pydantic import ValidationError
import pytest

def test_portal_config_validation():
    config = PortalConfig(
        id="1",
        name="Test Portal",
        baseUrl="https://test.com",
        ollamaUrl="http://localhost:11434",
        ollamaModel="gemma"
    )
    assert config.id == "1"
    assert config.name == "Test Portal"
    assert config.base_url == "https://test.com"
    assert config.requests_per_minute == 15
    assert config.ollama_url == "http://localhost:11434"
    assert config.ollama_model == "gemma"

    with pytest.raises(ValidationError):
        PortalConfig(id="1", name="Test Portal") # missing baseUrl

def test_rfp_opportunity_validation():
    opp = RFPOpportunity(id="123", portalId="1", url="https://test.com/rfp/1")
    assert opp.id == "123"
    assert opp.portal_id == "1"
    assert opp.url == "https://test.com/rfp/1"
    assert opp.title == "Untitled Opportunity"

def test_ollama_extraction_validation():
    extract = OllamaExtraction(title="Test", url="https://test.com")
    assert extract.title == "Test"
    assert extract.url == "https://test.com"
