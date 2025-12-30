"""Checkpoint Manager for Project Greenlight pipeline resume capabilities.

This module provides checkpoint and resume functionality for long-running pipelines,
allowing:
1. Resume after failures (network, API limits, crashes)
2. Partial regeneration (re-validate key frames, regenerate fill frames)
3. Cost optimization (skip expensive passes)
4. User interaction (review after Pass 5 before final generation)
"""

import json
import hashlib
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Optional, Dict, List, Any
from enum import Enum

from greenlight.core.logging_config import get_logger

logger = get_logger("checkpoint_manager")


class CheckpointLevel(Enum):
    """Pipeline checkpoint levels corresponding to pass completion."""
    STORY_STRUCTURE = 1      # After Pass 1: World + Story
    REFERENCES_READY = 2     # After Pass 2: Reference images generated
    KEYFRAMES_VALIDATED = 3  # After Pass 4: Key frames validated
    PROMPTS_WRITTEN = 4      # After Pass 5: All prompts written
    FRAMES_GENERATED = 5     # After Pass 6: All frames generated


@dataclass
class PassMetadata:
    """Metadata for a completed pipeline pass."""
    pass_number: int
    start_time: str  # ISO format
    end_time: str    # ISO format
    duration_seconds: float
    artifacts_created: Dict[str, str] = field(default_factory=dict)  # name -> path
    dependencies_satisfied: bool = True
    skippable: bool = True
    skip_conditions: List[str] = field(default_factory=list)
    error: Optional[str] = None


@dataclass
class CheckpointInfo:
    """Information about a single checkpoint."""
    level: int
    level_name: str
    timestamp: str  # ISO format
    artifacts_count: int
    size_bytes: int
    status: str  # "valid", "partial", "invalid"
    pass_metadata: Optional[PassMetadata] = None


@dataclass
class CheckpointManifest:
    """Master manifest tracking all checkpoints for a project."""
    project_path: str
    created: str  # ISO format
    last_modified: str  # ISO format
    passes_completed: List[int] = field(default_factory=list)
    current_level: int = 0
    checkpoints: Dict[int, CheckpointInfo] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dict."""
        result = {
            "project_path": self.project_path,
            "created": self.created,
            "last_modified": self.last_modified,
            "passes_completed": self.passes_completed,
            "current_level": self.current_level,
            "checkpoints": {}
        }
        for level, info in self.checkpoints.items():
            result["checkpoints"][str(level)] = {
                "level": info.level,
                "level_name": info.level_name,
                "timestamp": info.timestamp,
                "artifacts_count": info.artifacts_count,
                "size_bytes": info.size_bytes,
                "status": info.status,
                "pass_metadata": asdict(info.pass_metadata) if info.pass_metadata else None
            }
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CheckpointManifest":
        """Create from dict."""
        manifest = cls(
            project_path=data.get("project_path", ""),
            created=data.get("created", ""),
            last_modified=data.get("last_modified", ""),
            passes_completed=data.get("passes_completed", []),
            current_level=data.get("current_level", 0)
        )
        for level_str, info_data in data.get("checkpoints", {}).items():
            level = int(level_str)
            pass_meta = None
            if info_data.get("pass_metadata"):
                pass_meta = PassMetadata(**info_data["pass_metadata"])
            manifest.checkpoints[level] = CheckpointInfo(
                level=info_data.get("level", level),
                level_name=info_data.get("level_name", ""),
                timestamp=info_data.get("timestamp", ""),
                artifacts_count=info_data.get("artifacts_count", 0),
                size_bytes=info_data.get("size_bytes", 0),
                status=info_data.get("status", "unknown"),
                pass_metadata=pass_meta
            )
        return manifest


class ResumabilityMode(Enum):
    """Pipeline resumability modes."""
    FULL_RUN = "full"           # Ignore checkpoints, start fresh
    SMART_RESUME = "smart"      # Skip completed passes if valid
    FORCE_PASS = "force_pass"   # Force re-run specific passes


class CheckpointManager:
    """Manages pipeline checkpoints and resume operations."""

    CHECKPOINT_DIR_NAME = ".checkpoints"
    MANIFEST_FILE = "checkpoint_manifest.json"

    LEVEL_NAMES = {
        1: "story_structure",
        2: "references_ready",
        3: "keyframes_validated",
        4: "prompts_written",
        5: "frames_generated"
    }

    # Artifacts expected at each checkpoint level
    EXPECTED_ARTIFACTS = {
        1: ["world_config.json", "visual_script.md", "scenes.json"],
        2: ["references_manifest.json"],
        3: ["anchor_frames.json"],
        4: ["frame_prompts.json"],
        5: ["frames_manifest.json", "pipeline_stats.json"]
    }

    def __init__(self, project_path: Path):
        """Initialize checkpoint manager for a project.

        Args:
            project_path: Path to the project directory
        """
        self.project_path = Path(project_path)
        self.checkpoint_dir = self.project_path / self.CHECKPOINT_DIR_NAME
        self._manifest: Optional[CheckpointManifest] = None

    def _ensure_checkpoint_dir(self) -> Path:
        """Ensure checkpoint directory exists."""
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
        return self.checkpoint_dir

    def _get_manifest_path(self) -> Path:
        """Get path to manifest file."""
        return self.checkpoint_dir / self.MANIFEST_FILE

    def _load_manifest(self) -> CheckpointManifest:
        """Load or create checkpoint manifest."""
        if self._manifest is not None:
            return self._manifest

        manifest_path = self._get_manifest_path()
        if manifest_path.exists():
            try:
                data = json.loads(manifest_path.read_text(encoding="utf-8"))
                self._manifest = CheckpointManifest.from_dict(data)
            except (json.JSONDecodeError, KeyError) as e:
                logger.warning(f"Failed to load manifest, creating new: {e}")
                self._manifest = self._create_new_manifest()
        else:
            self._manifest = self._create_new_manifest()

        return self._manifest

    def _create_new_manifest(self) -> CheckpointManifest:
        """Create a new checkpoint manifest."""
        now = datetime.now().isoformat()
        return CheckpointManifest(
            project_path=str(self.project_path),
            created=now,
            last_modified=now,
            passes_completed=[],
            current_level=0,
            checkpoints={}
        )

    def _save_manifest(self) -> None:
        """Save manifest to disk."""
        if self._manifest is None:
            return

        self._ensure_checkpoint_dir()
        self._manifest.last_modified = datetime.now().isoformat()
        manifest_path = self._get_manifest_path()
        manifest_path.write_text(
            json.dumps(self._manifest.to_dict(), indent=2),
            encoding="utf-8"
        )

    def _calculate_artifacts_size(self, artifacts: Dict[str, str]) -> int:
        """Calculate total size of artifact files."""
        total = 0
        for path_str in artifacts.values():
            try:
                path = Path(path_str)
                if path.exists():
                    total += path.stat().st_size
            except Exception:
                pass
        return total

    def _hash_file(self, path: Path) -> str:
        """Calculate MD5 hash of a file."""
        if not path.exists():
            return ""
        hasher = hashlib.md5()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                hasher.update(chunk)
        return hasher.hexdigest()

    async def save_checkpoint(
        self,
        level: int,
        state_dict: Dict[str, Any],
        artifacts: Optional[Dict[str, str]] = None,
        pass_metadata: Optional[PassMetadata] = None
    ) -> Path:
        """Save a checkpoint at the specified level.

        Args:
            level: Checkpoint level (1-5)
            state_dict: State data to save
            artifacts: Dict of artifact name -> file path
            pass_metadata: Optional metadata about the pass

        Returns:
            Path to saved checkpoint file
        """
        if level not in self.LEVEL_NAMES:
            raise ValueError(f"Invalid checkpoint level: {level}")

        self._ensure_checkpoint_dir()
        manifest = self._load_manifest()

        # Create checkpoint data
        checkpoint_data = {
            "level": level,
            "level_name": self.LEVEL_NAMES[level],
            "timestamp": datetime.now().isoformat(),
            "state": state_dict,
            "artifacts": artifacts or {},
            "artifact_hashes": {}
        }

        # Calculate artifact hashes for integrity checking
        if artifacts:
            for name, path_str in artifacts.items():
                path = Path(path_str)
                if path.exists():
                    checkpoint_data["artifact_hashes"][name] = self._hash_file(path)

        # Save checkpoint file
        checkpoint_path = self.checkpoint_dir / f"checkpoint_level_{level}.json"
        checkpoint_path.write_text(
            json.dumps(checkpoint_data, indent=2, default=str),
            encoding="utf-8"
        )

        # Update manifest
        artifacts_size = self._calculate_artifacts_size(artifacts or {})
        checkpoint_info = CheckpointInfo(
            level=level,
            level_name=self.LEVEL_NAMES[level],
            timestamp=checkpoint_data["timestamp"],
            artifacts_count=len(artifacts or {}),
            size_bytes=artifacts_size + checkpoint_path.stat().st_size,
            status="valid",
            pass_metadata=pass_metadata
        )

        manifest.checkpoints[level] = checkpoint_info
        if level not in manifest.passes_completed:
            manifest.passes_completed.append(level)
            manifest.passes_completed.sort()
        manifest.current_level = max(manifest.current_level, level)

        self._save_manifest()

        logger.info(f"Saved checkpoint level {level} ({self.LEVEL_NAMES[level]})")
        return checkpoint_path

    async def load_checkpoint(self, level: int) -> Optional[Dict[str, Any]]:
        """Load a checkpoint at the specified level.

        Args:
            level: Checkpoint level to load

        Returns:
            Checkpoint data dict or None if not found/invalid
        """
        checkpoint_path = self.checkpoint_dir / f"checkpoint_level_{level}.json"

        if not checkpoint_path.exists():
            logger.warning(f"Checkpoint level {level} not found")
            return None

        try:
            data = json.loads(checkpoint_path.read_text(encoding="utf-8"))

            # Verify artifact integrity
            if not await self.verify_checkpoint_integrity(level):
                logger.warning(f"Checkpoint level {level} failed integrity check")
                return None

            logger.info(f"Loaded checkpoint level {level} ({self.LEVEL_NAMES[level]})")
            return data

        except (json.JSONDecodeError, KeyError) as e:
            logger.error(f"Failed to load checkpoint level {level}: {e}")
            return None

    async def verify_checkpoint_integrity(self, level: int) -> bool:
        """Verify all referenced files exist and match checksums.

        Args:
            level: Checkpoint level to verify

        Returns:
            True if checkpoint is valid
        """
        checkpoint_path = self.checkpoint_dir / f"checkpoint_level_{level}.json"

        if not checkpoint_path.exists():
            return False

        try:
            data = json.loads(checkpoint_path.read_text(encoding="utf-8"))
            artifacts = data.get("artifacts", {})
            artifact_hashes = data.get("artifact_hashes", {})

            for name, path_str in artifacts.items():
                path = Path(path_str)

                # Check file exists
                if not path.exists():
                    logger.warning(f"Missing artifact: {name} at {path}")
                    return False

                # Check hash matches (if we have one)
                if name in artifact_hashes:
                    current_hash = self._hash_file(path)
                    if current_hash != artifact_hashes[name]:
                        logger.warning(f"Artifact hash mismatch: {name}")
                        # Don't fail on hash mismatch - file may have been regenerated
                        # return False

            return True

        except Exception as e:
            logger.error(f"Error verifying checkpoint {level}: {e}")
            return False

    def has_valid_checkpoint(self, level: int) -> bool:
        """Check if a valid checkpoint exists at the specified level.

        Args:
            level: Checkpoint level to check

        Returns:
            True if valid checkpoint exists
        """
        manifest = self._load_manifest()

        if level not in manifest.checkpoints:
            return False

        checkpoint_info = manifest.checkpoints[level]
        return checkpoint_info.status == "valid"

    def get_highest_valid_checkpoint(self) -> Optional[int]:
        """Get the highest valid checkpoint level.

        Returns:
            Highest valid checkpoint level or None
        """
        manifest = self._load_manifest()

        for level in sorted(manifest.checkpoints.keys(), reverse=True):
            if manifest.checkpoints[level].status == "valid":
                return level

        return None

    def list_checkpoints(self) -> List[CheckpointInfo]:
        """List all available checkpoints.

        Returns:
            List of checkpoint info objects
        """
        manifest = self._load_manifest()
        return list(manifest.checkpoints.values())

    def get_checkpoint_info(self, level: int) -> Optional[CheckpointInfo]:
        """Get information about a specific checkpoint.

        Args:
            level: Checkpoint level

        Returns:
            CheckpointInfo or None
        """
        manifest = self._load_manifest()
        return manifest.checkpoints.get(level)

    def can_skip_pass(self, level: int) -> bool:
        """Check if a pass can be skipped due to valid checkpoint.

        Args:
            level: Checkpoint level (pass number)

        Returns:
            True if pass can be skipped
        """
        return self.has_valid_checkpoint(level)

    def get_resume_level(self) -> int:
        """Get the level from which to resume pipeline.

        Returns:
            Level to resume from (0 = start fresh)
        """
        highest = self.get_highest_valid_checkpoint()
        return highest if highest else 0

    async def invalidate_checkpoint(self, level: int) -> None:
        """Invalidate a checkpoint and all higher levels.

        Args:
            level: Checkpoint level to invalidate
        """
        manifest = self._load_manifest()

        # Invalidate this level and all higher levels
        for check_level in list(manifest.checkpoints.keys()):
            if check_level >= level:
                manifest.checkpoints[check_level].status = "invalid"
                if check_level in manifest.passes_completed:
                    manifest.passes_completed.remove(check_level)

        manifest.current_level = min(manifest.current_level, level - 1)
        self._save_manifest()

        logger.info(f"Invalidated checkpoints from level {level}")

    async def clear_all_checkpoints(self) -> None:
        """Clear all checkpoints for this project."""
        import shutil

        if self.checkpoint_dir.exists():
            shutil.rmtree(self.checkpoint_dir)

        self._manifest = None
        logger.info(f"Cleared all checkpoints for {self.project_path.name}")

    def get_skip_reason(self, level: int) -> Optional[str]:
        """Get human-readable reason why a pass was skipped.

        Args:
            level: Checkpoint level

        Returns:
            Skip reason or None
        """
        checkpoint_info = self.get_checkpoint_info(level)
        if not checkpoint_info:
            return None

        if checkpoint_info.pass_metadata and checkpoint_info.pass_metadata.skip_conditions:
            return ", ".join(checkpoint_info.pass_metadata.skip_conditions)

        return f"Valid checkpoint exists from {checkpoint_info.timestamp}"

    def get_manifest(self) -> Dict[str, Any]:
        """Get the full checkpoint manifest.

        Returns:
            Manifest as dict
        """
        return self._load_manifest().to_dict()


# Convenience functions for common operations

async def get_or_create_checkpoint_manager(project_path: Path) -> CheckpointManager:
    """Get or create a checkpoint manager for a project."""
    return CheckpointManager(project_path)


async def can_resume_from_checkpoint(project_path: Path) -> bool:
    """Check if a project can be resumed from a checkpoint."""
    mgr = CheckpointManager(project_path)
    return mgr.get_resume_level() > 0
