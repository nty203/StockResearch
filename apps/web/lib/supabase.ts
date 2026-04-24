import { createClient } from '@supabase/supabase-js'
import type { Database } from '@stock/shared'

// Server-side client for Route Handlers (edge runtime)
// Never import this in client components
export function createServerClient() {
  return createClient<Database>(
    process.env.SUPABASE_URL!,
    process.env.SUPABASE_SERVICE_KEY!,
    { auth: { persistSession: false } },
  )
}

// Client-side client (public anon key only)
export function createBrowserClient() {
  return createClient<Database>(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
  )
}
