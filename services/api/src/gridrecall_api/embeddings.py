import hashlib
import json
import math
import re
from collections.abc import Sequence
from typing import Any, Protocol


class EmbeddingProvider(Protocol):
    def embed(self, text: str) -> list[float]: ...


class LocalHashEmbeddingProvider:
    """Stable local embeddings for tests and credential-free demonstrations.

    Production uses Amazon Titan Text Embeddings through an adapter with the same
    interface. This implementation deliberately avoids pretending to be a model.
    """

    def __init__(self, dimensions: int = 64) -> None:
        self.dimensions = dimensions

    def embed(self, text: str) -> list[float]:
        vector = [0.0] * self.dimensions
        tokens = re.findall(r"[a-z0-9]+", text.lower())
        for token in tokens:
            digest = hashlib.sha256(token.encode()).digest()
            index = int.from_bytes(digest[:4], "big") % self.dimensions
            direction = 1.0 if digest[4] % 2 == 0 else -1.0
            vector[index] += direction
        magnitude = math.sqrt(sum(value * value for value in vector))
        return vector if magnitude == 0 else [value / magnitude for value in vector]


class BedrockTitanEmbeddingProvider:
    """Amazon Titan Text Embeddings V2 adapter.

    A client can be injected in tests. In production, boto3 resolves credentials from
    the Lambda execution role, so the application never needs an AWS access key.
    """

    def __init__(
        self,
        region: str,
        model_id: str = "amazon.titan-embed-text-v2:0",
        dimensions: int = 1024,
        client: Any | None = None,
    ) -> None:
        if dimensions not in {256, 512, 1024}:
            raise ValueError("Titan Text Embeddings V2 supports 256, 512, or 1024 dimensions")
        if client is None:
            import boto3

            client = boto3.client("bedrock-runtime", region_name=region)
        self._client = client
        self.model_id = model_id
        self.dimensions = dimensions

    def embed(self, text: str) -> list[float]:
        if not text.strip():
            raise ValueError("Embedding input cannot be empty")
        response = self._client.invoke_model(
            modelId=self.model_id,
            contentType="application/json",
            accept="application/json",
            body=json.dumps(
                {
                    "inputText": text,
                    "dimensions": self.dimensions,
                    "normalize": True,
                }
            ),
        )
        payload = json.loads(response["body"].read())
        embedding = payload.get("embedding")
        if not isinstance(embedding, list) or len(embedding) != self.dimensions:
            raise RuntimeError(
                f"Bedrock returned an invalid embedding; expected {self.dimensions} values"
            )
        return [float(value) for value in embedding]


def cosine_similarity(left: Sequence[float], right: Sequence[float]) -> float:
    if len(left) != len(right) or not left:
        return 0.0
    dot = sum(a * b for a, b in zip(left, right, strict=True))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return max(-1.0, min(1.0, dot / (left_norm * right_norm)))
