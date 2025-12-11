"""NATS client helper for publishing and consuming messages."""

import json
import logging
import os
from typing import Any

import nats
from nats.aio.client import Client as NATS
from nats.js import JetStreamContext
from nats.js.api import RetentionPolicy, StorageType, StreamConfig

logger = logging.getLogger(__name__)


class NATSClient:
    """NATS client wrapper for easy publishing and consuming."""

    def __init__(
        self,
        nats_url: str | None = None,
        stream_name: str | None = None,
    ):
        """
        Initialize NATS client.

        Args:
            nats_url: NATS server URL (defaults to NATS_URL env var)
            stream_name: JetStream name (defaults to STREAM_NAME env var)
        """
        self.nats_url = nats_url or os.getenv("NATS_URL", "nats://localhost:4222")
        self.stream_name = stream_name or os.getenv("STREAM_NAME", "droq-stream")
        self.nc: NATS | None = None
        self.js: JetStreamContext | None = None

    async def connect(self) -> None:
        """Connect to NATS server and initialize JetStream."""
        try:
            logger.info(f"Connecting to NATS at {self.nats_url}")
            self.nc = await nats.connect(self.nats_url)
            self.js = self.nc.jetstream()

            # Ensure stream exists
            await self._ensure_stream()

            logger.info("Connected to NATS and JetStream initialized")
        except Exception as e:
            logger.error(f"Failed to connect to NATS: {e}")
            raise

    async def _ensure_stream(self) -> None:
        """Ensure the JetStream exists, create if it doesn't."""
        try:
            # Try to get stream info
            stream_info = await self.js.stream_info(self.stream_name)
            logger.info(f"Stream '{self.stream_name}' already exists")
            logger.info(f"Stream subjects: {stream_info.config.subjects}")

            # Check if 'droq.local.public.>' is in subjects, if not, update stream
            required_subject = "droq.local.public.>"
            if required_subject not in stream_info.config.subjects:
                logger.warning(f"Stream '{self.stream_name}' missing required subject '{required_subject}', updating...")
                subjects = list(stream_info.config.subjects) + [required_subject]
                await self.js.update_stream(
                    StreamConfig(
                        name=self.stream_name,
                        subjects=subjects,
                        retention=stream_info.config.retention,
                        storage=stream_info.config.storage,
                    )
                )
                logger.info(f"Stream '{self.stream_name}' updated with subject '{required_subject}'")
        except Exception as e:
            # Stream doesn't exist, create it
            logger.info(f"Creating stream '{self.stream_name}' (error: {e})")
            await self.js.add_stream(
                StreamConfig(
                    name=self.stream_name,
                    subjects=[
                        f"{self.stream_name}.>",  # Backward compatibility
                        "droq.local.public.>",    # Full topic path format
                    ],
                    retention=RetentionPolicy.WORK_QUEUE,
                    storage=StorageType.FILE,
                )
            )
            logger.info(f"Stream '{self.stream_name}' created with subjects: ['{self.stream_name}.>', 'droq.local.public.>']")

    async def publish(
        self,
        subject: str,
        data: dict[str, Any],
        headers: dict[str, str] | None = None,
    ) -> None:
        """
        Publish a message to a NATS subject.

        Args:
            subject: NATS subject to publish to (can be full topic path or relative)
            data: Data to publish (will be JSON encoded)
            headers: Optional headers to include
        """
        if not self.js:
            raise RuntimeError("Not connected to NATS. Call connect() first.")

        try:
            # If subject starts with "droq.", use it as full topic path
            # Otherwise, prefix with stream name for backward compatibility
            if subject.startswith("droq."):
                full_subject = subject
            else:
                full_subject = f"{self.stream_name}.{subject}"

            # Encode data as JSON
            payload = json.dumps(data).encode()
            payload_size = len(payload)

            logger.info(f"[NATS] Publishing to subject: {full_subject}, payload size: {payload_size} bytes")

            # Publish with headers if provided
            if headers:
                ack = await self.js.publish(full_subject, payload, headers=headers)
            else:
                ack = await self.js.publish(full_subject, payload)

            logger.info(f"[NATS] ✅ Published message to {full_subject} (seq: {ack.seq if hasattr(ack, 'seq') else 'N/A'})")
        except Exception as e:
            logger.error(f"Failed to publish message: {e}")
            raise

    async def close(self) -> None:
        """Close NATS connection."""
        if self.nc:
            await self.nc.close()
            logger.info("NATS connection closed")

