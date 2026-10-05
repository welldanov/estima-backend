import argparse
import csv
import logging
import sqlite3
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from pydantic import ValidationError

from ..config import CITIES, DB_PATH
from ..database.connection import apply_schema, create_connection
from ..database.repositories import SaveResult, save_listing, upsert_city
from .models import SkipRecord
from .normalizer import normalize
from .reader import collect_json_files, extract_records, read_json
from .validator import validate_record

logger = logging.getLogger(__name__)


@dataclass
class SkippedRecord:
    file: Path
    record_number: int
    listing_id: int | None
    title: str | None
    reason: str


@dataclass
class SkippedFile:
    file: Path
    reason: str


@dataclass
class ImportResult:
    files: int = 0
    total: int = 0
    saved: Counter[SaveResult] = field(
        default_factory=Counter
    )
    skipped: list[SkippedRecord] = field(
        default_factory=list
    )
    skipped_files: list[SkippedFile] = field(
        default_factory=list
    )
    backup_path: Path | None = None

    def skip_reasons(self) -> Counter[str]:
        return Counter(
            record.reason
            for record in self.skipped
        )


def describe_validation_error(
        exc: ValidationError,
) -> str:
    fields = sorted({
        str(error["loc"][0])
        for error in exc.errors()
        if error["loc"]
    })

    return f"Invalid record: {', '.join(fields)}"


def import_file(
        conn: sqlite3.Connection,
        json_path: Path,
        result: ImportResult,
) -> None:
    try:
        records = extract_records(read_json(json_path))

    except ValueError as exc:
        # битый файл парсера не должен останавливать весь импорт
        result.skipped_files.append(
            SkippedFile(
                file=json_path,
                reason=str(exc),
            )
        )

        logger.warning(
            "Skipped file %s: %s",
            json_path,
            exc,
        )
        return

    result.files += 1
    result.total += len(records)

    if not records:
        logger.info(
            "No listing records, skipped file: %s",
            json_path,
        )
        return

    conn.execute("BEGIN")

    try:
        for index, raw_record in enumerate(records, start=1):
            conn.execute("SAVEPOINT record")

            try:
                listing = normalize(validate_record(raw_record))
                status = save_listing(conn, listing)

            except (SkipRecord, ValidationError) as exc:
                conn.execute("ROLLBACK TO SAVEPOINT record")

                reason = (
                    describe_validation_error(exc)
                    if isinstance(exc, ValidationError)
                    else str(exc)
                )

                result.skipped.append(
                    SkippedRecord(
                        file=json_path,
                        record_number=index,
                        listing_id=raw_record.get("id"),
                        title=raw_record.get("title"),
                        reason=reason,
                    )
                )

                logger.debug(
                    "Skipped id=%s (%s): %s",
                    raw_record.get("id"),
                    reason,
                    raw_record.get("title"),
                )

            else:
                result.saved[status] += 1

            conn.execute("RELEASE SAVEPOINT record")

        conn.commit()

    except Exception:
        conn.rollback()
        raise

    logger.debug(
        "Imported %s: %d records",
        json_path,
        len(records),
    )


def backup_database(
        db_path: Path,
) -> Path:
    # старую БД не удаляем, а откладываем рядом: удаляет её пользователь
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")

    backup_path = db_path.with_name(
        f"{db_path.stem}.backup-{timestamp}{db_path.suffix}"
    )

    db_path.rename(backup_path)

    logger.info(
        "Old database moved to: %s",
        backup_path,
    )

    return backup_path


def import_path(
        input_path: Path,
        db_path: Path,
        rebuild: bool = False,
) -> ImportResult:
    files = collect_json_files(input_path)

    result = ImportResult()

    if rebuild and db_path.exists():
        result.backup_path = backup_database(db_path)

    db_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    conn = create_connection(db_path)

    try:
        apply_schema(conn)

        for city in CITIES.values():
            upsert_city(conn, city)

        conn.commit()

        for number, json_file in enumerate(files, start=1):
            import_file(conn, json_file, result)

            if number % 100 == 0:
                logger.info(
                    "Processed files: %d/%d",
                    number,
                    len(files),
                )

    finally:
        conn.close()

    return result


def write_report(
        result: ImportResult,
        report_path: Path,
) -> None:
    with report_path.open(
            "w",
            encoding="utf-8",
            newline="",
    ) as file:
        writer = csv.writer(file)
        writer.writerow(
            ["file", "record_number", "listing_id", "reason", "title"]
        )

        for skipped_file in result.skipped_files:
            writer.writerow([
                skipped_file.file.as_posix(),
                None,
                None,
                skipped_file.reason,
                None,
            ])

        for record in result.skipped:
            writer.writerow([
                record.file.as_posix(),
                record.record_number,
                record.listing_id,
                record.reason,
                record.title,
            ])


def print_result(
        result: ImportResult,
) -> None:
    print()
    print("Import finished.")
    print(f"Files:    {result.files}")
    print(f"Records:  {result.total}")
    print(f"Inserted: {result.saved[SaveResult.INSERTED]}")
    print(f"Updated:  {result.saved[SaveResult.UPDATED]}")
    print(f"Stale:    {result.saved[SaveResult.STALE]}")
    print(f"Skipped:  {len(result.skipped)}")

    if result.backup_path is not None:
        print()
        print(f"Old database moved to: {result.backup_path}")

    if result.skipped_files:
        print()
        print(f"Skipped files: {len(result.skipped_files)}")

        for skipped_file in result.skipped_files:
            print(f"  {skipped_file.file}: {skipped_file.reason}")

    reasons = result.skip_reasons()

    if reasons:
        print()
        print("Skip reasons:")

        for reason, count in reasons.most_common():
            print(f"  {count:6}  {reason}")


def configure_logging(
        verbose: bool,
) -> None:
    logging.basicConfig(
        level=(
            logging.DEBUG
            if verbose
            else logging.INFO
        ),
        format=(
            "%(asctime)s | "
            "%(levelname)s | "
            "%(message)s"
        ),
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Import Avito JSON data into SQLite.",
    )

    parser.add_argument(
        "input",
        type=Path,
        help="JSON file or directory (searched recursively)",
    )

    parser.add_argument(
        "--db",
        type=Path,
        default=DB_PATH,
        help="SQLite database path",
    )

    parser.add_argument(
        "--rebuild",
        action="store_true",
        help="Delete the database and import from scratch",
    )

    parser.add_argument(
        "--report",
        type=Path,
        help="Write skipped records to CSV",
    )

    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable debug logging",
    )

    args = parser.parse_args()

    configure_logging(args.verbose)

    result = import_path(
        input_path=args.input,
        db_path=args.db,
        rebuild=args.rebuild,
    )

    print_result(result)

    if args.report is not None:
        write_report(result, args.report)
        print(f"\nSkipped records saved to: {args.report}")


if __name__ == "__main__":
    main()
