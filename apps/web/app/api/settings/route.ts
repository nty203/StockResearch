export const runtime = 'edge'

import { createServerClient } from '@/lib/supabase'

export async function GET() {
  const supabase = createServerClient()
  const { data, error } = await supabase
    .from('settings')
    .select('*')
    .order('key')

  if (error) return Response.json({ error: error.message }, { status: 500 })
  return Response.json(data ?? [])
}

export async function PATCH(req: Request) {
  const updates = await req.json() as { key: string; value_json: unknown }[]

  const supabase = createServerClient()
  const errors: string[] = []

  for (const { key, value_json } of updates) {
    const { error } = await supabase
      .from('settings')
      .update({ value_json, updated_at: new Date().toISOString() })
      .eq('key', key)
    if (error) errors.push(`${key}: ${error.message}`)
  }

  if (errors.length > 0) return Response.json({ errors }, { status: 500 })
  return Response.json({ ok: true })
}
