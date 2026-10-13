import json
import logging
import time
from typing import Any

logger = logging.getLogger("cloudforge")
logger.setLevel(logging.INFO)


def log(event: str, **fields: Any) -> None:
    logger.info(json.dumps({"event": event, **fields}, default=str))


def outcome(environment: str, status: str) -> None:
    log("job_outcome", environment=environment, status=status)
    logger.info(
        json.dumps(
            {
                "_aws": {
                    "Timestamp": int(time.time() * 1000),
                    "CloudWatchMetrics": [
                        {
                            "Namespace": "CloudForge",
                            "Dimensions": [["Environment"]],
                            "Metrics": [{"Name": status, "Unit": "Count"}],
                        }
                    ],
                },
                "Environment": environment,
                status: 1,
            }
        )
    )
