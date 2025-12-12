#!/usr/bin/env python3
"""Generate thumbnails for existing screenshots.

This migration script creates thumbnail versions of all existing screenshots
that don't already have thumbnails. Useful for backfilling after adding
the thumbnail feature.

Usage:
    python scripts/generate_thumbnails.py [--dry-run] [--force]

Options:
    --dry-run   Show what would be done without actually creating files
    --force     Regenerate thumbnails even if they already exist
"""

import argparse
import sys
from pathlib import Path
from PIL import Image
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

DATA_DIR = Path.home() / "activity-tracker-data"
SCREENSHOTS_DIR = DATA_DIR / "screenshots"
THUMBNAILS_DIR = DATA_DIR / "thumbnails"

THUMB_WIDTH = 200
THUMB_QUALITY = 75


def generate_thumbnail(screenshot_path: Path, thumbnail_path: Path, dry_run: bool = False) -> bool:
    """Generate a thumbnail for a single screenshot.

    Args:
        screenshot_path: Path to the original screenshot
        thumbnail_path: Path where thumbnail should be saved
        dry_run: If True, don't actually create the file

    Returns:
        True if thumbnail was created (or would be created in dry-run), False otherwise
    """
    if dry_run:
        logger.info(f"[DRY-RUN] Would create: {thumbnail_path}")
        return True

    try:
        # Open the original image
        with Image.open(screenshot_path) as img:
            # Calculate thumbnail size maintaining aspect ratio
            aspect_ratio = img.height / img.width
            thumb_height = int(THUMB_WIDTH * aspect_ratio)

            # Resize using high-quality resampling
            thumbnail = img.resize((THUMB_WIDTH, thumb_height), Image.Resampling.LANCZOS)

            # Ensure directory exists
            thumbnail_path.parent.mkdir(parents=True, exist_ok=True)

            # Save as WebP
            thumbnail.save(thumbnail_path, "WEBP", quality=THUMB_QUALITY, method=4)

        logger.debug(f"Created: {thumbnail_path}")
        return True

    except Exception as e:
        logger.error(f"Failed to create thumbnail for {screenshot_path}: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Generate thumbnails for existing screenshots")
    parser.add_argument('--dry-run', action='store_true', help="Show what would be done without creating files")
    parser.add_argument('--force', action='store_true', help="Regenerate thumbnails even if they exist")
    args = parser.parse_args()

    if not SCREENSHOTS_DIR.exists():
        logger.error(f"Screenshots directory not found: {SCREENSHOTS_DIR}")
        sys.exit(1)

    # Find all screenshot files
    screenshots = list(SCREENSHOTS_DIR.rglob("*.webp"))

    # Filter out crop files
    screenshots = [s for s in screenshots if not s.name.endswith("_crop.webp")]

    if not screenshots:
        logger.info("No screenshots found to process")
        return

    logger.info(f"Found {len(screenshots)} screenshots to process")

    created = 0
    skipped = 0
    failed = 0

    for screenshot_path in screenshots:
        # Calculate relative path and thumbnail path
        relative_path = screenshot_path.relative_to(SCREENSHOTS_DIR)
        thumbnail_path = THUMBNAILS_DIR / relative_path

        # Skip if thumbnail exists (unless --force)
        if thumbnail_path.exists() and not args.force:
            skipped += 1
            continue

        if generate_thumbnail(screenshot_path, thumbnail_path, dry_run=args.dry_run):
            created += 1
        else:
            failed += 1

        # Progress update every 100 images
        if (created + skipped + failed) % 100 == 0:
            logger.info(f"Progress: {created + skipped + failed}/{len(screenshots)} processed")

    # Final summary
    logger.info("=" * 50)
    logger.info(f"Completed: {created} created, {skipped} skipped, {failed} failed")

    if args.dry_run:
        logger.info("[DRY-RUN] No files were actually created")


if __name__ == "__main__":
    main()
