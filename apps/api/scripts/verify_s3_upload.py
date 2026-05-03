from __future__ import annotations

import argparse
import asyncio

from src.core.config import s3_settings
from src.services.s3_service import S3Service


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Verify production S3 upload access for Chest X-ray Upload persistence."
    )
    parser.add_argument(
        "--bucket",
        default=s3_settings.S3_BUCKET_NAME,
        help="S3 bucket name. Defaults to S3_BUCKET_NAME.",
    )
    parser.add_argument(
        "--region",
        default=s3_settings.AWS_REGION,
        help="AWS region. Defaults to AWS_REGION.",
    )
    return parser.parse_args()


async def main() -> None:
    args = parse_args()
    service = S3Service(
        bucket_name=args.bucket,
        region_name=args.region,
        upload_mode="aws",
    )
    object_key = await service.verify_upload_access()
    print(f"S3 upload verification passed: s3://{args.bucket}/{object_key}")


if __name__ == "__main__":
    asyncio.run(main())
