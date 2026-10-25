"""Prepare public NLP assets during a container build, without calling Gemini."""
import os
from pathlib import Path


def main():
    project = Path(__file__).resolve().parent.parent
    cache = project / '.cache'
    (cache / 'models').mkdir(parents=True, exist_ok=True)
    (cache / 'nltk_data').mkdir(parents=True, exist_ok=True)
    os.environ.setdefault('NLTK_DATA', str(cache / 'nltk_data'))

    # Use the public tokenizer API: newer Unstructured releases install spaCy's
    # English model; older supported releases prepare their NLTK resources.
    from unstructured.nlp.tokenize import pos_tag, sent_tokenize
    assert sent_tokenize('CVBoost prepares document parsing during the build.')
    assert pos_tag('Data analysts use Python and SQL.')

    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2',
        device='cpu', trust_remote_code=False, cache_folder=str(cache / 'models'), token=False)
    vector = model.encode(['Data analysts use Python and SQL.'],
        normalize_embeddings=True, show_progress_bar=False)
    assert vector.shape == (1, 384), 'Unexpected MiniLM embedding dimensions'
    print('Public tokenizer and MiniLM assets are ready. No Gemini request was made.')


if __name__ == '__main__':
    main()
