# CoopManager Pro 🏢

An advanced, full-stack Cooperative Management System designed to handle members, savings, loans, shares, contributions, and general cooperative finances.

## 🌟 Features

* **Role-Based Access Control (RBAC):** Distinct dashboards and permissions for Super Admins, Managers, Loan Officers, and standard Members.
* **Member Management & KYC:** Track member profiles, next of kin, and securely upload/verify KYC documents.
* **Savings & Wallets:** Manage individual member savings accounts, deposits, withdrawals, and dividend payouts.
* **Loan Processing:** Configurable loan products, application workflows, guarantor approvals, and automated repayment tracking.
* **Share Capital Management:** Track total cooperative shares, unit prices, and member shareholdings.
* **Contributions & Fines:** Automate mandatory/voluntary dues, levies, and penalty tracking.
* **Financial Ledger:** Global cooperative income and expense tracking.
* **Analytics Dashboard:** Real-time visual metrics using Recharts.

## 🛠️ Tech Stack

**Backend**
* Python 3.10+
* Django 5.0 & Django REST Framework
* PostgreSQL
* Simple JWT (JSON Web Tokens)

**Frontend**
* React 18 (Vite)
* Tailwind CSS
* React Router v6
* Axios (with automated interceptors)
* Lucide React & Recharts

## 📋 Prerequisites

Before you begin, ensure you have the following installed:
* [Node.js](https://nodejs.org/) (v18.0 or higher required for Vite)
* [Python](https://www.python.org/downloads/) (v3.10 or higher)
* [PostgreSQL](https://www.postgresql.org/) (running locally or via Docker)

---

## 🚀 Local Development Setup

### 1. Database Setup
Create a new PostgreSQL database. You can do this via pgAdmin or the psql CLI:
```sql
CREATE DATABASE cooperative_db;
CREATE USER coop_user WITH PASSWORD 'Coop@12345';
GRANT ALL PRIVILEGES ON DATABASE cooperative_db TO coop_user;
```

### 2. Backend Setup
Navigate to the backend directory, set up your virtual environment, and install dependencies.

```bash
cd backend

# Create and activate virtual environment
python -m venv venv
# On Windows: .\venv\Scripts\Activate.ps1
# On Mac/Linux: source venv/bin/activate

# Install requirements
pip install -r requirements.txt
```

**Environment Variables**
Create a `.env` file inside the `backend` folder next to `manage.py`:
```env
DEBUG=True
SECRET_KEY=your-secret-key-here
ALLOWED_HOSTS=127.0.0.1,localhost

DB_NAME=cooperative_db
DB_USER=coop_user
DB_PASSWORD=Coop@12345
DB_HOST=localhost
DB_PORT=5432

CORS_ALLOWED_ORIGIN=http://localhost:5173
```

**Migrate & Run**
```bash
# Apply database migrations
python manage.py migrate

# Create your admin account
python manage.py createsuperuser

# Start the server
python manage.py runserver
```
*The backend API will run on `http://127.0.0.1:8000`*

### 3. Frontend Setup
Open a new terminal window, navigate to the frontend directory, and install dependencies.

```bash
cd frontend

# Install Node modules
npm install

# Start the development server
npm run dev
```
*The frontend application will run on `http://localhost:5173`*

---

## 🔐 Default API Endpoints

* **Admin Panel:** `http://127.0.0.1:8000/admin/`
* **Auth (Login):** `/api/v1/auth/login/`
* **Dashboard Summary:** `/api/v1/reports/dashboard-summary/`

## 📁 Project Structure

```text
cooperative-management-system/
├── backend/                  # Django API
│   ├── apps/                 # Modular Django apps (loans, savings, etc.)
│   ├── config/               # Main Django settings & URLs
│   ├── manage.py
│   └── requirements.txt
├── frontend/                 # React UI
│   ├── src/
│   │   ├── api/              # Axios configuration & interceptors
│   │   ├── components/       # Reusable UI components
│   │   ├── context/          # React Context (Auth)
│   │   ├── layouts/          # Page layouts (Sidebar/Navbar)
│   │   └── pages/            # Route components
│   ├── index.html
│   ├── tailwind.config.js
│   └── package.json
├── .gitignore
└── README.md
```