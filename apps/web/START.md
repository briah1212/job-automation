# Quick Start Guide

## Installation

```bash
cd /home/brian/job_automation/apps/web
npm install
```

## Development Server

```bash
npm run dev
```

Visit: http://localhost:3000

## Build for Production

```bash
npm run build
npm start
```

## Docker Build

```bash
docker build -t job-automation-web .
docker run -p 3000:3000 -e NEXT_PUBLIC_API_URL=http://localhost:8000 job-automation-web
```

## Environment Setup

1. Copy .env.example to .env.local
2. Update NEXTAUTH_SECRET with a secure random string
3. Configure API_URL to point to your backend

## Routes

- / → Redirects to /dashboard
- /auth/login → Login page
- /auth/register → Registration page
- /dashboard → Main dashboard with stats
- /dashboard/profile → User profile editor
- /dashboard/resumes → Resume management
- /dashboard/resumes/[id] → Resume detail
- /dashboard/jobs → Job listings
- /dashboard/jobs/[id] → Job detail with match analysis
- /dashboard/applications → Application kanban board
- /dashboard/applications/[id] → Application review

## Tech Stack

- Next.js 14 (App Router)
- TypeScript
- Tailwind CSS
- shadcn/ui components
- NextAuth.js for authentication
- React Hook Form + Zod validation
- Lucide React icons
