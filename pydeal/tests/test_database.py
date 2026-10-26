import sqlite3
import tempfile
import unittest
from pathlib import Path

from database import (
    MAX_CAR_PHOTOS,
    MAX_CUSTOMER_PHOTOS,
    DealershipDatabase,
)


class DealershipDatabaseTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database = DealershipDatabase(Path(self.temp_dir.name) / "test.db")

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_car_crud_and_search(self) -> None:
        car = {
            "make": "Toyota",
            "model": "Camry",
            "year": "2022",
            "vin": "ABC123",
            "mileage": "18000",
            "price": "24500",
            "status": "Available",
            "image_path": "C:/photos/camry.jpg",
            "photos": ["C:/photos/camry.jpg", "C:/photos/camry-interior.jpg"],
            "notes": "Fresh tires",
        }
        self.database.save_car(car)
        found = self.database.list_cars("cam")
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]["notes"], "Fresh tires")
        self.assertEqual(found[0]["image_path"], "C:/photos/camry.jpg")
        self.assertEqual(
            found[0]["photos"],
            ["C:/photos/camry.jpg", "C:/photos/camry-interior.jpg"],
        )
        car_id = found[0]["id"]

        car["price"] = "23000"
        self.database.save_car(car, car_id)
        self.assertEqual(self.database.list_cars()[0]["price"], 23000)
        self.assertEqual(self.database.list_cars()[0]["notes"], "Fresh tires")
        self.assertEqual(
            self.database.list_cars()[0]["photos"],
            ["C:/photos/camry.jpg", "C:/photos/camry-interior.jpg"],
        )
        self.assertEqual(
            len(self.database.list_cars("Fresh tires")),
            1,
        )
        self.database.delete_car(car_id)
        self.assertEqual(self.database.list_cars(), [])

    def test_duplicate_vin_is_rejected(self) -> None:
        car = {
            "make": "Honda",
            "model": "Civic",
            "year": "2020",
            "vin": "DUPLICATE",
            "mileage": "1000",
            "price": "15000",
            "status": "Available",
            "image_path": "",
            "notes": "",
        }
        self.database.save_car(car)
        with self.assertRaises(sqlite3.IntegrityError):
            self.database.save_car({**car, "make": "Acura"})

    def test_customer_crud_and_validation(self) -> None:
        customer = {
            "first_name": "Alex",
            "last_name": "Morgan",
            "email": "alex@example.com",
            "phone": "555-0100",
            "address": "12 Main Street",
            "image_path": "C:/photos/alex.png",
            "photos": ["C:/photos/alex.png", "C:/photos/alex-id.jpg"],
            "notes": "Prefers email contact.",
        }
        self.database.save_customer(customer)
        found = self.database.list_customers("example")
        self.assertEqual(found[0]["last_name"], "Morgan")
        self.assertEqual(found[0]["notes"], "Prefers email contact.")
        self.assertEqual(found[0]["image_path"], "C:/photos/alex.png")
        self.assertEqual(
            found[0]["photos"],
            ["C:/photos/alex.png", "C:/photos/alex-id.jpg"],
        )
        customer_id = found[0]["id"]

        customer["phone"] = "555-0199"
        self.database.save_customer(customer, customer_id)
        self.assertEqual(self.database.list_customers()[0]["phone"], "555-0199")
        self.assertEqual(
            len(self.database.list_customers("Prefers email")),
            1,
        )
        self.assertEqual(
            self.database.list_customers()[0]["image_path"],
            "C:/photos/alex.png",
        )
        self.assertEqual(
            self.database.list_customers()[0]["photos"],
            ["C:/photos/alex.png", "C:/photos/alex-id.jpg"],
        )
        self.database.delete_customer(customer_id)
        self.assertEqual(self.database.list_customers(), [])

        with self.assertRaises(ValueError):
            self.database.save_customer({**customer, "email": "not-an-email"})

    def test_invalid_car_details_are_rejected(self) -> None:
        with self.assertRaises(ValueError):
            self.database.save_car(
                {
                    "make": "Toyota",
                    "model": "Camry",
                    "year": "2022",
                    "vin": "",
                    "mileage": "-1",
                    "price": "1000",
                    "status": "Available",
                    "image_path": "",
                    "notes": "",
                }
            )

    def test_existing_database_is_migrated_without_losing_records(self) -> None:
        legacy_path = Path(self.temp_dir.name) / "legacy.db"
        connection = sqlite3.connect(legacy_path)
        try:
            connection.executescript(
                """
                CREATE TABLE cars (
                    id INTEGER PRIMARY KEY, make TEXT NOT NULL, model TEXT NOT NULL,
                    year INTEGER NOT NULL, vin TEXT NOT NULL DEFAULT '',
                    mileage INTEGER NOT NULL DEFAULT 0, price REAL NOT NULL DEFAULT 0,
                    status TEXT NOT NULL DEFAULT 'Available',
                    image_path TEXT NOT NULL DEFAULT ''
                );
                CREATE TABLE customers (
                    id INTEGER PRIMARY KEY, first_name TEXT NOT NULL,
                    last_name TEXT NOT NULL, email TEXT NOT NULL DEFAULT '',
                    phone TEXT NOT NULL DEFAULT '', address TEXT NOT NULL DEFAULT '',
                    image_path TEXT NOT NULL DEFAULT ''
                );
                INSERT INTO cars (make, model, year, image_path)
                    VALUES ('Mazda', '3', 2021, 'C:/photos/mazda.jpg');
                INSERT INTO customers (first_name, last_name, image_path)
                    VALUES ('Sam', 'Lee', 'C:/photos/sam.jpg');
                """
            )
        finally:
            connection.close()

        migrated = DealershipDatabase(legacy_path)
        self.assertEqual(migrated.list_cars()[0]["make"], "Mazda")
        self.assertEqual(
            migrated.list_cars()[0]["photos"], ["C:/photos/mazda.jpg"]
        )
        self.assertEqual(migrated.list_customers()[0]["last_name"], "Lee")
        self.assertEqual(
            migrated.list_customers()[0]["photos"], ["C:/photos/sam.jpg"]
        )

    def test_photo_library_limits_are_enforced(self) -> None:
        car_photos = [f"car-{index}.jpg" for index in range(MAX_CAR_PHOTOS)]
        self.database.save_car(
            {
                "make": "Toyota",
                "model": "Corolla",
                "year": "2021",
                "status": "Available",
                "photos": car_photos,
            }
        )
        self.assertEqual(self.database.list_cars()[0]["photos"], car_photos)

        customer_photos = [
            f"customer-{index}.jpg" for index in range(MAX_CUSTOMER_PHOTOS)
        ]
        self.database.save_customer(
            {
                "first_name": "Taylor",
                "last_name": "Jones",
                "photos": customer_photos,
            }
        )
        self.assertEqual(
            self.database.list_customers()[0]["photos"], customer_photos
        )

        car = {
            "make": "Toyota",
            "model": "Corolla",
            "year": "2021",
            "vin": "",
            "mileage": "0",
            "price": "10000",
            "status": "Available",
            "photos": [f"car-{index}.jpg" for index in range(MAX_CAR_PHOTOS + 1)],
        }
        with self.assertRaisesRegex(ValueError, "at most 20 photos"):
            self.database.save_car(car)

        customer = {
            "first_name": "Taylor",
            "last_name": "Jones",
            "photos": [
                f"customer-{index}.jpg" for index in range(MAX_CUSTOMER_PHOTOS + 1)
            ],
        }
        with self.assertRaisesRegex(ValueError, "at most 10 photos"):
            self.database.save_customer(customer)

    def test_legacy_single_photo_is_supported(self) -> None:
        self.database.save_car(
            {
                "make": "Honda",
                "model": "Accord",
                "year": "2020",
                "status": "Available",
                "image_path": "C:/photos/accord.jpg",
            }
        )
        self.assertEqual(
            self.database.list_cars()[0]["photos"], ["C:/photos/accord.jpg"]
        )


if __name__ == "__main__":
    unittest.main()
