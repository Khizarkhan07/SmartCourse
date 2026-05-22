# SmartCourse — Intelligent Course Delivery Platform

A scalable, async backend for a modern learning management system supporting universities, enterprises, and training academies.

---

## Architecture

![SmartCourse Week 1 Architecture](Week1-arch.png)

> Full architecture breakdown and design decisions: [docs/architecture.md](docs/architecture.md)

---

## Tech Stack

| Technology | Purpose |
|---|---|
| **Python 3.14 + FastAPI** | Async web framework |
| **PostgreSQL 16** | Primary relational database |
| **SQLAlchemy 2 (async)** | ORM with connection pooling |
| **asyncpg** | Async PostgreSQL driver |
| **Alembic** | Database schema migrations |
| **Pydantic v2** | Request/response validation |
| **python-jose** | JWT authentication |
| **bcrypt** | Password hashing |
| **slowapi** | Rate limiting |
| **Docker + Docker Compose** | Local infrastructure |

---

## Project Structure

```
SmartCourse/
├── app/
│   ├── main.py              # App entry point, middleware registration
│   ├── config.py            # Environment config (pydantic-settings)
│   ├── database.py          # Async engine, connection pool, session factory
│   ├── auth.py              # JWT creation/decoding, role guard dependency
│   ├── security.py          # bcrypt password hashing
│   ├── models/
│   │   ├── user.py          # User table (id, name, email, role, ...)
│   │   └── course.py        # Course table (id, title, status, instructor_id, ...)
│   ├── schemas/
│   │   ├── user.py          # UserCreate, UserLogin, UserResponse
│   │   └── course.py        # CourseCreate, CourseUpdate, CourseResponse
│   ├── services/
│   │   ├── user_service.py  # User business logic
│   │   └── course_service.py# Course business logic
│   └── routers/
│       ├── auth.py          # POST /auth/login
│       ├── users.py         # POST/GET /users
│       └── courses.py       # POST/GET/PATCH /courses
├── alembic/                 # DB migration files
├── docs/
│   └── architecture.md      # Architecture diagram + design decisions
├── docker-compose.yml       # PostgreSQL container
├── requirements.txt
├── .env                     # Local config (not committed)
└── .gitignore
```

---

## Local Setup

### Prerequisites
- Python 3.11+
- Docker Desktop

### 1. Clone the repository

```bash
git clone <repo-url>
cd SmartCourse
```

### 2. Create and activate virtual environment

```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment variables

Create a `.env` file in the root directory:

```env
# Database
DATABASE_URL=postgresql+asyncpg://smartcourse_user:smartcourse_pass@localhost:5433/smartcourse_db
DATABASE_URL_SYNC=postgresql+psycopg2://smartcourse_user:smartcourse_pass@localhost:5433/smartcourse_db

# App
APP_ENV=development
SECRET_KEY=change-this-to-a-random-secret-in-production
CORS_ORIGINS=http://localhost:3000,http://localhost:5173

# JWT
ACCESS_TOKEN_EXPIRE_MINUTES=60
ALGORITHM=HS256
```

### 5. Start PostgreSQL with Docker

```bash
docker-compose up -d
```

### 6. Run database migrations

```bash
alembic upgrade head
```

### 7. Start the development server

```bash
uvicorn app.main:app --reload --port 8000
```

The API is now running at `http://localhost:8000`

---

## API Documentation

FastAPI auto-generates interactive docs:

| URL | Description |
|---|---|
| `http://localhost:8000/docs` | Swagger UI — interactive, supports auth |
| `http://localhost:8000/redoc` | ReDoc — clean reference docs |
| `http://localhost:8000/health` | Health check |

---

## API Endpoints

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| `POST` | `/auth/login` | Public (rate limited 5/min) | Login, receive JWT token |
| `POST` | `/users/` | Public | Register new user |
| `GET` | `/users/` | Authenticated | List users (paginated) |
| `GET` | `/users/{id}` | Authenticated | Get user by ID |
| `POST` | `/courses/` | Instructor / Admin | Create course |
| `GET` | `/courses/` | Public | List courses (paginated) |
| `GET` | `/courses/{id}` | Public | Get course by ID |
| `PATCH` | `/courses/{id}` | Instructor (owner) / Admin | Update course |

### Pagination

All list endpoints support:
```
?limit=20&offset=0    → first 20 results
?limit=20&offset=20   → next 20 results
```
Max `limit` is 100.

---

## User Roles

| Role | Permissions |
|---|---|
| `student` | Browse courses, enroll (Week 2) |
| `instructor` | Create and manage own courses |
| `admin` | Full access |

---

## Development Notes

### Running migrations after model changes

```bash
alembic revision --autogenerate -m "describe your change"
alembic upgrade head
```

### Resetting the database

```bash
docker-compose down -v   # removes volume — all data lost
docker-compose up -d
alembic upgrade head
```
