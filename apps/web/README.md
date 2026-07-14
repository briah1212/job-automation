# Job Automation Web Frontend

Next.js 14 frontend for the job application automation platform.

## Development

Install dependencies:
```bash
npm install
```

Run development server:
```bash
npm run dev
```

Open http://localhost:3000

## Build

```bash
npm run build
npm start
```

## Docker

```bash
docker build -t job-automation-web .
docker run -p 3000:3000 job-automation-web
```

## Environment Variables

Copy `.env.example` to `.env.local` and configure:

- `NEXT_PUBLIC_API_URL`: Backend API URL (public)
- `API_URL`: Backend API URL (server-side)
- `NEXTAUTH_SECRET`: Secret for NextAuth.js
- `NEXTAUTH_URL`: Frontend URL
