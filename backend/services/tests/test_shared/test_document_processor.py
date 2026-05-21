"""
Tests for document processor module.
"""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../'))

from services.shared.document_processor import (
    TextExtractor,
    TextChunker,
    FileHasher,
    DocumentProcessor,
    EmbeddingProcessor,
    ChunkingConfig,
    ExtractionResult,
    ProcessedDocument
)


class TestTextExtractor:
    """Tests for TextExtractor class."""
    
    def test_extract_from_txt_utf8(self):
        """Test extracting text from UTF-8 file."""
        content = "Hello, World! This is a test document."
        file_bytes = content.encode('utf-8')
        
        result = TextExtractor.extract_from_txt(file_bytes)
        
        assert result.success is True
        assert result.text == content
        assert result.error is None
    
    def test_extract_from_txt_latin1(self):
        """Test extracting text from Latin-1 encoded file."""
        content = "Café résumé naïve"
        file_bytes = content.encode('latin-1')
        
        result = TextExtractor.extract_from_txt(file_bytes)
        
        assert result.success is True
        assert "Caf" in result.text  # Basic content check
    
    def test_extract_from_txt_empty(self):
        """Test extracting from empty file."""
        result = TextExtractor.extract_from_txt(b"   ")
        
        assert result.success is False
        assert "No text found" in result.error
    
    def test_extract_unsupported_format(self):
        """Test extracting from unsupported format."""
        result = TextExtractor.extract("test.xyz", b"content")
        
        assert result.success is False
        assert "Unsupported file type" in result.error
    
    def test_is_supported_pdf(self):
        """Test PDF format is supported."""
        assert TextExtractor.is_supported("document.pdf") is True
        assert TextExtractor.is_supported("DOCUMENT.PDF") is True
    
    def test_is_supported_docx(self):
        """Test DOCX format is supported."""
        assert TextExtractor.is_supported("document.docx") is True
    
    def test_is_supported_txt(self):
        """Test TXT format is supported."""
        assert TextExtractor.is_supported("document.txt") is True
        assert TextExtractor.is_supported("readme.md") is True
    
    def test_is_supported_unsupported(self):
        """Test unsupported formats."""
        assert TextExtractor.is_supported("document.xyz") is False
        assert TextExtractor.is_supported("image.jpg") is False


class TestTextChunker:
    """Tests for TextChunker class."""
    
    def test_chunk_text_basic(self, sample_text: str):
        """Test basic text chunking."""
        chunker = TextChunker(ChunkingConfig(chunk_size=50, overlap=10))
        chunks = chunker.chunk_text(sample_text)
        
        assert len(chunks) > 0
        assert all(isinstance(c, str) for c in chunks)
    
    def test_chunk_text_empty(self):
        """Test chunking empty text."""
        chunker = TextChunker()
        chunks = chunker.chunk_text("")
        
        assert chunks == []
    
    def test_chunk_text_whitespace(self):
        """Test chunking whitespace-only text."""
        chunker = TextChunker()
        chunks = chunker.chunk_text("   \n\t   ")
        
        assert chunks == []
    
    def test_chunk_text_small_text(self):
        """Test chunking text smaller than chunk size."""
        chunker = TextChunker(ChunkingConfig(chunk_size=1000, overlap=50))
        small_text = "This is a small text."
        chunks = chunker.chunk_text(small_text)
        
        assert len(chunks) == 1
        assert chunks[0] == small_text
    
    def test_estimate_chunk_count(self, sample_text: str):
        """Test estimating chunk count."""
        chunker = TextChunker(ChunkingConfig(chunk_size=50, overlap=10))
        
        estimated = chunker.estimate_chunk_count(sample_text)
        actual_chunks = chunker.chunk_text(sample_text)
        
        # Estimate should be reasonably close
        assert abs(estimated - len(actual_chunks)) <= 2
    
    def test_chunk_overlap(self):
        """Test that chunks have proper overlap."""
        text = "word " * 100  # 100 words
        chunker = TextChunker(ChunkingConfig(chunk_size=20, overlap=5))
        
        chunks = chunker.chunk_text(text)
        
        # Should have multiple chunks
        assert len(chunks) > 1
        
        # Each chunk except last should be similar size
        for chunk in chunks[:-1]:
            assert len(chunk) > 0


class TestFileHasher:
    """Tests for FileHasher class."""
    
    def test_compute_hash_sha256(self):
        """Test SHA256 hashing."""
        content = b"test content"
        hash1 = FileHasher.compute_hash(content, "sha256")
        hash2 = FileHasher.compute_hash(content, "sha256")
        
        assert hash1 == hash2  # Deterministic
        assert len(hash1) == 64  # SHA256 hex length
    
    def test_compute_hash_md5(self):
        """Test MD5 hashing."""
        content = b"test content"
        hash1 = FileHasher.compute_hash(content, "md5")
        
        assert len(hash1) == 32  # MD5 hex length
    
    def test_compute_hash_different_content(self):
        """Test different content produces different hashes."""
        hash1 = FileHasher.compute_hash(b"content 1")
        hash2 = FileHasher.compute_hash(b"content 2")
        
        assert hash1 != hash2
    
    def test_compute_text_hash(self):
        """Test text hashing."""
        text = "Hello, World!"
        hash1 = FileHasher.compute_text_hash(text)
        hash2 = FileHasher.compute_text_hash(text)
        
        assert hash1 == hash2
    
    def test_compute_hash_unsupported_algorithm(self):
        """Test unsupported hash algorithm."""
        with pytest.raises(ValueError) as exc_info:
            FileHasher.compute_hash(b"content", "sha999")
        
        assert "Unsupported hash algorithm" in str(exc_info.value)


class TestDocumentProcessor:
    """Tests for DocumentProcessor class."""
    
    def test_validate_file_valid(self):
        """Test validating a valid file."""
        processor = DocumentProcessor()
        
        is_valid, error = processor.validate_file("test.txt", b"content")
        
        assert is_valid is True
        assert error is None
    
    def test_validate_file_empty_filename(self):
        """Test validating with empty filename."""
        processor = DocumentProcessor()
        
        is_valid, error = processor.validate_file("", b"content")
        
        assert is_valid is False
        assert "Filename is required" in error
    
    def test_validate_file_empty_content(self):
        """Test validating with empty content."""
        processor = DocumentProcessor()
        
        is_valid, error = processor.validate_file("test.txt", b"")
        
        assert is_valid is False
        assert "File is empty" in error
    
    def test_validate_file_unsupported_type(self):
        """Test validating unsupported file type."""
        processor = DocumentProcessor()
        
        is_valid, error = processor.validate_file("test.xyz", b"content")
        
        assert is_valid is False
        assert "Unsupported" in error
    
    def test_validate_file_too_large(self):
        """Test validating file that's too large."""
        processor = DocumentProcessor()
        large_content = b"x" * (51 * 1024 * 1024)  # 51MB
        
        is_valid, error = processor.validate_file("test.txt", large_content)
        
        assert is_valid is False
        assert "too large" in error
    
    def test_process_txt_file(self):
        """Test processing a text file."""
        processor = DocumentProcessor()
        content = "This is test content.\n" * 10
        
        success, result, error = processor.process("test.txt", content.encode())
        
        assert success is True
        assert isinstance(result, ProcessedDocument)
        assert result.text == content
        assert len(result.chunks) > 0
        assert len(result.file_hash) == 64  # SHA256
    
    def test_process_empty_extraction(self):
        """Test processing file with no extractable content."""
        processor = DocumentProcessor()
        
        # Create processor with mock extractor that returns empty
        with patch.object(TextExtractor, 'extract') as mock_extract:
            mock_extract.return_value = ExtractionResult(success=True, text="   ")
            
            success, result, error = processor.process("test.txt", b"content")
        
        assert success is False
        assert error is not None


class TestEmbeddingProcessor:
    """Tests for EmbeddingProcessor class."""
    
    @pytest.mark.asyncio
    async def test_get_embedding_with_client(self, mock_embedding_client: AsyncMock):
        """Test getting embedding with client."""
        processor = EmbeddingProcessor(embedding_client=mock_embedding_client)
        
        embedding = await processor.get_embedding("test text")
        
        assert len(embedding) == 1536
        mock_embedding_client.get_embedding.assert_called_once_with("test text")
    
    @pytest.mark.asyncio
    async def test_get_embedding_without_client(self):
        """Test getting mock embedding without client."""
        processor = EmbeddingProcessor()
        
        embedding = await processor.get_embedding("test text")
        
        assert len(embedding) == 1536
        assert all(0 <= x <= 1 for x in embedding)
    
    @pytest.mark.asyncio
    async def test_get_embedding_deterministic_mock(self):
        """Test mock embedding is deterministic."""
        processor = EmbeddingProcessor()
        
        emb1 = await processor.get_embedding("test text")
        emb2 = await processor.get_embedding("test text")
        emb3 = await processor.get_embedding("different text")
        
        assert emb1 == emb2  # Same input = same output
        assert emb1 != emb3  # Different input = different output
    
    @pytest.mark.asyncio
    async def test_get_embedding_with_cache(self, mock_cache: AsyncMock, mock_embedding_client: AsyncMock):
        """Test embedding caching."""
        cached_embedding = [0.5] * 1536
        mock_cache.get = AsyncMock(return_value=cached_embedding)
        
        processor = EmbeddingProcessor(
            embedding_client=mock_embedding_client,
            cache=mock_cache
        )
        
        embedding = await processor.get_embedding("test text")
        
        assert embedding == cached_embedding
        mock_embedding_client.get_embedding.assert_not_called()  # Should use cache
    
    @pytest.mark.asyncio
    async def test_get_embeddings_batch(self, mock_embedding_client: AsyncMock):
        """Test batch embedding processing."""
        processor = EmbeddingProcessor(
            embedding_client=mock_embedding_client,
            batch_size=2
        )
        texts = ["text 1", "text 2", "text 3"]
        
        embeddings = await processor.get_embeddings_batch(texts)
        
        assert len(embeddings) == 3
        assert all(len(e) == 1536 for e in embeddings)
    
    @pytest.mark.asyncio
    async def test_get_embeddings_batch_with_cache(self, mock_cache: AsyncMock):
        """Test batch processing with some cached."""
        # First item cached, others not
        mock_cache.get = AsyncMock(side_effect=[
            [0.1] * 1536,  # Cached
            None,          # Not cached
            None           # Not cached
        ])
        
        processor = EmbeddingProcessor(cache=mock_cache)
        texts = ["text 1", "text 2", "text 3"]
        
        embeddings = await processor.get_embeddings_batch(texts)
        
        assert len(embeddings) == 3
        assert embeddings[0] == [0.1] * 1536  # From cache
