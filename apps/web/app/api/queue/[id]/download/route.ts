export const runtime = 'edge'

import { createServerClient } from '@/lib/supabase'

export async function GET(_req: Request, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params
  const supabase = createServerClient()

  const { data: item, error } = await supabase
    .from('analysis_queue')
    .select('ticker, prompt_type, storage_path_prompt')
    .eq('id', id)
    .single()

  if (error || !item?.storage_path_prompt) {
    return Response.json({ error: 'Not found' }, { status: 404 })
  }

  const { data: file, error: storageErr } = await supabase
    .storage
    .from('analysis_queue')
    .download(item.storage_path_prompt)

  if (storageErr || !file) return Response.json({ error: 'Storage error' }, { status: 500 })

  const text = await file.text()
  const filename = `${item.ticker}_${item.prompt_type}.md`

  return new Response(text, {
    headers: {
      'Content-Type': 'text/markdown; charset=utf-8',
      'Content-Disposition': `attachment; filename="${filename}"`,
    },
  })
}
