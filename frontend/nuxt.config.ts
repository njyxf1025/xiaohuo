import { defineNuxtConfig } from 'nuxt/config'
import net from 'net'
import fs from 'fs'
import os from 'os'
import path from 'path'

function resolveClientEntry(config) {
  const input = config.environments?.client?.build?.rollupOptions?.input ?? config.build?.rollupOptions?.input
  if (input) {
    if (typeof input === 'string') return input
    if (!Array.isArray(input) && input.entry) return input.entry
  }
  return null
}

function buildManifest(clientServer) {
  const config = clientServer.config
  const clientEntry = resolveClientEntry(config)
  const manifest = {
    '@vite/client': {
      file: '@vite/client',
      css: [],
      module: true,
      isEntry: true,
    },
  }
  if (clientEntry) {
    manifest[clientEntry] = {
      file: clientEntry,
      isEntry: true,
      module: true,
      resourceType: 'script',
    }
  }
  return manifest
}

function createMinimalViteNodeServer(clientServer) {
  const socketName = `nuxt-vite-node-${process.pid}-${Date.now()}`
  const socketPath = path.join(os.tmpdir(), `${socketName}.sock`)
  let cachedManifest = null

  const server = net.createServer((socket) => {
    const INITIAL_BUFFER_SIZE = 64 * 1024
    let buffer = Buffer.alloc(INITIAL_BUFFER_SIZE)
    let writeOffset = 0
    let readOffset = 0

    socket.setNoDelay(true)
    socket.setKeepAlive(true, 0)

    function resetBuffer() { writeOffset = 0; readOffset = 0 }
    function compactBuffer() {
      if (readOffset > 0) {
        const remaining = writeOffset - readOffset
        if (remaining > 0) buffer.copy(buffer, 0, readOffset, writeOffset)
        writeOffset = remaining
        readOffset = 0
      }
    }
    function ensureBufferCapacity(additionalBytes) {
      const requiredSize = writeOffset + additionalBytes
      if (requiredSize > buffer.length) {
        compactBuffer()
        if (writeOffset + additionalBytes > buffer.length) {
          const newSize = Math.max(buffer.length * 2, requiredSize)
          const newBuffer = Buffer.alloc(newSize)
          buffer.copy(newBuffer, 0, 0, writeOffset)
          buffer = newBuffer
        }
      }
    }

    function sendResponse(sock, id, data) {
      const responseJSON = JSON.stringify({ id, type: 'response', data })
      const msgBuf = Buffer.from(responseJSON, 'utf-8')
      const fullMsg = Buffer.alloc(4 + msgBuf.length)
      fullMsg.writeUInt32BE(msgBuf.length, 0)
      msgBuf.copy(fullMsg, 4)
      sock.write(fullMsg)
    }

    function sendError(sock, id, error) {
      const responseJSON = JSON.stringify({
        id,
        type: 'error',
        error: {
          message: error.message || String(error),
          stack: error.stack || '',
        },
      })
      const msgBuf = Buffer.from(responseJSON, 'utf-8')
      const fullMsg = Buffer.alloc(4 + msgBuf.length)
      fullMsg.writeUInt32BE(msgBuf.length, 0)
      msgBuf.copy(fullMsg, 4)
      sock.write(fullMsg)
    }

    async function processMessage(request) {
      try {
        switch (request.type) {
          case 'manifest': {
            if (!cachedManifest) {
              cachedManifest = buildManifest(clientServer)
            }
            sendResponse(socket, request.id, cachedManifest)
            break
          }
          case 'invalidates': {
            cachedManifest = null
            sendResponse(socket, request.id, [])
            break
          }
          case 'resolve': {
            sendResponse(socket, request.id, null)
            break
          }
          case 'module': {
            sendError(socket, request.id, { message: 'Module fetch not available in SPA mode' })
            break
          }
          default: {
            sendError(socket, request.id, { message: `Unknown request type: ${request.type}` })
          }
        }
      } catch (error) {
        sendError(socket, request.id, error)
      }
    }

    socket.on('data', (data) => {
      try {
        ensureBufferCapacity(data.length)
        data.copy(buffer, writeOffset)
        writeOffset += data.length
        while (writeOffset - readOffset >= 4) {
          const totalLength = 4 + buffer.readUInt32BE(readOffset)
          if (writeOffset - readOffset < totalLength) break
          const messageJSON = buffer.subarray(readOffset + 4, readOffset + totalLength).toString('utf-8')
          readOffset += totalLength
          try {
            const request = JSON.parse(messageJSON)
            processMessage(request).catch((error) => {
              sendError(socket, request?.id || 'unknown', error)
            })
          } catch (parseError) {
            socket.destroy(new Error('Invalid JSON in message'))
            return
          }
        }
        if (readOffset > buffer.length / 2) compactBuffer()
      } catch (error) {
        socket.destroy(error instanceof Error ? error : new Error('Buffer management error'))
      }
    })
    socket.on('error', () => { resetBuffer() })
    socket.on('close', () => { resetBuffer() })
  })

  try { fs.unlinkSync(socketPath) } catch {}
  server.listen(socketPath)
  server.on('error', () => {})

  return { socketPath, server }
}

export default defineNuxtConfig({
  srcDir: 'app/',
  ssr: false,
  devtools: { enabled: false },
  experimental: {
    appManifest: false,
  },
  app: {
    head: {
      title: '火宝短剧',
      meta: [{ name: 'viewport', content: 'width=device-width, initial-scale=1' }],
      link: [
        { rel: 'icon', type: 'image/png', href: '/favicon.png' },
        { rel: 'shortcut icon', type: 'image/png', href: '/favicon.png' },
      ],
    },
  },
  vite: {
    optimizeDeps: {
      include: ['lucide-vue-next'],
    },
    server: {
      proxy: {
        '/api': { target: 'http://localhost:5679', changeOrigin: true },
        '/static': { target: 'http://localhost:5679', changeOrigin: true },
      },
    },
  },
  hooks: {
    'vite:serverCreated'(viteServer, { isServer }) {
      if (!isServer && !process.env.NUXT_VITE_NODE_OPTIONS) {
        const { socketPath } = createMinimalViteNodeServer(viteServer)
        process.env.NUXT_VITE_NODE_OPTIONS = JSON.stringify({
          socketPath,
          root: viteServer.config.root,
          base: '/',
          baseURL: 'http://localhost:3013',
        })
      }
    },
  },
  compatibilityDate: '2025-05-15',
})
