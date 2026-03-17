# Run: Auth And Dashboard

## Tasks

### auth
Title: Add user authentication

Implement JWT-based auth with login/signup endpoints.

Acceptance criteria:
- signup endpoint exists
- login returns JWT
- auth middleware protects private routes

### dashboard_api
Title: Create dashboard API
Depends on: auth

Build REST endpoints for dashboard data aggregation.

Acceptance criteria:
- endpoint returns summary stats
- integration test covers auth + response shape
