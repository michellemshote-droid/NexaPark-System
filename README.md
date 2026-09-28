# NexaPark Kenya — Modern Car Parking System

A Flask + SQLite web-based parking management system.

## 1. Main Features

### Customer Features

- View live parking-slot availability from the home page.
- Register a vehicle at the parking entrance.
- Automatically assign an available parking bay.
- Calculate parking duration and parking fees at exit.
- Complete a payment and release the parking bay.
- Pre-book parking capacity for a future arrival/departure window.
- Cancel a booking using the booking reference and vehicle plate.
- Use valet drop-off instead of parking the vehicle yourself.
- Request valet pickup when the vehicle is ready to be returned.
- Make M-Pesa payments through the Safaricom Daraja API.

### Admin Features

The authenticated admin dashboard provides access to:

- Dashboard statistics
- Currently parked vehicles
- Parking-slot status
- Online bookings
- Valet operations
- Payment records
- Parking history
- Daily reports

The admin area is protected by a username and password.

---

# 2. Technology Used

- **Python 3** — application programming language
- **Flask** — web framework
- **SQLite** — local database
- **HTML/CSS/JavaScript** — web interface
- **Werkzeug** — password hashing and related Flask security utilities
- **Safaricom M-Pesa Daraja API** — M-Pesa STK Push and payment callbacks
- **ngrok** — used during local development to expose the M-Pesa callback endpoint publicly

No separate MySQL/PostgreSQL server is required for this local application.

---

# 3. Project Structure

```text
modern-car-parking-system/
│
├── app.py                         # Main Flask application and routes
├── auth.py                        # Admin authentication and password checks
├── database.py                    # SQLite database setup and queries
├── parking.py                     # Parking, booking and valet business logic
├── pricing.py                     # Parking-fee calculation
├── requirements.txt               # Python dependencies
├── README.md                      # Project documentation
│
├── database/
│   └── .gitkeep                   # Database folder; parking.db is created here
│
├── static/
│   ├── css/
│   │   └── style.css              # Website styling
│   └── js/
│       └── main.js                # Client-side JavaScript
│
└── templates/
    ├── base.html                  # Shared customer-page layout/navigation
    ├── index.html                 # Home page
    ├── entry.html                 # Vehicle entry form
    ├── entry_success.html         # Successful entry result
    ├── exit.html                  # Vehicle exit form
    ├── payment.html               # Exit/payment confirmation
    ├── exit_success.html          # Successful exit result
    ├── book.html                  # Pre-booking form
    ├── book_success.html          # Booking confirmation
    ├── book_cancel.html           # Booking cancellation form
    ├── valet_dropoff.html         # Valet drop-off form
    ├── valet_dropoff_success.html # Successful valet drop-off
    ├── valet_pickup.html          # Valet pickup request form
    │
    └── admin/
        ├── base.html              # Shared admin layout
        ├── login.html             # Admin login
        ├── dashboard.html         # Admin dashboard
        ├── vehicles.html          # Active vehicles
        ├── slots.html             # Slot monitoring
        ├── bookings.html          # Booking management
        ├── valet.html             # Valet management
        ├── payments.html          # Payment records
        ├── history.html           # Parking history
        └── reports.html           # Reports
```

---

# 4. Requirements

Install:

- **Python 3.10+ recommended**
- `pip`
- A modern web browser such as Chrome, Edge or Firefox

The project does not require Node.js, XAMPP, MySQL or a separate database server.

---

# 5. Cross-Platform Setup

NexaPark is a Python/Flask application and can be developed on **Windows, Linux, or macOS**. The application itself is not tied to one operating system.

The commands differ mainly when creating and activating the Python virtual environment. Choose the section that matches your operating system.

## 5.1 Windows — PowerShell

Open **PowerShell** and move into the project folder:

```powershell
cd path\to\modern-car-parking-system
```

### Step 1 — Check Python

```powershell
python --version
```

If `python` is not available, try:

```powershell
py --version
```

### Step 2 — Create a Virtual Environment

```powershell
python -m venv .venv
```

If your system uses the Python launcher instead:

```powershell
py -m venv .venv
```

### Step 3 — Activate the Environment

```powershell
.venv\Scripts\activate.ps1
```

If PowerShell blocks the activation script, you can allow locally-created scripts for your user account with:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

Then run the activation command again.

### Step 4 — Install Dependencies

```powershell
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### Step 5 — Create the First Admin Account

```powershell
flask --app app.py create-admin
```

The terminal will ask for a username and password. Password input is hidden while you type.

The password must:

- contain at least 10 characters;
- contain at least one letter; and
- contain at least one digit.

There is no hard-coded default admin password.

### Step 6 — Start NexaPark

```powershell
python app.py
```

Open the local address shown by Flask, normally:

```text
http://127.0.0.1:5000/
```

### Step 7 — Stop the Server

Press `Ctrl + C` in the terminal running Flask.

## 5.2 Windows — Command Prompt

The same project can be run from Command Prompt:

```cmd
cd path\to\modern-car-parking-system

python -m venv .venv

.venv\Scripts\activate

python -m pip install --upgrade pip

pip install -r requirements.txt

flask --app app.py create-admin

python app.py
```

## 5.3 Linux — Bash

Open a terminal and move into the project folder:

```bash
cd /path/to/modern-car-parking-system
```

Check Python:

```bash
python3 --version
```

Create the virtual environment:

```bash
python3 -m venv .venv
```

Activate it:

```bash
source .venv/bin/activate
```

Install dependencies:

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Create the first admin account:

```bash
flask --app app.py create-admin
```

Start NexaPark:

```bash
python app.py
```

Then open:

```text
http://127.0.0.1:5000/
```

This method also applies to Linux distributions such as Ubuntu and Kali Linux.

## 5.4 macOS — Terminal

Open Terminal and move into the project folder:

```bash
cd /path/to/modern-car-parking-system

python3 --version

python3 -m venv .venv

source .venv/bin/activate

python -m pip install --upgrade pip

pip install -r requirements.txt

flask --app app.py create-admin

python app.py
```

Then open:

```text
http://127.0.0.1:5000/
```

## 5.5 Setup Scripts Included with the Project

For convenience, the project includes platform-specific setup scripts:

- `setup_windows.ps1` — Windows PowerShell
- `setup_linux_mac.sh` — Linux/macOS Bash

These scripts automate the virtual-environment and dependency-installation steps. You still create the admin account explicitly so that credentials are not hard-coded into the project.

> **Note:** A `.bat` file is a Windows batch script, while a `.sh` file is a Bash shell script. Simply renaming a `.bat` file to `.sh` does not convert the commands. The scripts included here use the correct commands for their respective shells.

---

# 6. Configuration and Environment Variables

NexaPark can receive configuration through environment variables. This is useful when deploying the application or when you do not want secrets written directly into source code.

## Admin Account Variables

If both variables are supplied, the application can create the account once when it starts:

### PowerShell

```powershell
$env:NEXAPARK_ADMIN_USERNAME="admin"
$env:NEXAPARK_ADMIN_PASSWORD="YourOwnStrongPasswordHere"

python app.py
```

### Linux/macOS Bash

```bash
export NEXAPARK_ADMIN_USERNAME="admin"
export NEXAPARK_ADMIN_PASSWORD="YourOwnStrongPasswordHere"

python app.py
```

The interactive `flask --app app.py create-admin` command is usually easier for local development. Existing admin accounts are not overwritten automatically.

Treat passwords and secret keys as secrets. Do not commit credentials or secret values to GitHub or place them directly in source code.

## Application Secret Key

For deployment, set a strong secret key.

### PowerShell

```powershell
$env:NEXAPARK_SECRET_KEY="replace-with-a-long-random-secret"
```

### Linux/macOS Bash

```bash
export NEXAPARK_SECRET_KEY="replace-with-a-long-random-secret"
```

To enable secure session cookies when the application is served over HTTPS:

### PowerShell

```powershell
$env:NEXAPARK_HTTPS="1"
```

### Linux/macOS Bash

```bash
export NEXAPARK_HTTPS="1"
```

Debug mode is disabled by default. For local development only, it can be enabled with `FLASK_DEBUG=1`. Do not use Flask debug mode as a production configuration.

---

# 7. Customer Workflow

## A. Normal Parking Entry

1. Open the home page.
2. Select **Enter Parking**.
3. Enter the vehicle plate number.
4. Select the vehicle type.
5. Submit the form.
6. NexaPark checks available capacity and assigns an available bay.
7. The entry time and assigned bay are displayed.

## B. Vehicle Exit

1. Select **Vehicle Exit**.
2. Enter the same vehicle plate number used at entry.
3. NexaPark calculates the parking duration.
4. The applicable parking fee is displayed.
5. Select **Pay & Open Exit Barrier**.
6. The application records the payment and completes the parking session.
7. The occupied bay is released.

For the current software implementation, the physical parking barrier is not connected to the application. The software records the payment and completes the exit workflow.

---

# 8. Parking Pricing

The fee rules are defined in `pricing.py`.

The current pricing model is:

| Parking Duration  |     Fee |
| ----------------- | ------: |
| Up to 30 minutes  |   KSh 0 |
| Up to 2 hours     |  KSh 50 |
| Up to 4 hours     | KSh 100 |
| Up to 6 hours     | KSh 300 |
| More than 6 hours | KSh 500 |

If the pricing rules are changed, edit `pricing.py` rather than changing the HTML pages.

---

# 9. Online Pre-Booking

NexaPark adds online parking-capacity booking through `/book`.

A customer supplies:

- Vehicle plate number
- Vehicle type
- Requested arrival time
- Requested departure time
- Optional valet service

If capacity is available for the requested period, the system creates a booking and proceeds through the configured payment process.

## Important Design Detail

NexaPark reserves **parking capacity**, not a specific bay number.

For example, if the facility has 20 bays and 5 compatible bookings overlap during a period, those bookings reserve 5 spaces of capacity. The actual bay number is assigned when the vehicle arrives.

This avoids changing the existing bay-allocation logic unnecessarily.

## Booking at Entry

When a vehicle arrives, NexaPark checks whether its plate has a confirmed booking whose window has started. If so, the booking is linked to the new parking session automatically.

Walk-in vehicles can still enter when capacity allows.

## No-Shows

Confirmed bookings that pass their departure time without being checked in can be marked `NO_SHOW`, releasing the reserved capacity.

## Cancel a Booking

Use:

```text
/book/cancel
```

The customer must provide the booking reference and the plate number used for the booking.

---

# 10. Valet Parking

NexaPark adds a separate valet workflow.

## Valet Drop-Off

Customer page:

```text
/valet/dropoff
```

The customer provides:

- Vehicle plate
- Vehicle type
- Optional drop-off location/note

The system records the vehicle as a valet parking session while still using the same parking-capacity rules as normal parking.

## Request Valet Pickup

Customer page:

```text
/valet/pickup
```

The customer enters the vehicle plate and submits a pickup request.

The valet status moves through:

```text
PARKED → RETRIEVING → DELIVERED
```

## Admin Valet Control

Admin page:

```text
/admin/valet
```

The admin can view valet vehicles, bays and statuses and advance a request from `PARKED` to `RETRIEVING` and then to `DELIVERED`.

After the vehicle is returned, the customer still uses the normal **Vehicle Exit** and payment flow to complete the parking session.

---

# 11. Admin Dashboard

Open:

```text
/admin/login
```

After successful authentication, the admin can access:

```text
/admin/dashboard
/admin/vehicles
/admin/slots
/admin/bookings
/admin/valet
/admin/payments
/admin/history
/admin/reports
```

Unauthenticated users are redirected to the admin login page when attempting to access protected admin pages.

## Account Security

- Passwords are stored as salted password hashes rather than plain text.
- Admin sessions use HTTP-only cookies.
- SameSite cookies are set to `Lax`.
- Login attempts are rate-limited through temporary account lockout after repeated failures.
- HTTPS deployments can enable secure session cookies.

---

# 12. Useful URLs

When the server is running locally:

| Page            | URL                                                                            |
| --------------- | ------------------------------------------------------------------------------ |
| Home            | [http://127.0.0.1:5000/](http://127.0.0.1:5000/)                               |
| Enter Parking   | [http://127.0.0.1:5000/entry](http://127.0.0.1:5000/entry)                     |
| Vehicle Exit    | [http://127.0.0.1:5000/exit](http://127.0.0.1:5000/exit)                       |
| Pre-book a Bay  | [http://127.0.0.1:5000/book](http://127.0.0.1:5000/book)                       |
| Cancel Booking  | [http://127.0.0.1:5000/book/cancel](http://127.0.0.1:5000/book/cancel)         |
| Valet Drop-off  | [http://127.0.0.1:5000/valet/dropoff](http://127.0.0.1:5000/valet/dropoff)     |
| Valet Pickup    | [http://127.0.0.1:5000/valet/pickup](http://127.0.0.1:5000/valet/pickup)       |
| Admin Login     | [http://127.0.0.1:5000/admin/login](http://127.0.0.1:5000/admin/login)         |
| Admin Dashboard | [http://127.0.0.1:5000/admin/dashboard](http://127.0.0.1:5000/admin/dashboard) |
| Slot API        | [http://127.0.0.1:5000/api/slots](http://127.0.0.1:5000/api/slots)             |

---

# 13. Database

The application uses SQLite.

The database file is created automatically under:

```text
database/parking.db
```

On startup, the application initializes the required tables and parking slots.

If an older NexaPark database already exists, the application contains initialization logic for the newer tables and columns used by bookings and valet operations.

For a clean development test, you can remove the local `database/parking.db` and start the application again. This will reset the local test data, so do not do this if you need to preserve existing records.

---

# 14. Troubleshooting

## `python` Is Not Recognized

Try:

```powershell
py --version
```

If Python is installed but the `python` command is unavailable, use `py` in the commands or reinstall Python with the option to add it to PATH.

## `pip install -r requirements.txt` Fails

Make sure the virtual environment is active:

```powershell
.venv\Scripts\activate
```

Then try:

```powershell
python -m pip install -r requirements.txt
```

An internet connection is normally required when installing Flask and Werkzeug for the first time.

## The Browser Says the Page Cannot Be Reached

Make sure Flask is still running in the terminal and that you opened the exact address printed by Flask, normally:

```text
http://127.0.0.1:5000/
```

## Admin Login Does Not Work

If no admin account has been created, run:

```powershell
flask --app app.py create-admin
```

Then create the username and password interactively.

## Port 5000 Is Already in Use

Stop the other Flask application using that port, or change the development configuration before starting the server.

## I Changed HTML/CSS but Cannot See the Change

Refresh the browser. If the old CSS still appears, use a hard refresh such as:

```text
Ctrl + F5
```

---

# 15. M-Pesa / Daraja Integration

NexaPark integrates with the **Safaricom M-Pesa Daraja API** to support payment processing through M-Pesa STK Push.

The integration is used for:

- Pre-booking deposits
- Remaining parking and valet balances at vehicle exit
- M-Pesa payment status tracking
- Daraja callback confirmation
- Recording confirmed transactions in the database

## M-Pesa Payment Workflow

```text
Customer selects payment
        ↓
NexaPark calculates amount due
        ↓
NexaPark requests an M-Pesa STK Push
        ↓
Customer completes payment on the M-Pesa device
        ↓
Safaricom sends a callback to NexaPark
        ↓
NexaPark verifies and records the transaction
        ↓
Payment status is updated
        ↓
Booking or parking session is completed
```

During local development, the Daraja callback endpoint can be exposed using an HTTPS ngrok tunnel.

---

# 16. Current Implementation Scope

NexaPark is a working local software system for managing:

- Parking operations
- Online bookings
- Valet workflows
- Administration
- Payment records
- M-Pesa payment processing
- Reporting

The following physical or production infrastructure is not currently connected to the software:

- Physical parking barrier controller
- Physical bay-occupancy sensors
- License-plate recognition cameras
- Production hosting/infrastructure

The implemented Flask application provides the software workflows that can later be connected to physical parking equipment and production infrastructure.

---

# 17. Quick-Start Summary

### Windows PowerShell

```powershell
cd path\to\modern-car-parking-system

python -m venv .venv

.\.venv\Scripts\Activate.ps1

pip install -r requirements.txt

flask --app app.py create-admin

python app.py
```

### Linux/macOS Bash

```bash
cd /path/to/modern-car-parking-system

python3 -m venv .venv

source .venv/bin/activate

pip install -r requirements.txt

flask --app app.py create-admin

python app.py
```

Then open:

```text
http://127.0.0.1:5000/
```

For the admin area:

```text
http://127.0.0.1:5000/admin/login
```

## Valet and Pre-Booking Payments

Pre-bookings use a **50% M-Pesa deposit flow**:

1. The customer selects arrival/departure times and optionally adds valet service.
2. Parking is priced from the selected duration.
3. Valet adds KSh 100 to the total.
4. The customer enters an M-Pesa number and receives an STK Push for 50% of the total.
5. The booking remains `PENDING_PAYMENT` until Daraja confirms the deposit.
6. After confirmation it becomes `CONFIRMED` and the customer can check in with the same plate.
7. If valet was selected, the check-in automatically creates a valet request.
8. At exit, the system calculates the actual parking and valet total and subtracts the deposit already paid. Only the remaining balance is sent to M-Pesa.

Unpaid booking attempts expire after 15 minutes. Confirmed bookings that pass their end time without check-in become `NO_SHOW`.

### M-Pesa Callback

`MPESA_CALLBACK_URL` must be a publicly reachable HTTPS URL ending in `/mpesa/callback`.

Daraja callbacks are used to confirm booking deposits and final parking-balance payments.

## Environment File

NexaPark can also use a `.env` file to store local environment variables and sensitive configuration.

The `.env` file may contain values such as:

- Application secret key
- M-Pesa/Daraja consumer key
- M-Pesa/Daraja consumer secret
- M-Pesa shortcode
- M-Pesa passkey
- M-Pesa callback URL
- Other environment-specific configuration values required by the application

Example:

````text
NEXAPARK_SECRET_KEY=replace-with-a-long-random-secret

MPESA_CALLBACK_URL=https://your-public-domain/mpesa/callback## Environment File

NexaPark can also use a `.env` file to store local environment variables and sensitive configuration.

The `.env` file may contain values such as:

- Application secret key
- M-Pesa/Daraja consumer key
- M-Pesa/Daraja consumer secret
- M-Pesa shortcode
- M-Pesa passkey
- M-Pesa callback URL
- Other environment-specific configuration values required by the application

Example:

```text
NEXAPARK_SECRET_KEY=replace-with-a-long-random-secret

MPESA_CALLBACK_URL=https://your-public-domain/mpesa/callback
````
