# Dealership Manager

A desktop application for keeping track of dealership inventory and customer
profiles. Records are stored locally in a SQLite database.

## Requirements

- Python 3.10 or newer
- Tkinter (included with most standard Python installations)


## Features

- Add, edit, delete, and search car inventory.
- Track make, model, year, VIN, mileage, price, and availability status.
- Attach up to 20 photos to each car and keep searchable notes.
- Add, edit, delete, and search customer profiles.
- Store customer names and optional email, phone, and address details.
- Attach up to 10 photos to each customer and keep searchable profile notes.
- Double-click a car or customer to open a complete profile with its photo
  library, details, and notes together. Double-click a thumbnail to view the
  photo larger.
- Validate required fields, numeric vehicle details, email format, and unique
  non-empty VINs.

Install the image display dependency with:

```powershell
python -m pip install -r requirements.txt
```

Photo files stay at their selected locations on disk; the database stores the
photo file paths. Existing single-photo profiles are retained when the database
is upgraded.

