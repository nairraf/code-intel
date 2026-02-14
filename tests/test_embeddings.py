import pytest
import httpx
from src.embeddings import OllamaClient
from src.config import EMBEDDING_DIMENSIONS

@pytest.mark.asyncio
async def test_successful_embedding_mock(mocker):
    client = OllamaClient()
    mock_response = mocker.Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"embedding": [0.1] * EMBEDDING_DIMENSIONS}
    mock_response.raise_for_status = mocker.Mock()
    
    # Mock httpx.AsyncClient.post
    mock_post = mocker.patch("httpx.AsyncClient.post", return_value=mock_response)
    
    vec = await client.get_embedding("hello world")
    assert len(vec) == EMBEDDING_DIMENSIONS
    assert vec[0] == 0.1
    mock_post.assert_called_once()

@pytest.mark.asyncio
async def test_embedding_retry_logic(mocker):
    client = OllamaClient()
    
    # First call fails, second succeeds
    fail_response = mocker.Mock()
    fail_response.raise_for_status.side_effect = httpx.HTTPError("Service Unavailable")
    
    success_response = mocker.Mock()
    success_response.status_code = 200
    success_response.json.return_value = {"embedding": [0.5] * EMBEDDING_DIMENSIONS}
    success_response.raise_for_status = mocker.Mock()
    
    mock_post = mocker.patch("httpx.AsyncClient.post", side_effect=[fail_response, success_response])
    
    # Mock asyncio.sleep to speed up tests
    mocker.patch("asyncio.sleep", return_value=None)
    
    vec = await client.get_embedding("test retry")
    assert vec[0] == 0.5
    assert mock_post.call_count == 2

@pytest.mark.asyncio
async def test_embedding_dimension_mismatch(mocker, caplog):
    client = OllamaClient()
    mock_response = mocker.Mock()
    mock_response.status_code = 200
    # Wrong dimensions
    mock_response.json.return_value = {"embedding": [1.0, 2.0]}
    mock_response.raise_for_status = mocker.Mock()
    
    mocker.patch("httpx.AsyncClient.post", return_value=mock_response)
    
    # Should still return but log a warning
    vec = await client.get_embedding("mismatch")
    assert len(vec) == 2
    assert "Embedding dimension mismatch" in caplog.text
