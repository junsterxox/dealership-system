"""Desktop interface for managing dealership inventory and customer profiles."""

import sqlite3
import os
from pathlib import Path
import sys
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import Any, Callable

from database import (
    CAR_STATUSES,
    MAX_CAR_PHOTOS,
    MAX_CUSTOMER_PHOTOS,
    DealershipDatabase,
)


def _database_path() -> str | Path:
    if not getattr(sys, "frozen", False):
        return "dealership.db"

    local_app_data = Path(
        os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")
    )
    data_directory = local_app_data / "DealershipManager"
    data_directory.mkdir(parents=True, exist_ok=True)
    database_path = data_directory / "dealership.db"

    legacy_path = Path(sys.executable).resolve().parent / "dealership.db"
    if not database_path.exists() and legacy_path.is_file():
        source = sqlite3.connect(str(legacy_path))
        destination = sqlite3.connect(str(database_path))
        try:
            source.backup(destination)
        finally:
            destination.close()
            source.close()

    return database_path


try:
    from PIL import Image, ImageTk
except ImportError:
    Image = None
    ImageTk = None


class DealershipApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Dealership Manager")
        self.geometry("1080x680")
        self.minsize(820, 520)
        self.database = DealershipDatabase(_database_path())
        self._configure_style()

        heading = ttk.Frame(self, padding=(22, 18, 22, 10))
        heading.pack(fill="x")
        ttk.Label(heading, text="Dealership Manager", style="Title.TLabel").pack(
            anchor="w"
        )
        ttk.Label(
            heading,
            text="Keep your inventory and customer records organized.",
            style="Subtitle.TLabel",
        ).pack(anchor="w", pady=(3, 0))

        self.tabs = ttk.Notebook(self)
        self.tabs.pack(fill="both", expand=True, padx=20, pady=(6, 20))
        self._build_cars_tab()
        self._build_customers_tab()

    def _configure_style(self) -> None:
        style = ttk.Style(self)
        if "vista" in style.theme_names():
            style.theme_use("vista")
        style.configure("Title.TLabel", font=("Segoe UI", 21, "bold"))
        style.configure("Subtitle.TLabel", font=("Segoe UI", 10))
        style.configure("Treeview", rowheight=30, font=("Segoe UI", 10))
        style.configure("Treeview.Heading", font=("Segoe UI", 10, "bold"))
        style.configure("Section.TLabel", font=("Segoe UI", 13, "bold"))

    def _build_table_tab(self, title: str, columns: list[tuple[str, str, int]]) -> tuple:
        frame = ttk.Frame(self.tabs, padding=16)
        self.tabs.add(frame, text=title)
        toolbar = ttk.Frame(frame)
        toolbar.pack(fill="x", pady=(0, 12))
        ttk.Label(toolbar, text=title, style="Section.TLabel").pack(side="left")
        search_var = tk.StringVar()
        search = ttk.Entry(toolbar, textvariable=search_var, width=30)
        search.pack(side="right", padx=(8, 0))
        ttk.Label(toolbar, text="Search").pack(side="right")

        table_frame = ttk.Frame(frame)
        table_frame.pack(fill="both", expand=True)
        tree = ttk.Treeview(
            table_frame,
            columns=[column[0] for column in columns],
            show="headings",
            selectmode="browse",
        )
        for key, label, width in columns:
            tree.heading(key, text=label)
            tree.column(key, width=width, minwidth=70, anchor="w")
        vertical = ttk.Scrollbar(table_frame, orient="vertical", command=tree.yview)
        horizontal = ttk.Scrollbar(table_frame, orient="horizontal", command=tree.xview)
        tree.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
        tree.grid(row=0, column=0, sticky="nsew")
        vertical.grid(row=0, column=1, sticky="ns")
        horizontal.grid(row=1, column=0, sticky="ew")
        table_frame.rowconfigure(0, weight=1)
        table_frame.columnconfigure(0, weight=1)

        buttons = ttk.Frame(frame)
        buttons.pack(fill="x", pady=(12, 0))
        return frame, tree, search_var, search, buttons

    def _build_cars_tab(self) -> None:
        _, self.car_tree, self.car_search, car_entry, buttons = self._build_table_tab(
            "Cars",
            [
                ("make", "Make", 120),
                ("model", "Model", 140),
                ("year", "Year", 75),
                ("vin", "VIN", 180),
                ("mileage", "Mileage", 105),
                ("price", "Price", 105),
                ("status", "Status", 100),
            ],
        )
        ttk.Button(
            buttons, text="Add car", command=lambda: self._edit_car()
        ).pack(side="left")
        ttk.Button(
            buttons, text="Edit selected", command=self._edit_selected_car
        ).pack(side="left", padx=8)
        ttk.Button(
            buttons, text="Delete selected", command=self._delete_selected_car
        ).pack(side="left")
        self.car_tree.bind("<Double-1>", self._open_car_profile)
        self.car_search.trace_add("write", lambda *_: self._refresh_cars())
        car_entry.bind("<Return>", lambda _event: self._refresh_cars())
        self._refresh_cars()

    def _build_customers_tab(self) -> None:
        _, self.customer_tree, self.customer_search, entry, buttons = (
            self._build_table_tab(
                "Customers",
                [
                    ("first_name", "First name", 115),
                    ("last_name", "Last name", 115),
                    ("email", "Email", 190),
                    ("phone", "Phone", 125),
                    ("address", "Address", 300),
                ],
            )
        )
        ttk.Button(
            buttons, text="Add customer", command=lambda: self._edit_customer()
        ).pack(side="left")
        ttk.Button(
            buttons, text="Edit selected", command=self._edit_selected_customer
        ).pack(side="left", padx=8)
        ttk.Button(
            buttons, text="Delete selected", command=self._delete_selected_customer
        ).pack(side="left")
        self.customer_tree.bind("<Double-1>", self._open_customer_profile)
        self.customer_search.trace_add("write", lambda *_: self._refresh_customers())
        entry.bind("<Return>", lambda _event: self._refresh_customers())
        self._refresh_customers()

    def _replace_rows(self, tree: ttk.Treeview, rows: list[dict], keys: tuple) -> None:
        tree.delete(*tree.get_children())
        for row in rows:
            values = tuple(row[key] for key in keys)
            if "price" in row:
                values = tuple(
                    f"${row[key]:,.2f}" if key == "price" else row[key]
                    for key in keys
                )
            if "mileage" in row:
                values = tuple(
                    f"{row[key]:,}" if key == "mileage" else row[key]
                    for key in keys
                )
            tree.insert("", "end", iid=str(row["id"]), values=values)

    def _refresh_cars(self) -> None:
        rows = self.database.list_cars(self.car_search.get())
        self._replace_rows(
            self.car_tree,
            rows,
            ("make", "model", "year", "vin", "mileage", "price", "status"),
        )

    def _refresh_customers(self) -> None:
        rows = self.database.list_customers(self.customer_search.get())
        self._replace_rows(
            self.customer_tree,
            rows,
            ("first_name", "last_name", "email", "phone", "address"),
        )

    def _selected_id(self, tree: ttk.Treeview, entity: str) -> int | None:
        selection = tree.selection()
        if not selection:
            messagebox.showinfo("Select a record", f"Select a {entity} first.")
            return None
        return int(selection[0])

    def _edit_car(self, car: dict | None = None) -> None:
        self._show_form(
            title="Edit car" if car else "Add car",
            fields=[
                ("make", "Make", car.get("make", "") if car else ""),
                ("model", "Model", car.get("model", "") if car else ""),
                ("year", "Year", str(car.get("year", "")) if car else ""),
                ("vin", "VIN (optional)", car.get("vin", "") if car else ""),
                (
                    "mileage",
                    "Mileage",
                    str(car.get("mileage", 0)) if car else "0",
                ),
                ("price", "Price", str(car.get("price", 0)) if car else "0"),
                (
                    "status",
                    "Status",
                    car.get("status", "Available") if car else "Available",
                ),
                ("photos", "Photo library", car.get("photos", []) if car else []),
                ("notes", "Notes (optional)", car.get("notes", "") if car else ""),
            ],
            on_save=lambda values: self._save_car(values, car["id"] if car else None),
            choices={"status": CAR_STATUSES},
            multiline_fields=("notes",),
            photo_fields={"photos": MAX_CAR_PHOTOS},
        )

    def _save_car(self, values: dict, car_id: int | None) -> bool:
        try:
            self.database.save_car(values, car_id)
        except (ValueError, LookupError, sqlite3.IntegrityError) as error:
            detail = (
                "That VIN is already assigned to another car."
                if isinstance(error, sqlite3.IntegrityError)
                else str(error)
            )
            messagebox.showerror("Couldn't save car", detail)
            return False
        self._refresh_cars()
        return True

    def _edit_selected_car(self) -> None:
        car_id = self._selected_id(self.car_tree, "car")
        if car_id is not None:
            car = next(
                (row for row in self.database.list_cars() if row["id"] == car_id),
                None,
            )
            if car is not None:
                self._edit_car(car)

    def _open_car_profile(self, event: tk.Event) -> None:
        self._open_profile_from_row(event, self.car_tree, "car")

    def _open_customer_profile(self, event: tk.Event) -> None:
        self._open_profile_from_row(event, self.customer_tree, "customer")

    def _open_profile_from_row(
        self, event: tk.Event, tree: ttk.Treeview, entity: str
    ) -> None:
        item = tree.identify_row(event.y)
        if not item:
            return
        tree.selection_set(item)
        record_id = int(item)
        records = (
            self.database.list_cars()
            if entity == "car"
            else self.database.list_customers()
        )
        record = next((row for row in records if row["id"] == record_id), None)
        if record is not None:
            self._show_profile(record, entity)

    def _show_profile(self, record: dict, entity: str) -> None:
        is_car = entity == "car"
        title = (
            f'{record["year"]} {record["make"]} {record["model"]}'
            if is_car
            else f'{record["first_name"]} {record["last_name"]}'
        )
        fields = (
            (
                ("Year", record["year"]),
                ("Make", record["make"]),
                ("Model", record["model"]),
                ("VIN", record["vin"]),
                ("Mileage", f'{record["mileage"]:,} miles'),
                ("Price", f'${record["price"]:,.2f}'),
                ("Status", record["status"]),
            )
            if is_car
            else (
                ("First name", record["first_name"]),
                ("Last name", record["last_name"]),
                ("Email", record["email"]),
                ("Phone", record["phone"]),
                ("Address", record["address"]),
            )
        )

        dialog = tk.Toplevel(self)
        dialog.title(f"{title} — Profile")
        dialog.geometry("760x650")
        dialog.minsize(560, 450)
        container = ttk.Frame(dialog, padding=20)
        container.pack(fill="both", expand=True)
        ttk.Label(container, text=title, style="Title.TLabel").pack(anchor="w")
        ttk.Label(
            container,
            text=f"{entity.title()} profile",
            style="Subtitle.TLabel",
        ).pack(anchor="w", pady=(2, 14))

        overview = ttk.Frame(container)
        overview.pack(fill="x", expand=False)
        photo_paths = record.get("photos") or (
            [record["image_path"]] if record.get("image_path") else []
        )
        photo_frame = ttk.LabelFrame(
            overview,
            text=f"Photo library ({len(photo_paths)}/"
            f"{MAX_CAR_PHOTOS if is_car else MAX_CUSTOMER_PHOTOS})",
            padding=8,
        )
        photo_frame.pack(side="right", fill="both", padx=(16, 0))
        gallery_canvas = tk.Canvas(
            photo_frame, width=230, height=190, highlightthickness=0
        )
        gallery_scrollbar = ttk.Scrollbar(
            photo_frame, orient="vertical", command=gallery_canvas.yview
        )
        gallery_canvas.configure(yscrollcommand=gallery_scrollbar.set)
        gallery_canvas.pack(side="left", fill="both", expand=True)
        gallery_scrollbar.pack(side="right", fill="y")
        gallery = ttk.Frame(gallery_canvas)
        gallery_window = gallery_canvas.create_window(
            (0, 0), window=gallery, anchor="nw"
        )
        gallery.bind(
            "<Configure>",
            lambda _event: gallery_canvas.configure(
                scrollregion=gallery_canvas.bbox("all")
            ),
        )
        gallery_canvas.bind(
            "<Configure>",
            lambda event: gallery_canvas.itemconfigure(
                gallery_window, width=event.width
            ),
        )
        if not photo_paths:
            ttk.Label(gallery, text="No photos added yet.").grid(
                row=0, column=0, padx=8, pady=8
            )
        elif Image is None or ImageTk is None:
            ttk.Label(
                gallery,
                text="Install Pillow to display photos.\n"
                "Run: python -m pip install -r requirements.txt",
            ).grid(row=0, column=0, padx=8, pady=8)
        else:
            for index, photo_path in enumerate(photo_paths):
                tile = ttk.Frame(gallery, padding=4)
                tile.grid(row=index // 2, column=index % 2, sticky="nsew")
                try:
                    with Image.open(photo_path) as image:
                        image.thumbnail((98, 72), Image.Resampling.LANCZOS)
                        photo = ImageTk.PhotoImage(image.copy())
                    image_label = ttk.Label(tile, image=photo, cursor="hand2")
                    image_label.image = photo
                    image_label.pack()
                    image_label.bind(
                        "<Double-1>",
                        lambda _event, path=photo_path: self._show_photo_preview(path),
                    )
                except (OSError, ValueError, tk.TclError):
                    ttk.Label(tile, text="Photo unavailable", width=14).pack()
                ttk.Label(
                    tile,
                    text=Path(photo_path).name,
                    width=15,
                    anchor="center",
                ).pack()

        details = ttk.LabelFrame(overview, text="Details", padding=12)
        details.pack(side="left", fill="both", expand=True)
        for row, (label, value) in enumerate(fields):
            ttk.Label(details, text=f"{label}:", font=("Segoe UI", 10, "bold")).grid(
                row=row, column=0, sticky="nw", padx=(0, 12), pady=4
            )
            ttk.Label(
                details,
                text=str(value) if value not in ("", None) else "—",
                wraplength=310,
                justify="left",
            ).grid(row=row, column=1, sticky="nw", pady=4)

        ttk.Label(container, text="Notes", style="Section.TLabel").pack(
            anchor="w", pady=(16, 6)
        )
        notes_frame = ttk.Frame(container)
        notes_frame.pack(fill="both", expand=True)
        notes = tk.Text(notes_frame, wrap="word", height=8, font=("Segoe UI", 10))
        notes_scrollbar = ttk.Scrollbar(
            notes_frame, orient="vertical", command=notes.yview
        )
        notes.configure(yscrollcommand=notes_scrollbar.set)
        notes.insert("1.0", record.get("notes", "") or "No notes added.")
        notes.configure(state="disabled")
        notes.pack(side="left", fill="both", expand=True)
        notes_scrollbar.pack(side="right", fill="y")

    def _show_photo_preview(self, photo_path: str) -> None:
        if Image is None or ImageTk is None:
            return
        try:
            with Image.open(photo_path) as image:
                image.thumbnail((1100, 800), Image.Resampling.LANCZOS)
                photo = ImageTk.PhotoImage(image.copy())
        except (OSError, ValueError, tk.TclError) as error:
            messagebox.showerror("Couldn't open photo", str(error))
            return
        preview = tk.Toplevel(self)
        preview.title(Path(photo_path).name)
        image_label = ttk.Label(preview, image=photo)
        image_label.image = photo
        image_label.pack(padx=12, pady=12)

    def _delete_selected_car(self) -> None:
        car_id = self._selected_id(self.car_tree, "car")
        if car_id is not None and messagebox.askyesno(
            "Delete car", "Delete this car from inventory?"
        ):
            try:
                self.database.delete_car(car_id)
            except LookupError as error:
                messagebox.showerror("Couldn't delete car", str(error))
            self._refresh_cars()

    def _edit_customer(self, customer: dict | None = None) -> None:
        self._show_form(
            title="Edit customer" if customer else "Add customer",
            fields=[
                ("first_name", "First name", customer.get("first_name", "") if customer else ""),
                ("last_name", "Last name", customer.get("last_name", "") if customer else ""),
                ("email", "Email (optional)", customer.get("email", "") if customer else ""),
                ("phone", "Phone (optional)", customer.get("phone", "") if customer else ""),
                ("address", "Address (optional)", customer.get("address", "") if customer else ""),
                (
                    "photos",
                    "Photo library",
                    customer.get("photos", []) if customer else [],
                ),
                (
                    "notes",
                    "Notes (optional)",
                    customer.get("notes", "") if customer else "",
                ),
            ],
            on_save=lambda values: self._save_customer(
                values, customer["id"] if customer else None
            ),
            multiline_fields=("notes",),
            photo_fields={"photos": MAX_CUSTOMER_PHOTOS},
        )

    def _save_customer(self, values: dict, customer_id: int | None) -> bool:
        try:
            self.database.save_customer(values, customer_id)
        except (ValueError, LookupError) as error:
            messagebox.showerror("Couldn't save customer", str(error))
            return False
        self._refresh_customers()
        return True

    def _edit_selected_customer(self) -> None:
        customer_id = self._selected_id(self.customer_tree, "customer")
        if customer_id is not None:
            customer = next(
                (
                    row
                    for row in self.database.list_customers()
                    if row["id"] == customer_id
                ),
                None,
            )
            if customer is not None:
                self._edit_customer(customer)

    def _delete_selected_customer(self) -> None:
        customer_id = self._selected_id(self.customer_tree, "customer")
        if customer_id is not None and messagebox.askyesno(
            "Delete customer", "Delete this customer profile?"
        ):
            try:
                self.database.delete_customer(customer_id)
            except LookupError as error:
                messagebox.showerror("Couldn't delete customer", str(error))
            self._refresh_customers()

    def _show_form(
        self,
        title: str,
        fields: list[tuple[str, str, Any]],
        on_save: Callable[[dict[str, Any]], bool],
        choices: dict[str, tuple[str, ...]] | None = None,
        multiline_fields: tuple[str, ...] = (),
        photo_fields: dict[str, int] | None = None,
    ) -> None:
        dialog = tk.Toplevel(self)
        dialog.title(title)
        dialog.transient(self)
        dialog.resizable(False, False)
        dialog.grab_set()
        container = ttk.Frame(dialog, padding=20)
        container.pack(fill="both", expand=True)
        variables: dict[str, tk.StringVar] = {}
        text_widgets: dict[str, tk.Text] = {}
        photo_lists: dict[str, list[str]] = {}
        for row, (key, label, value) in enumerate(fields):
            ttk.Label(container, text=label).grid(
                row=row, column=0, sticky="w", padx=(0, 16), pady=5
            )
            if photo_fields and key in photo_fields:
                maximum = photo_fields[key]
                photos = list(value) if isinstance(value, (list, tuple)) else []
                photo_lists[key] = photos
                photo_section = ttk.Frame(container)
                photo_section.grid(row=row, column=1, sticky="ew", pady=5)
                photo_list = tk.Listbox(
                    photo_section,
                    height=4,
                    width=34,
                    selectmode="extended",
                    exportselection=False,
                )
                photo_list.pack(fill="x")
                photo_count = tk.StringVar()

                def refresh_photo_list(
                    paths=photos, listing=photo_list, count=photo_count, limit=maximum
                ) -> None:
                    listing.delete(0, "end")
                    for path in paths:
                        listing.insert("end", Path(path).name or path)
                    count.set(f"{len(paths)} of {limit} photos")

                def add_photos(
                    paths=photos,
                    listing=photo_list,
                    count=photo_count,
                    limit=maximum,
                ) -> None:
                    available = limit - len(paths)
                    if available <= 0:
                        messagebox.showinfo(
                            "Photo limit reached",
                            f"This profile already has the maximum of {limit} photos.",
                            parent=dialog,
                        )
                        return
                    selected = filedialog.askopenfilenames(
                        parent=dialog,
                        title="Choose photos",
                        filetypes=[
                            (
                                "Image files",
                                "*.png *.jpg *.jpeg *.gif *.bmp *.webp *.tif *.tiff",
                            ),
                            ("All files", "*.*"),
                        ],
                    )
                    skipped = 0
                    for selected_path in selected:
                        path = str(Path(selected_path))
                        if path not in paths and len(paths) < limit:
                            paths.append(path)
                        elif path not in paths:
                            skipped += 1
                    refresh_photo_list(paths, listing, count, limit)
                    if skipped:
                        messagebox.showinfo(
                            "Photo limit reached",
                            f"{skipped} photo(s) weren't added because the "
                            f"profile limit is {limit}.",
                            parent=dialog,
                        )

                def remove_photos(
                    paths=photos,
                    listing=photo_list,
                    count=photo_count,
                    limit=maximum,
                ) -> None:
                    selected = list(listing.curselection())
                    for index in reversed(selected):
                        del paths[index]
                    refresh_photo_list(paths, listing, count, limit)

                photo_actions = ttk.Frame(photo_section)
                photo_actions.pack(fill="x", pady=(4, 0))
                ttk.Button(
                    photo_actions, text="Add photos...", command=add_photos
                ).pack(side="left")
                ttk.Button(
                    photo_actions, text="Remove selected", command=remove_photos
                ).pack(side="left", padx=(6, 0))
                ttk.Label(photo_actions, textvariable=photo_count).pack(side="right")
                refresh_photo_list()
                continue
            variable = tk.StringVar(value=value)
            variables[key] = variable
            if choices and key in choices:
                widget = ttk.Combobox(
                    container,
                    textvariable=variable,
                    values=choices[key],
                    state="readonly",
                    width=31,
                )
            elif key in multiline_fields:
                widget = tk.Text(container, width=32, height=5, wrap="word")
                widget.insert("1.0", value)
                text_widgets[key] = widget
            else:
                widget = ttk.Entry(container, textvariable=variable, width=34)
            widget.grid(row=row, column=1, sticky="ew", pady=5)
        actions = ttk.Frame(container)
        actions.grid(row=len(fields), column=0, columnspan=2, sticky="e", pady=(14, 0))

        def submit() -> None:
            values: dict[str, Any] = {
                key: variable.get() for key, variable in variables.items()
            }
            values.update(
                {
                    key: widget.get("1.0", "end-1c")
                    for key, widget in text_widgets.items()
                }
            )
            values.update(photo_lists)
            if on_save(values):
                dialog.destroy()

        ttk.Button(actions, text="Cancel", command=dialog.destroy).pack(side="right")
        ttk.Button(actions, text="Save", command=submit).pack(
            side="right", padx=(0, 8)
        )
        dialog.bind("<Return>", lambda _event: submit())
        first_input = container.grid_slaves(row=0, column=1)
        if first_input:
            first_input[0].focus_set()

if __name__ == "__main__":
    DealershipApp().mainloop()
