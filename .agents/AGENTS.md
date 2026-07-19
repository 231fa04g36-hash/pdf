# Project Development Rules & Guidelines

These are the core engineering standards and rules to be followed throughout this PDF Chatbot project. Every feature, component, API endpoint, and modification must adhere to these practices.

## 1. Project Structure

Organize the application into clean, modular, feature-based folders. Do not create folders like `misc/`, `temp/`, or `newfolder/`.

- **Frontend (`frontend/` or root client folder)**:
  - `features/`: Feature-specific modules containing their own state, components, and logic.
  - `components/`: Reusable, generic UI components (e.g., `Button`, `Input`, `Modal`).
  - `services/`: API services and external clients (e.g., Axios instance and endpoints).
  - `hooks/`: Reusable React hooks.
  - `utils/`: Reusable helper functions.
  - `constants/`: Global constants, configuration values, and action types.
- **Backend (`backend/` or root server folder)**:
  - Feature-based structure matching the backend modules (e.g., upload, chat, health).

## 2. Code Quality & Standards

- **Linting & Formatting**: Follow ESLint and Prettier configurations strictly.
- **Naming Conventions**:
  - Components: PascalCase (e.g., `ChatWindow`, `ChatMessage`, `UploadBox`).
  - Functions & Variables: camelCase (e.g., `validatePDF`, `uploadPDF`, `fetchAnswer`, `displayToast`).
  - Folders & Files: lowercase or kebab-case where appropriate, except for React component files which should match their component name (PascalCase).
- **Single Responsibility (SOLID)**: Keep functions and components small and focused on a single responsibility.
- **DRY (Don't Repeat Yourself)**: Abstract duplicate logic into reusable components, services, or custom hooks.
- **Keep Components Dumb**: Presentational components should only render UI and emit events. Business logic (API calls, complex calculations) belongs in hooks, services, or utils.

## 3. State Management

- **Local State**: Use `useState()` strictly for local UI-specific states such as inputs, loading/spinning indicators, and modal open/close states.
- **Shared State**: Use React Context (or equivalent lightweight state management) for state shared across multiple components (e.g., Theme, User Session, Chat History).
- **Server State**: Use **TanStack Query (React Query)** to handle all API operations, including caching, retries, loading states, refetching, and handling stale data. Avoid manual state management of API data.

## 4. API Design

- **Consistent Endpoints**: Structure endpoints logically, for example:
  - `GET /health` (Health check)
  - `POST /upload` (Upload PDF)
  - `POST /chat` (Query chat/AI)
  - `DELETE /chat` (Clear chat history)
- **Standardized Response Envelope**: All endpoints must return a consistent JSON response:
  ```json
  {
      "success": true,
      "message": "Operation description",
      "data": {}
  }
  ```

## 5. Error Handling & Validation

- **Request & UI States**: Every API call must explicitly handle:
  - **Loading**: Show skeleton placeholders or loading spinners (never show raw text like "Loading...").
  - **Success**: Display success feedback (e.g., React Hot Toast).
  - **Failure**: Gracefully handle errors and present user-friendly alerts.
  - **Timeout**: Gracefully handle slow or dropped requests.
- **Upload Validation**: Every file upload must validate:
  - Only PDF files (`application/pdf`).
  - Maximum file size limit.
  - Empty files.
  - Corrupted/unreadable files.

## 6. GitHub & Documentation Quality

- **Essential Repository Files**:
  - `README.md` (Detailed setup instructions, architecture diagram, screenshots, and demo GIF).
  - `.gitignore` (Ignore venv, node_modules, env secrets, vector databases, etc.).
  - `.env.example` (Template for required environment variables).
  - Backend dependency tracker (e.g., `requirements.txt`).
  - Frontend package file (`package.json`).
  - `LICENSE`.
- **Logging**: Use proper Python logging (`logging.info()`, `logging.error()`) on the backend. Do not use raw `print()` statements.
- **Environment Variables**: Never hardcode API keys, Backend URLs, or Database URLs.
- **Security Basics**:
  - Sanitize all uploaded filenames before saving.
  - Validate and restrict upload sizes on both frontend and backend.
  - Never expose API keys or credentials to the frontend.

## 7. Communication Preferences

- Always converse with the user in **Hinglish** (Hindi language written using the Roman script/English alphabet) for all responses. Avoid pure English and Devanagari script.
