import assert from 'node:assert/strict'
import { test } from 'node:test'
import { fileURLToPath } from 'node:url'
import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { createServer } from 'vite'

import { api } from '../src/api.js'


test('API helper uses the expected routes and browser key header', async (t) => {
  const originalFetch = globalThis.fetch
  const originalLocalStorage = globalThis.localStorage
  t.after(() => {
    globalThis.fetch = originalFetch
    if (originalLocalStorage === undefined) delete globalThis.localStorage
    else globalThis.localStorage = originalLocalStorage
  })

  const calls = []
  globalThis.localStorage = { getItem: () => 'browser-test-key' }
  globalThis.fetch = async (url, options = {}) => {
    calls.push({ url, options })
    return { ok: true, json: async () => ({ ok: true }) }
  }

  await api.ask('Question?', [{ role: 'user', content: 'Earlier' }])
  await api.getDocuments()
  await api.ingest(new Blob(['document']))
  await api.ingestUrl('https://example.com')
  await api.deleteDocument('a b.pdf')
  await api.deleteAllDocuments()
  await api.getHistory()
  await api.saveHistory([])

  assert.deepEqual(
    calls.map(({ url, options }) => [url, options.method || 'GET']),
    [
      ['/api/ask', 'POST'],
      ['/api/documents', 'GET'],
      ['/api/ingest', 'POST'],
      ['/api/ingest/url', 'POST'],
      ['/api/document?filename=a%20b.pdf', 'DELETE'],
      ['/api/documents', 'DELETE'],
      ['/api/history', 'GET'],
      ['/api/history', 'POST'],
    ],
  )
  assert.equal(calls[0].options.headers['X-Groq-Api-Key'], 'browser-test-key')
  assert.deepEqual(JSON.parse(calls[0].options.body), {
    question: 'Question?',
    chat_history: [{ role: 'user', content: 'Earlier' }],
  })
  assert.ok(calls[2].options.body instanceof FormData)
})


test('App renders the empty workspace without a browser or backend', async (t) => {
  const root = fileURLToPath(new URL('..', import.meta.url))
  const vite = await createServer({
    root,
    appType: 'custom',
    logLevel: 'silent',
    server: { middlewareMode: true },
  })
  t.after(() => vite.close())

  const { default: App } = await vite.ssrLoadModule('/src/App.jsx')
  const html = renderToStaticMarkup(createElement(App))

  assert.match(html, /Studio Workspace/)
  assert.match(html, /Search your documents/)
  assert.match(html, /Add sources/)
})
