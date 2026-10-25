"""Lazy, singleton SBERT encoder. Long documents are token-chunked, not truncated."""
from threading import Lock
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
from config import BASE_DIR
from services.errors import AppError


class SemanticEncoder:
    def __init__(self, model_name: str):
        self.model_name = model_name
        self._model = None
        self._lock = Lock()

    def _document_vector(self, model, text: str) -> np.ndarray:
        # This full token list is only used for splitting, never passed to the model.
        tokens = model.tokenizer.encode(text, add_special_tokens=False,
                                        truncation=False, verbose=False)
        if not tokens:
            raise AppError(422, 'empty_embedding', 'A document has no text to compare.')
        sequence_limit = min(int(model.max_seq_length), 256)
        window = sequence_limit - 2
        if window < 1:
            raise AppError(503, 'embedding_failed', 'The semantic model has an invalid input limit.')
        overlap = min(32, window - 1)
        chunks, weights = [], []
        start, previous_end = 0, 0
        while start < len(tokens):
            end = min(start + window, len(tokens))
            while True:
                chunk = model.tokenizer.decode(tokens[start:end], skip_special_tokens=True)
                # A slice starting within a word can expand when encoded again.
                # Include special tokens so model.encode never silently truncates it.
                encoded = model.tokenizer.encode(chunk, add_special_tokens=True,
                                                  truncation=False, verbose=False)
                excess = len(encoded) - sequence_limit
                if excess <= 0:
                    break
                if end - start <= 1:
                    raise AppError(503, 'embedding_failed', 'A text segment could not fit the semantic model.')
                end = max(start + 1, end - excess)
            if end <= previous_end:
                # Drop overlap if expansion otherwise prevents forward progress.
                start = previous_end
                continue
            chunks.append(chunk)
            # Count each original token once, even when chunk sizes vary.
            weights.append(end - previous_end)
            previous_end = end
            if end == len(tokens):
                break
            start = max(start + 1, end - overlap)
        vectors = model.encode(chunks, batch_size=16, normalize_embeddings=True,
                               convert_to_numpy=True, show_progress_bar=False)
        mean = np.average(vectors, axis=0, weights=weights)
        return mean / max(np.linalg.norm(mean), 1e-12)

    def score(self, resume: str, job: str) -> float:
        with self._lock:
            if self._model is None:
                try:
                    from sentence_transformers import SentenceTransformer
                    self._model = SentenceTransformer(self.model_name, device='cpu', trust_remote_code=False,
                        cache_folder=str(BASE_DIR / '.cache' / 'models'), token=False)
                except Exception:
                    raise AppError(503, 'embedding_unavailable', 'The semantic model could not be loaded. Install requirements.txt and allow the initial model download on the server.') from None
            try:
                vectors = np.stack([self._document_vector(self._model, resume), self._document_vector(self._model, job)])
                similarity = float(cosine_similarity(vectors[:1], vectors[1:])[0, 0])
                return max(0.0, min(1.0, similarity)) * 100
            except AppError:
                raise
            except Exception:
                raise AppError(503, 'embedding_failed', 'The semantic comparison could not be completed. Please try again.') from None

