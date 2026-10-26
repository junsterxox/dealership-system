"""SQLite persistence and validation for the dealership manager."""

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator


CAR_STATUSES = ("Available", "Reserved", "Sold")
MAX_CAR_PHOTOS = 20
MAX_CUSTOMER_PHOTOS = 10
CAR_FIELDS = (
    "make",
    "model",
    "year",
    "vin",
    "mileage",
    "price",
    "status",
    "image_path",
    "notes",
)
CUSTOMER_FIELDS = (
    "first_name",
    "last_name",
    "email",
    "phone",
    "address",
    "image_path",
    "notes",
)


class DealershipDatabase:
    def __init__(self, path: str | Path = "dealership.db") -> None:
        self.path = str(path)
        self._initialize()

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS cars (
                    id INTEGER PRIMARY KEY,
                    make TEXT NOT NULL,
                    model TEXT NOT NULL,
                    year INTEGER NOT NULL,
                    vin TEXT NOT NULL DEFAULT '',
                    mileage INTEGER NOT NULL DEFAULT 0,
                    price REAL NOT NULL DEFAULT 0,
                    status TEXT NOT NULL DEFAULT 'Available',
                    image_path TEXT NOT NULL DEFAULT '',
                    notes TEXT NOT NULL DEFAULT ''
                );
                CREATE UNIQUE INDEX IF NOT EXISTS cars_vin_unique
                    ON cars(vin COLLATE NOCASE) WHERE vin <> '';
                CREATE TABLE IF NOT EXISTS customers (
                    id INTEGER PRIMARY KEY,
                    first_name TEXT NOT NULL,
                    last_name TEXT NOT NULL,
                    email TEXT NOT NULL DEFAULT '',
                    phone TEXT NOT NULL DEFAULT '',
                    address TEXT NOT NULL DEFAULT '',
                    image_path TEXT NOT NULL DEFAULT '',
                    notes TEXT NOT NULL DEFAULT ''
                );
                CREATE TABLE IF NOT EXISTS car_photos (
                    id INTEGER PRIMARY KEY,
                    car_id INTEGER NOT NULL REFERENCES cars(id) ON DELETE CASCADE,
                    path TEXT NOT NULL,
                    position INTEGER NOT NULL,
                    UNIQUE (car_id, path)
                );
                CREATE TABLE IF NOT EXISTS customer_photos (
                    id INTEGER PRIMARY KEY,
                    customer_id INTEGER NOT NULL REFERENCES customers(id)
                        ON DELETE CASCADE,
                    path TEXT NOT NULL,
                    position INTEGER NOT NULL,
                    UNIQUE (customer_id, path)
                );
                """
            )
            for table in ("cars", "customers"):
                columns = {
                    row["name"]
                    for row in connection.execute(f"PRAGMA table_info({table})")
                }
                for column in ("image_path", "notes"):
                    if column not in columns:
                        connection.execute(
                            f"ALTER TABLE {table} ADD COLUMN "
                            f"{column} TEXT NOT NULL DEFAULT ''"
                        )
            connection.execute(
                """INSERT OR IGNORE INTO car_photos (car_id, path, position)
                   SELECT id, image_path, 0 FROM cars WHERE image_path <> ''"""
            )
            connection.execute(
                """INSERT OR IGNORE INTO customer_photos (
                       customer_id, path, position
                   ) SELECT id, image_path, 0 FROM customers WHERE image_path <> ''"""
            )

    @staticmethod
    def _photo_paths(values: dict[str, Any], maximum: int) -> list[str]:
        photos = values.get("photos")
        if photos is None:
            photos = [values.get("image_path", "")]
        if isinstance(photos, str):
            photos = [photos]
        if not isinstance(photos, (list, tuple)):
            raise ValueError("Photos must be provided as a list of file paths.")
        paths = list(
            dict.fromkeys(
                str(path).strip() for path in photos if str(path).strip()
            )
        )
        if len(paths) > maximum:
            raise ValueError(f"A profile can have at most {maximum} photos.")
        return paths

    @staticmethod
    def _attach_photo_paths(
        connection: sqlite3.Connection,
        rows: list[sqlite3.Row],
        photo_table: str,
        owner_column: str,
    ) -> list[dict[str, Any]]:
        records = [dict(row) for row in rows]
        if not records:
            return records
        ids = [record["id"] for record in records]
        placeholders = ",".join("?" for _ in ids)
        photos = connection.execute(
            f"""SELECT {owner_column}, path FROM {photo_table}
                WHERE {owner_column} IN ({placeholders}) ORDER BY position, id""",
            ids,
        ).fetchall()
        paths_by_id: dict[int, list[str]] = {}
        for photo in photos:
            paths_by_id.setdefault(photo[owner_column], []).append(photo["path"])
        for record in records:
            paths = paths_by_id.get(record["id"], [])
            record["photos"] = paths
            record["image_path"] = paths[0] if paths else ""
        return records

    @staticmethod
    def _replace_photos(
        connection: sqlite3.Connection,
        photo_table: str,
        owner_column: str,
        owner_id: int,
        paths: list[str],
    ) -> None:
        connection.execute(
            f"DELETE FROM {photo_table} WHERE {owner_column} = ?", (owner_id,)
        )
        connection.executemany(
            f"""INSERT INTO {photo_table} ({owner_column}, path, position)
                VALUES (?, ?, ?)""",
            [(owner_id, path, position) for position, path in enumerate(paths)],
        )

    @staticmethod
    def _clean(values: dict[str, Any], fields: tuple[str, ...]) -> dict[str, str]:
        return {field: str(values.get(field, "")).strip() for field in fields}

    @staticmethod
    def _validate_car(values: dict[str, str]) -> dict[str, Any]:
        if not values["make"] or not values["model"]:
            raise ValueError("Make and model are required.")
        try:
            year = int(values["year"])
            mileage = int(values["mileage"] or "0")
            price = float(values["price"] or "0")
        except ValueError as error:
            raise ValueError("Year, mileage, and price must be valid numbers.") from error
        if not 1886 <= year <= 2100:
            raise ValueError("Enter a valid model year (1886–2100).")
        if mileage < 0 or price < 0:
            raise ValueError("Mileage and price cannot be negative.")
        if values["status"] not in CAR_STATUSES:
            raise ValueError("Choose a valid car status.")
        return {**values, "year": year, "mileage": mileage, "price": price}

    @staticmethod
    def _validate_customer(values: dict[str, str]) -> dict[str, str]:
        if not values["first_name"] or not values["last_name"]:
            raise ValueError("First and last name are required.")
        email = values["email"]
        if email and ("@" not in email or "." not in email.rsplit("@", 1)[-1]):
            raise ValueError("Enter a valid email address.")
        return values

    def list_cars(self, search: str = "") -> list[dict[str, Any]]:
        term = f"%{search.strip()}%"
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM cars
                WHERE make LIKE ? OR model LIKE ? OR CAST(year AS TEXT) LIKE ?
                   OR vin LIKE ? OR status LIKE ? OR notes LIKE ?
                ORDER BY id DESC
                """,
                (term, term, term, term, term, term),
            ).fetchall()
            return self._attach_photo_paths(
                connection, rows, "car_photos", "car_id"
            )

    def save_car(self, values: dict[str, Any], car_id: int | None = None) -> None:
        cleaned = self._validate_car(self._clean(values, CAR_FIELDS))
        photos = self._photo_paths(values, MAX_CAR_PHOTOS)
        cleaned["image_path"] = photos[0] if photos else ""
        with self._connect() as connection:
            if car_id is None:
                result = connection.execute(
                    """INSERT INTO cars (
                           make, model, year, vin, mileage, price, status, image_path, notes
                       ) VALUES (
                           :make, :model, :year, :vin, :mileage, :price, :status,
                           :image_path, :notes
                       )""",
                    cleaned,
                )
                car_id = result.lastrowid
            else:
                result = connection.execute(
                    """UPDATE cars SET make=:make, model=:model, year=:year, vin=:vin,
                       mileage=:mileage, price=:price, status=:status,
                       image_path=:image_path, notes=:notes WHERE id=:id""",
                    {**cleaned, "id": car_id},
                )
                if result.rowcount == 0:
                    raise LookupError("The selected car no longer exists.")
            self._replace_photos(connection, "car_photos", "car_id", car_id, photos)

    def delete_car(self, car_id: int) -> None:
        with self._connect() as connection:
            result = connection.execute("DELETE FROM cars WHERE id = ?", (car_id,))
            if result.rowcount == 0:
                raise LookupError("The selected car no longer exists.")

    def list_customers(self, search: str = "") -> list[dict[str, Any]]:
        term = f"%{search.strip()}%"
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM customers
                WHERE first_name LIKE ? OR last_name LIKE ? OR email LIKE ?
                   OR phone LIKE ? OR address LIKE ? OR notes LIKE ?
                ORDER BY last_name COLLATE NOCASE, first_name COLLATE NOCASE
                """,
                (term, term, term, term, term, term),
            ).fetchall()
            return self._attach_photo_paths(
                connection, rows, "customer_photos", "customer_id"
            )

    def save_customer(
        self, values: dict[str, Any], customer_id: int | None = None
    ) -> None:
        cleaned = self._validate_customer(self._clean(values, CUSTOMER_FIELDS))
        photos = self._photo_paths(values, MAX_CUSTOMER_PHOTOS)
        cleaned["image_path"] = photos[0] if photos else ""
        with self._connect() as connection:
            if customer_id is None:
                result = connection.execute(
                    """INSERT INTO customers (
                           first_name, last_name, email, phone, address, image_path, notes
                       ) VALUES (
                           :first_name, :last_name, :email, :phone, :address,
                           :image_path, :notes
                       )""",
                    cleaned,
                )
                customer_id = result.lastrowid
            else:
                result = connection.execute(
                    """UPDATE customers SET first_name=:first_name, last_name=:last_name,
                       email=:email, phone=:phone, address=:address,
                       image_path=:image_path, notes=:notes WHERE id=:id""",
                    {**cleaned, "id": customer_id},
                )
                if result.rowcount == 0:
                    raise LookupError("The selected customer no longer exists.")
            self._replace_photos(
                connection, "customer_photos", "customer_id", customer_id, photos
            )

    def delete_customer(self, customer_id: int) -> None:
        with self._connect() as connection:
            result = connection.execute(
                "DELETE FROM customers WHERE id = ?", (customer_id,)
            )
            if result.rowcount == 0:
                raise LookupError("The selected customer no longer exists.")
