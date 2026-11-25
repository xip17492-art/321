# Global Radar — Phase 1

Private, mobile-first PWA foundation for a global market research platform.

## Included in Phase 1
- Next.js App Router application
- Private email/password login through Supabase Auth
- Server-side session verification before dashboard rendering
- Logout
- PWA manifest and installable home-screen metadata
- Responsive dark dashboard shell for Taiwan, US, crypto and futures modules
- Security headers and environment-variable template

## Not included yet
- Live market data, chart engine, portfolio persistence, AI signals, backtesting, push notifications, or broker execution.
- The dashboard labels data sources as pending; it does not fabricate quotes.
- No real-money trading or broker order integration is present.

## Setup

1. Create a Supabase project.
2. In Supabase Authentication, disable public sign-ups. Create your private user from the Supabase dashboard (Authentication → Users → Add user).
3. Add the Vercel site URL and the matching local URL to Authentication → URL Configuration. Add `https://YOUR-VERCEL-DOMAIN/auth/callback` to allowed redirect URLs if using email OTP/magic-link flows later.
4. Copy `.env.example` to `.env.local` and fill in:
   - `NEXT_PUBLIC_SUPABASE_URL`
   - `NEXT_PUBLIC_SUPABASE_ANON_KEY` (or Supabase publishable key)
5. Run:
   ```bash
   npm install
   npm run dev
   ```
6. Deploy to Vercel with Root Directory set to `global-finance-platform`. Add the same environment variables in Vercel → Project Settings → Environment Variables, then redeploy.

## Security notes
- Do not commit `.env.local`, service-role keys, exchange API secrets, or broker credentials.
- Only the public/anon/publishable Supabase key belongs in the browser; database tables added later must use Row Level Security (RLS).
- The authenticated dashboard calls `auth.getUser()` on the server and redirects unauthenticated visitors to /login.
- For any future private user data, enforce ownership in database policies. Hiding UI is not access control.

## Existing Taiwan radar
This phase is developed under `global-finance-platform/` on a separate branch. Existing root files and the current GitHub Pages radar are intentionally left unchanged.
