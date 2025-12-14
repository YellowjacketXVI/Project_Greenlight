"""
Dataset Crafter for LoRA-Compatible Storage

Creates training datasets from:
- User interactions
- Workflow patterns
- UI customizations
- LLM conversations

Supports multiple formats:
- JSONL (recommended for LoRA fine-tuning)
- Alpaca format
- ShareGPT format
- Custom formats
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Any, Optional, Callable
import json


class DatasetFormat(Enum):
    """Supported dataset formats."""
    JSONL = "jsonl"           # Standard JSON Lines
    ALPACA = "alpaca"         # Alpaca instruction format
    SHAREGPT = "sharegpt"     # ShareGPT conversation format
    OPENAI = "openai"         # OpenAI fine-tuning format
    CUSTOM = "custom"         # Custom format with transformer


@dataclass
class DatasetEntry:
    """A single dataset entry."""
    id: str
    instruction: str
    input_text: str
    output_text: str
    system_prompt: str = ""
    category: str = "general"
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    quality_score: float = 1.0
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_jsonl(self) -> Dict[str, Any]:
        """Convert to JSONL format."""
        return {
            "instruction": self.instruction,
            "input": self.input_text,
            "output": self.output_text,
        }
    
    def to_alpaca(self) -> Dict[str, Any]:
        """Convert to Alpaca format."""
        return {
            "instruction": self.instruction,
            "input": self.input_text,
            "output": self.output_text,
            "text": f"### Instruction:\n{self.instruction}\n\n### Input:\n{self.input_text}\n\n### Response:\n{self.output_text}",
        }
    
    def to_sharegpt(self) -> Dict[str, Any]:
        """Convert to ShareGPT format."""
        conversations = []
        if self.system_prompt:
            conversations.append({"from": "system", "value": self.system_prompt})
        conversations.append({"from": "human", "value": f"{self.instruction}\n{self.input_text}"})
        conversations.append({"from": "gpt", "value": self.output_text})
        return {"conversations": conversations}
    
    def to_openai(self) -> Dict[str, Any]:
        """Convert to OpenAI fine-tuning format."""
        messages = []
        if self.system_prompt:
            messages.append({"role": "system", "content": self.system_prompt})
        messages.append({"role": "user", "content": f"{self.instruction}\n{self.input_text}"})
        messages.append({"role": "assistant", "content": self.output_text})
        return {"messages": messages}
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to full dictionary."""
        return {
            "id": self.id,
            "instruction": self.instruction,
            "input_text": self.input_text,
            "output_text": self.output_text,
            "system_prompt": self.system_prompt,
            "category": self.category,
            "tags": self.tags,
            "metadata": self.metadata,
            "quality_score": self.quality_score,
            "timestamp": self.timestamp.isoformat(),
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DatasetEntry":
        return cls(
            id=data["id"],
            instruction=data["instruction"],
            input_text=data.get("input_text", data.get("input", "")),
            output_text=data.get("output_text", data.get("output", "")),
            system_prompt=data.get("system_prompt", ""),
            category=data.get("category", "general"),
            tags=data.get("tags", []),
            metadata=data.get("metadata", {}),
            quality_score=data.get("quality_score", 1.0),
            timestamp=datetime.fromisoformat(data["timestamp"]) if "timestamp" in data else datetime.now(),
        )


@dataclass
class LoRADataset:
    """A complete LoRA training dataset."""
    id: str
    name: str
    description: str
    entries: List[DatasetEntry] = field(default_factory=list)
    format: DatasetFormat = DatasetFormat.JSONL
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "entries": [e.to_dict() for e in self.entries],
            "format": self.format.value,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "metadata": self.metadata,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LoRADataset":
        return cls(
            id=data["id"],
            name=data["name"],
            description=data["description"],
            entries=[DatasetEntry.from_dict(e) for e in data.get("entries", [])],
            format=DatasetFormat(data.get("format", "jsonl")),
            created_at=datetime.fromisoformat(data["created_at"]) if "created_at" in data else datetime.now(),
            updated_at=datetime.fromisoformat(data["updated_at"]) if "updated_at" in data else datetime.now(),
            metadata=data.get("metadata", {}),
        )


class DatasetCrafter:
    """
    Crafts LoRA-compatible training datasets from user interactions.

    Features:
    - Multiple format support (JSONL, Alpaca, ShareGPT, OpenAI)
    - Quality filtering
    - Category-based organization
    - Automatic deduplication
    - Export with train/val split
    """

    def __init__(self, storage_path: Path = None):
        self.storage_path = storage_path
        self._datasets: Dict[str, LoRADataset] = {}
        self._entry_buffer: List[DatasetEntry] = []
        self._custom_transformers: Dict[str, Callable] = {}

        if storage_path:
            self.storage_path.mkdir(parents=True, exist_ok=True)
            self._load_datasets()

    def _load_datasets(self) -> None:
        """Load existing datasets from storage."""
        if not self.storage_path:
            return

        for file in self.storage_path.glob("dataset_*.json"):
            with open(file, "r", encoding="utf-8") as f:
                data = json.load(f)
                dataset = LoRADataset.from_dict(data)
                self._datasets[dataset.id] = dataset

    def _save_dataset(self, dataset: LoRADataset) -> None:
        """Save dataset to storage."""
        if self.storage_path:
            file_path = self.storage_path / f"dataset_{dataset.id}.json"
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(dataset.to_dict(), f, indent=2)

    def create_dataset(self, name: str, description: str, format: DatasetFormat = DatasetFormat.JSONL) -> LoRADataset:
        """Create a new dataset."""
        import hashlib
        dataset_id = hashlib.sha256(f"{name}{datetime.now().isoformat()}".encode()).hexdigest()[:12]

        dataset = LoRADataset(
            id=dataset_id,
            name=name,
            description=description,
            format=format,
        )
        self._datasets[dataset_id] = dataset
        self._save_dataset(dataset)
        return dataset

    def get_dataset(self, dataset_id: str) -> Optional[LoRADataset]:
        """Get a dataset by ID."""
        return self._datasets.get(dataset_id)

    def list_datasets(self) -> List[Dict[str, Any]]:
        """List all datasets."""
        return [
            {"id": d.id, "name": d.name, "entries": len(d.entries), "format": d.format.value}
            for d in self._datasets.values()
        ]

    def add_entry(
        self,
        dataset_id: str,
        instruction: str,
        input_text: str,
        output_text: str,
        system_prompt: str = "",
        category: str = "general",
        tags: List[str] = None,
        quality_score: float = 1.0,
    ) -> Optional[DatasetEntry]:
        """Add an entry to a dataset."""
        dataset = self._datasets.get(dataset_id)
        if not dataset:
            return None

        import hashlib
        entry_id = hashlib.sha256(f"{instruction}{input_text}{output_text}".encode()).hexdigest()[:12]

        # Check for duplicates
        for existing in dataset.entries:
            if existing.id == entry_id:
                return existing  # Already exists

        entry = DatasetEntry(
            id=entry_id,
            instruction=instruction,
            input_text=input_text,
            output_text=output_text,
            system_prompt=system_prompt,
            category=category,
            tags=tags or [],
            quality_score=quality_score,
        )

        dataset.entries.append(entry)
        dataset.updated_at = datetime.now()
        self._save_dataset(dataset)
        return entry

    def add_from_memory(self, dataset_id: str, memory_entries: List[Any]) -> int:
        """Add entries from VectorMemory entries."""
        count = 0
        for mem in memory_entries:
            if hasattr(mem, 'to_training_pair'):
                pair = mem.to_training_pair()
                entry = self.add_entry(
                    dataset_id=dataset_id,
                    instruction=pair.get("instruction", ""),
                    input_text=pair.get("input", ""),
                    output_text=pair.get("output", ""),
                    category=mem.memory_type.value if hasattr(mem, 'memory_type') else "general",
                )
                if entry:
                    count += 1
        return count

    def filter_by_quality(self, dataset_id: str, min_score: float = 0.5) -> List[DatasetEntry]:
        """Filter entries by quality score."""
        dataset = self._datasets.get(dataset_id)
        if not dataset:
            return []
        return [e for e in dataset.entries if e.quality_score >= min_score]

    def filter_by_category(self, dataset_id: str, category: str) -> List[DatasetEntry]:
        """Filter entries by category."""
        dataset = self._datasets.get(dataset_id)
        if not dataset:
            return []
        return [e for e in dataset.entries if e.category == category]

    def export(
        self,
        dataset_id: str,
        output_path: Path,
        format: DatasetFormat = None,
        min_quality: float = 0.0,
        train_split: float = 0.9,
    ) -> Dict[str, int]:
        """
        Export dataset to file(s).

        Args:
            dataset_id: Dataset to export
            output_path: Output file path (without extension)
            format: Override dataset format
            min_quality: Minimum quality score filter
            train_split: Train/validation split ratio

        Returns:
            Dict with counts: {"train": N, "val": M, "total": N+M}
        """
        dataset = self._datasets.get(dataset_id)
        if not dataset:
            return {"train": 0, "val": 0, "total": 0}

        # Filter by quality
        entries = [e for e in dataset.entries if e.quality_score >= min_quality]

        if not entries:
            return {"train": 0, "val": 0, "total": 0}

        # Split train/val
        import random
        random.shuffle(entries)
        split_idx = int(len(entries) * train_split)
        train_entries = entries[:split_idx]
        val_entries = entries[split_idx:]

        # Determine format
        fmt = format or dataset.format

        # Export
        train_path = Path(str(output_path) + "_train.jsonl")
        val_path = Path(str(output_path) + "_val.jsonl")

        self._write_entries(train_entries, train_path, fmt)
        if val_entries:
            self._write_entries(val_entries, val_path, fmt)

        return {
            "train": len(train_entries),
            "val": len(val_entries),
            "total": len(entries),
        }

    def _write_entries(self, entries: List[DatasetEntry], path: Path, fmt: DatasetFormat) -> None:
        """Write entries to file in specified format."""
        with open(path, "w", encoding="utf-8") as f:
            for entry in entries:
                if fmt == DatasetFormat.JSONL:
                    data = entry.to_jsonl()
                elif fmt == DatasetFormat.ALPACA:
                    data = entry.to_alpaca()
                elif fmt == DatasetFormat.SHAREGPT:
                    data = entry.to_sharegpt()
                elif fmt == DatasetFormat.OPENAI:
                    data = entry.to_openai()
                elif fmt == DatasetFormat.CUSTOM and fmt.value in self._custom_transformers:
                    data = self._custom_transformers[fmt.value](entry)
                else:
                    data = entry.to_jsonl()

                f.write(json.dumps(data) + "\n")

    def register_transformer(self, name: str, transformer: Callable[[DatasetEntry], Dict]) -> None:
        """Register a custom format transformer."""
        self._custom_transformers[name] = transformer

    def get_stats(self, dataset_id: str) -> Dict[str, Any]:
        """Get dataset statistics."""
        dataset = self._datasets.get(dataset_id)
        if not dataset:
            return {}

        categories = {}
        total_quality = 0.0

        for entry in dataset.entries:
            categories[entry.category] = categories.get(entry.category, 0) + 1
            total_quality += entry.quality_score

        return {
            "id": dataset.id,
            "name": dataset.name,
            "total_entries": len(dataset.entries),
            "categories": categories,
            "avg_quality": total_quality / len(dataset.entries) if dataset.entries else 0,
            "format": dataset.format.value,
            "created_at": dataset.created_at.isoformat(),
            "updated_at": dataset.updated_at.isoformat(),
        }

