"""
Image Engine - Image-to-Vector Translation with SafeTensor Support

Features:
- Image to vector notation translation
- SafeTensor format for model-safe storage
- Image comparison learning analysis
- Procedural UI generation from image vectors
- Reference image collaboration across engines
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
import json
import hashlib
import struct
import base64


class SafeTensorFormat(Enum):
    """Supported SafeTensor formats."""
    FLOAT32 = "float32"
    FLOAT16 = "float16"
    BFLOAT16 = "bfloat16"
    INT8 = "int8"
    UINT8 = "uint8"


class ImageType(Enum):
    """Image classification types."""
    REFERENCE = "reference"
    GENERATED = "generated"
    COMPARISON = "comparison"
    UI_ELEMENT = "ui_element"
    STORYBOARD = "storyboard"
    CHARACTER = "character"
    LOCATION = "location"
    PROP = "prop"


@dataclass
class ImageVector:
    """Vector representation of an image."""
    id: str
    source_path: str
    vector_notation: str
    dimensions: Tuple[int, int]
    channels: int
    image_type: ImageType
    tensor_format: SafeTensorFormat = SafeTensorFormat.FLOAT32
    embedding: List[float] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    checksum: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "source_path": self.source_path,
            "vector_notation": self.vector_notation,
            "dimensions": list(self.dimensions),
            "channels": self.channels,
            "image_type": self.image_type.value,
            "tensor_format": self.tensor_format.value,
            "embedding": self.embedding[:100],  # Truncate for storage
            "tags": self.tags,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
            "checksum": self.checksum,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ImageVector":
        return cls(
            id=data["id"],
            source_path=data["source_path"],
            vector_notation=data["vector_notation"],
            dimensions=tuple(data["dimensions"]),
            channels=data["channels"],
            image_type=ImageType(data["image_type"]),
            tensor_format=SafeTensorFormat(data.get("tensor_format", "float32")),
            embedding=data.get("embedding", []),
            tags=data.get("tags", []),
            metadata=data.get("metadata", {}),
            created_at=datetime.fromisoformat(data["created_at"]) if "created_at" in data else datetime.now(),
            checksum=data.get("checksum", ""),
        )


@dataclass
class ImageComparison:
    """Comparison result between two images."""
    id: str
    source_id: str
    target_id: str
    similarity_score: float
    structural_similarity: float
    color_similarity: float
    feature_matches: int
    delta_vector: List[float] = field(default_factory=list)
    analysis_notes: str = ""
    created_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "source_id": self.source_id,
            "target_id": self.target_id,
            "similarity_score": self.similarity_score,
            "structural_similarity": self.structural_similarity,
            "color_similarity": self.color_similarity,
            "feature_matches": self.feature_matches,
            "delta_vector": self.delta_vector[:50],
            "analysis_notes": self.analysis_notes,
            "created_at": self.created_at.isoformat(),
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ImageComparison":
        return cls(
            id=data["id"],
            source_id=data["source_id"],
            target_id=data["target_id"],
            similarity_score=data["similarity_score"],
            structural_similarity=data["structural_similarity"],
            color_similarity=data["color_similarity"],
            feature_matches=data["feature_matches"],
            delta_vector=data.get("delta_vector", []),
            analysis_notes=data.get("analysis_notes", ""),
            created_at=datetime.fromisoformat(data["created_at"]) if "created_at" in data else datetime.now(),
        )


class ImageEngine:
    """
    Image-to-Vector Translation Engine.

    Features:
    - Load images and convert to vector notation
    - SafeTensor format storage
    - Image comparison with learning analysis
    - Procedural UI element generation
    - Reference image collaboration
    """

    _instance: Optional["ImageEngine"] = None

    def __init__(self, storage_path: Path = None):
        self.storage_path = storage_path
        self._vectors: Dict[str, ImageVector] = {}
        self._comparisons: Dict[str, ImageComparison] = {}
        self._reference_image: Optional[ImageVector] = None

        if storage_path:
            self.storage_path.mkdir(parents=True, exist_ok=True)
            self._vectors_file = storage_path / "image_vectors.json"
            self._tensors_dir = storage_path / "tensors"
            self._tensors_dir.mkdir(exist_ok=True)
            self._load_vectors()
        else:
            self._vectors_file = None
            self._tensors_dir = None

    def _load_vectors(self) -> None:
        """Load vectors from storage."""
        if self._vectors_file and self._vectors_file.exists():
            with open(self._vectors_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                for v in data.get("vectors", []):
                    vec = ImageVector.from_dict(v)
                    self._vectors[vec.id] = vec
                for c in data.get("comparisons", []):
                    comp = ImageComparison.from_dict(c)
                    self._comparisons[comp.id] = comp

    def _save_vectors(self) -> None:
        """Save vectors to storage."""
        if self._vectors_file:
            data = {
                "vectors": [v.to_dict() for v in self._vectors.values()],
                "comparisons": [c.to_dict() for c in self._comparisons.values()],
            }
            with open(self._vectors_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)

    def vectorize_image(
        self,
        image_path: Path,
        image_type: ImageType = ImageType.REFERENCE,
        tags: List[str] = None,
        tensor_format: SafeTensorFormat = SafeTensorFormat.FLOAT32,
    ) -> ImageVector:
        """
        Convert an image to vector notation.

        Args:
            image_path: Path to the image file
            image_type: Classification type
            tags: Optional tags for the image
            tensor_format: SafeTensor format for storage

        Returns:
            ImageVector with notation and embedding
        """
        # Generate ID from path
        path_str = str(image_path)
        vector_id = hashlib.sha256(path_str.encode()).hexdigest()[:12]

        # Read image metadata (without heavy dependencies)
        dimensions, channels = self._get_image_info(image_path)

        # Generate vector notation
        type_prefix = image_type.value.upper()
        tag_str = "_".join(tags[:3]) if tags else "UNNAMED"
        vector_notation = f"@IMG_{type_prefix}_{tag_str}_{vector_id[:6]}"

        # Generate checksum
        checksum = self._compute_checksum(image_path)

        # Create simple embedding (placeholder - real impl would use ML model)
        embedding = self._generate_embedding(image_path, dimensions)

        vector = ImageVector(
            id=vector_id,
            source_path=path_str,
            vector_notation=vector_notation,
            dimensions=dimensions,
            channels=channels,
            image_type=image_type,
            tensor_format=tensor_format,
            embedding=embedding,
            tags=tags or [],
            checksum=checksum,
        )

        self._vectors[vector_id] = vector
        self._save_vectors()

        # Save tensor if storage configured
        if self._tensors_dir:
            self._save_safetensor(vector)

        return vector

    def _get_image_info(self, path: Path) -> Tuple[Tuple[int, int], int]:
        """Get image dimensions and channels without heavy deps."""
        # Try to read PNG/JPEG header
        try:
            with open(path, "rb") as f:
                header = f.read(32)

                # PNG
                if header[:8] == b'\x89PNG\r\n\x1a\n':
                    width = struct.unpack(">I", header[16:20])[0]
                    height = struct.unpack(">I", header[20:24])[0]
                    return (width, height), 4  # Assume RGBA

                # JPEG
                if header[:2] == b'\xff\xd8':
                    f.seek(0)
                    data = f.read()
                    # Find SOF marker
                    idx = data.find(b'\xff\xc0')
                    if idx != -1:
                        height = struct.unpack(">H", data[idx+5:idx+7])[0]
                        width = struct.unpack(">H", data[idx+7:idx+9])[0]
                        return (width, height), 3
        except Exception:
            pass

        return (0, 0), 3  # Default

    def _compute_checksum(self, path: Path) -> str:
        """Compute file checksum."""
        try:
            with open(path, "rb") as f:
                return hashlib.sha256(f.read()).hexdigest()[:16]
        except Exception:
            return ""

    def _generate_embedding(self, path: Path, dims: Tuple[int, int]) -> List[float]:
        """Generate simple embedding (placeholder for ML model)."""
        # Simple hash-based embedding for demo
        try:
            with open(path, "rb") as f:
                data = f.read(4096)  # First 4KB
                embedding = []
                for i in range(0, min(len(data), 512), 4):
                    val = struct.unpack("f", data[i:i+4])[0] if i+4 <= len(data) else 0.0
                    # Normalize to -1 to 1
                    embedding.append(max(-1.0, min(1.0, val / 1e10)))
                return embedding[:128]  # 128-dim embedding
        except Exception:
            return [0.0] * 128

    def _save_safetensor(self, vector: ImageVector) -> Path:
        """Save vector as SafeTensor format."""
        tensor_path = self._tensors_dir / f"{vector.id}.safetensor"

        # SafeTensor header format
        header = {
            "id": vector.id,
            "notation": vector.vector_notation,
            "dims": list(vector.dimensions),
            "format": vector.tensor_format.value,
            "shape": [len(vector.embedding)],
        }

        header_json = json.dumps(header).encode("utf-8")
        header_size = len(header_json)

        with open(tensor_path, "wb") as f:
            # Write header size (8 bytes)
            f.write(struct.pack("<Q", header_size))
            # Write header
            f.write(header_json)
            # Write embedding data
            for val in vector.embedding:
                f.write(struct.pack("<f", val))

        return tensor_path

    def load_safetensor(self, tensor_path: Path) -> Optional[ImageVector]:
        """Load vector from SafeTensor file."""
        try:
            with open(tensor_path, "rb") as f:
                header_size = struct.unpack("<Q", f.read(8))[0]
                header_json = f.read(header_size).decode("utf-8")
                header = json.loads(header_json)

                # Read embedding
                embedding = []
                while True:
                    data = f.read(4)
                    if not data:
                        break
                    embedding.append(struct.unpack("<f", data)[0])

                return ImageVector(
                    id=header["id"],
                    source_path="",
                    vector_notation=header["notation"],
                    dimensions=tuple(header["dims"]),
                    channels=3,
                    image_type=ImageType.REFERENCE,
                    tensor_format=SafeTensorFormat(header["format"]),
                    embedding=embedding,
                )
        except Exception:
            return None

    def compare_images(self, source_id: str, target_id: str) -> Optional[ImageComparison]:
        """Compare two images and generate analysis."""
        source = self._vectors.get(source_id)
        target = self._vectors.get(target_id)

        if not source or not target:
            return None

        # Compute similarities
        similarity = self._compute_similarity(source.embedding, target.embedding)
        structural = self._compute_structural_similarity(source, target)
        color = self._compute_color_similarity(source, target)

        # Compute delta vector
        delta = [t - s for s, t in zip(source.embedding[:50], target.embedding[:50])]

        comp_id = hashlib.sha256(f"{source_id}{target_id}".encode()).hexdigest()[:12]

        comparison = ImageComparison(
            id=comp_id,
            source_id=source_id,
            target_id=target_id,
            similarity_score=similarity,
            structural_similarity=structural,
            color_similarity=color,
            feature_matches=int(similarity * 100),
            delta_vector=delta,
            analysis_notes=f"Compared {source.vector_notation} to {target.vector_notation}",
        )

        self._comparisons[comp_id] = comparison
        self._save_vectors()
        return comparison

    def _compute_similarity(self, emb1: List[float], emb2: List[float]) -> float:
        """Compute cosine similarity between embeddings."""
        if not emb1 or not emb2:
            return 0.0

        min_len = min(len(emb1), len(emb2))
        dot = sum(a * b for a, b in zip(emb1[:min_len], emb2[:min_len]))
        norm1 = sum(a * a for a in emb1[:min_len]) ** 0.5
        norm2 = sum(b * b for b in emb2[:min_len]) ** 0.5

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return max(0.0, min(1.0, dot / (norm1 * norm2)))

    def _compute_structural_similarity(self, v1: ImageVector, v2: ImageVector) -> float:
        """Compute structural similarity based on dimensions."""
        if v1.dimensions == (0, 0) or v2.dimensions == (0, 0):
            return 0.5

        w_ratio = min(v1.dimensions[0], v2.dimensions[0]) / max(v1.dimensions[0], v2.dimensions[0])
        h_ratio = min(v1.dimensions[1], v2.dimensions[1]) / max(v1.dimensions[1], v2.dimensions[1])

        return (w_ratio + h_ratio) / 2

    def _compute_color_similarity(self, v1: ImageVector, v2: ImageVector) -> float:
        """Compute color similarity (placeholder)."""
        # Would use histogram comparison in real implementation
        return self._compute_similarity(v1.embedding[64:], v2.embedding[64:])

    def set_reference_image(self, vector_id: str) -> bool:
        """Set the reference image for cross-engine collaboration."""
        if vector_id in self._vectors:
            self._reference_image = self._vectors[vector_id]
            return True
        return False

    def get_reference_image(self) -> Optional[ImageVector]:
        """Get the current reference image."""
        return self._reference_image

    def get_vector(self, vector_id: str) -> Optional[ImageVector]:
        """Get a vector by ID."""
        return self._vectors.get(vector_id)

    def query_by_notation(self, notation: str) -> List[ImageVector]:
        """Query vectors by notation pattern."""
        results = []
        for vec in self._vectors.values():
            if notation in vec.vector_notation:
                results.append(vec)
        return results

    def query_by_tags(self, tags: List[str], match_all: bool = False) -> List[ImageVector]:
        """Query vectors by tags."""
        results = []
        for vec in self._vectors.values():
            if match_all:
                if all(t in vec.tags for t in tags):
                    results.append(vec)
            else:
                if any(t in vec.tags for t in tags):
                    results.append(vec)
        return results

    def list_vectors(self) -> List[Dict[str, Any]]:
        """List all vectors."""
        return [
            {"id": v.id, "notation": v.vector_notation, "type": v.image_type.value}
            for v in self._vectors.values()
        ]

    def export_for_training(self, output_path: Path) -> int:
        """Export vectors as training data."""
        entries = []
        for vec in self._vectors.values():
            entries.append({
                "instruction": f"Vectorize {vec.image_type.value} image",
                "input": json.dumps({"path": vec.source_path, "tags": vec.tags}),
                "output": vec.vector_notation,
            })

        with open(output_path, "w", encoding="utf-8") as f:
            for entry in entries:
                f.write(json.dumps(entry) + "\n")

        return len(entries)


# Singleton accessor
_image_engine_instance: Optional[ImageEngine] = None


def get_image_engine(storage_path: Path = None) -> ImageEngine:
    """Get or create the ImageEngine singleton."""
    global _image_engine_instance
    if _image_engine_instance is None:
        _image_engine_instance = ImageEngine(storage_path)
    return _image_engine_instance

