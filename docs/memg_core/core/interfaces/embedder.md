# `memg_core/core/interfaces/embedder.py`

## Module Description
This module provides an interface for generating text embeddings using `FastEmbed`. It's designed for local execution, eliminating the need for external API keys for embedding generation. It supports embedding single texts or lists of texts.

## Internal Dependencies
- None

## External Dependencies
- `os`: For interacting with environment variables.
- `fastembed`: `TextEmbedding` for generating embeddings.

## Classes

### `Embedder`
- **Description**: A wrapper class around the `FastEmbed` library, providing methods to generate vector embeddings for text. It allows for specification of a model name, defaulting to an environment variable or a predefined model.
- **Attributes**:
  - `model_name`: `str` - The name of the FastEmbed model being used. Defaults to `EMBEDDER_MODEL` environment variable or `Snowflake/snowflake-arctic-embed-xs`.
  - `model`: `fastembed.TextEmbedding` - An instance of the `TextEmbedding` class from `fastembed`.
- **Methods**:
  - `__init__`:
    - **Description**: Initializes the `Embedder` with an optional model name. It prioritizes the `EMBEDDER_MODEL` environment variable, then a default model.
    - **Inputs**:
      - `model_name`: `str | None` = None - The specific model name to use for embeddings.
    - **Returns**: None
    - **Schema**:
      - Input: `model_name` (String or None)
      - Output: None
      - Type Mixing: Defined type

  - `get_embedding`:
    - **Description**: Generates a single embedding vector for a given text string.
    - **Inputs**:
      - `text`: `str` - The input text to be embedded.
    - **Returns**: `list[float]` - A list of floats representing the embedding vector.
    - **Raises**: `RuntimeError` - If FastEmbed returns an empty embedding.
    - **Schema**:
      - Input: `text` (String)
      - Output: `list[float]` (List of Floats)
      - Type Mixing: Defined type

  - `get_embeddings`:
    - **Description**: Generates embedding vectors for a list of text strings.
    - **Inputs**:
      - `texts`: `list[str]` - A list of input texts to be embedded.
    - **Returns**: `list[list[float]]` - A list of lists of floats, where each inner list is an embedding vector for the corresponding input text.
    - **Schema**:
      - Input: `texts` (List of Strings)
      - Output: `list[list[float]]` (List of Lists of Floats)
      - Type Mixing: Defined type
