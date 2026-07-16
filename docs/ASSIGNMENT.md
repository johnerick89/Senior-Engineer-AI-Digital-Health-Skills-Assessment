# Last Mile Health — Senior Full-Stack Engineer, AI & Digital Health Practice Assessment

Thank you for taking the time to complete this assessment. Please read the requirements carefully before you begin.

## Project Overview

You are tasked with building a Retrieval-Augmented Generation (RAG) application using the provided starter code. Your solution should demonstrate production-quality thinking across the full stack.

| Layer    | Provided Starter      | URL            | Substitution Policy                                                                            |
| -------- | --------------------- | -------------- | ---------------------------------------------------------------------------------------------- |
| Frontend | Next.js (React)       | localhost:3000 | Any framework you prefer.                                                                      |
| Chat UI  | Chainlit              | localhost:8000 | May be used in place of or alongside the Next.js frontend for the chat interface.              |
| Backend  | FastAPI (Python)      | localhost:6100 | Substitute with a framework you are more comfortable with, provided core requirements are met. |
| Database | PostgreSQL + pgvector | localhost:5432 | Required; do not substitute.                                                                   |

## Requirements

### 1. Chat Interface

- A user-friendly chat UI for interacting with the RAG system.
- Responses should be grounded in the content of uploaded documents.

### 2. PDF Upload

- A dedicated page on the frontend for allowing users to upload PDF documents for ingestion into the RAG pipeline.

### 3. RAG Backend

- Implement a backend service that handles document ingestion, vector storage, and retrieval-augmented generation.
- Ensure the backend is scalable, secure, and well-documented.

### 4. Database

- Use PostgreSQL with pgvector for vector storage.
- The database has not been pre-configured; you will need to set up the necessary tables and indexes for efficient RAG operations.

### 5. Testing

- Implement automated tests for the backend and frontend to ensure functionality and reliability.
- Instructions for running tests should be included in your README.

### 6. Local Run Instructions

- Clear, step-by-step instructions for running the application locally, included in your README.

### 7. Production Deployment Plan

- A brief written outline of how you would deploy this application to production, covering cloud provider choice, CI/CD strategy, and any infrastructure considerations.

## Bonus

- Include a `.env.example` file with all necessary environment variables incase you use a `.env` file.
- Document architectural decisions and any notable trade-offs.
- Include additional service layers (e.g., caching, scheduling) if you believe they would enhance the solution, and document your reasoning.

## Additional Notes

- Feel free to expand your README or inline documentation as you progress through the assessment.
- If you make architectural changes from the starter code, document your reasoning clearly.
- Commit frequently with descriptive messages to illustrate your development workflow; avoid submitting a single, monolithic commit at the conclusion of the assessment.

Good luck — we look forward to reviewing your submission!
