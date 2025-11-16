# GCRegisterWeb-10-26 - React Frontend

TypeScript + React SPA for PayGate Prime channel registration and management.

## Architecture

- **Framework:** React 18 with TypeScript
- **Build Tool:** Vite 5
- **Routing:** React Router v6
- **State Management:** TanStack Query (React Query)
- **API Client:** Axios with JWT authentication
- **Backend API:** https://gcregisterapi-10-26-291176869049.us-central1.run.app

## Features

- User authentication (signup/login) with JWT
- Dashboard showing all user channels (0-10 limit)
- Channel management (view details, edit, delete)
- Threshold payout visualization (progress bars)
- Automatic token refresh on 401
- Protected routes

## Development

```bash
# Install dependencies
npm install

# Run dev server (localhost:5173)
npm run dev

# Build for production
npm run build

# Preview production build
npm run preview
```

## Environment Variables

Create `.env` file:

```
VITE_API_URL=https://gcregisterapi-10-26-291176869049.us-central1.run.app
```

## Deployment to Cloud Storage

```bash
# Build production bundle
npm run build

# Upload to Cloud Storage bucket
gsutil -m rsync -r dist/ gs://www-paygateprime-com

# Set cache headers
gsutil -m setmeta -h "Cache-Control:public, max-age=31536000" 'gs://www-paygateprime-com/assets/*.js'
gsutil -m setmeta -h "Cache-Control:public, max-age=31536000" 'gs://www-paygateprime-com/assets/*.css'
```

## Project Structure

```
src/
├── pages/              # Route pages
│   ├── LoginPage.tsx
│   ├── SignupPage.tsx
│   └── DashboardPage.tsx
├── services/           # API layer
│   ├── api.ts
│   ├── authService.ts
│   └── channelService.ts
├── types/              # TypeScript types
│   ├── auth.ts
│   └── channel.ts
├── App.tsx             # Root component
├── main.tsx            # Entry point
└── index.css           # Global styles
```

## Integration with Backend

All API calls go to GCRegisterAPI-10-26:
- `POST /api/auth/signup` - User registration
- `POST /api/auth/login` - User login
- `POST /api/auth/refresh` - Token refresh
- `GET /api/channels` - Get user's channels
- `POST /api/channels/register` - Register new channel
- `PUT /api/channels/:id` - Update channel
- `DELETE /api/channels/:id` - Delete channel

## Token Management

- Access token: Stored in localStorage, expires in 15 minutes
- Refresh token: Stored in localStorage, expires in 30 days
- Automatic refresh on 401 response
- Redirect to /login if refresh fails
