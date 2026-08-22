# Intelligent Loan Risk Assessment System (Backend)

This is the backend API for the Intelligent Loan Risk Assessment System. It is built using Node.js, Express, and MongoDB.

## Features
- **RBAC**: Role-based access control for Applicants, Officers, and Admins
- **Clean Architecture**: Routes → Controllers → Services → Models
- **AI Integration**: Internal mock ML service and client service to connect to an external Python/FastAPI microservice
- **Auto-decisioning**: Evaluates AI risk scores against configured thresholds to auto-approve/reject loans
- **Audit Trails**: Full system action logging

## Prerequisites
- Node.js (v18+)
- MongoDB (running locally on default port 27017, or update `MONGODB_URI`)

## Setup
1. Copy `.env.example` to `.env` (already done by the setup script)
2. Ensure MongoDB is running.
3. Install dependencies:
   ```bash
   npm install
   ```
4. Seed the database with default users (Admin, Officer, Applicant):
   ```bash
   npm run seed
   ```

## Running the Server
```bash
# Development (with nodemon)
npm run dev

# Production
npm start
```
Server runs on `http://localhost:5000` by default.

## Testing
Run the Jest and Supertest suite:
```bash
npm test
```

## API Postman Testing
Test users created by `npm run seed`:
- **Admin**: `admin@loanrisk.com` / `password123`
- **Officer**: `officer@loanrisk.com` / `password123`
- **Applicant**: `applicant@loanrisk.com` / `password123`
