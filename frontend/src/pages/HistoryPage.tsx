import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { getHistory } from '../api/client'

interface HistoryItem {
  id: string
  musicName: string
  avatarName: string
  model: string
  videoUrl: string
  createdAt: string
}

const modelLabels: Record<string, string> = {
  wav2lip: 'Wav2Lip',
  sadtalker: 'SadTalker',
  latentsync: 'LatentSync',
}

export default function HistoryPage() {
  const [items, setItems] = useState<HistoryItem[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    getHistory()
      .then(setItems)
      .catch(() => setItems([]))
      .finally(() => setLoading(false))
  }, [])

  return (
    <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div className="flex items-center justify-between mb-8">
        <h1 className="text-2xl font-bold text-gray-100">历史记录</h1>
        <Link
          to="/create"
          className="px-4 py-2 rounded-lg bg-purple-500/20 text-purple-300 text-sm font-medium hover:bg-purple-500/30 transition-all"
        >
          + 新建
        </Link>
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-20">
          <div className="w-8 h-8 border-2 border-purple-500 border-t-transparent rounded-full animate-spin" />
        </div>
      ) : items.length === 0 ? (
        <div className="text-center py-20">
          <div className="text-5xl mb-4">📭</div>
          <p className="text-gray-500 mb-4">暂无历史记录</p>
          <Link
            to="/create"
            className="inline-flex items-center gap-2 px-6 py-2.5 rounded-xl bg-gradient-to-r from-purple-600 to-blue-600 text-white font-medium shadow-lg shadow-purple-500/25 hover:scale-105 transition-all"
          >
            开始创作
          </Link>
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {items.map((item) => (
            <div
              key={item.id}
              className="bg-[#1a1d2e] rounded-xl border border-white/5 overflow-hidden hover:border-white/10 transition-all hover:-translate-y-0.5"
            >
              <video
                src={item.videoUrl}
                className="w-full aspect-video bg-black/50"
                preload="metadata"
              />
              <div className="p-4 space-y-2">
                <h3 className="font-semibold text-gray-200 truncate">{item.musicName}</h3>
                <div className="flex items-center gap-2 text-xs text-gray-500">
                  <span className="px-2 py-0.5 rounded bg-purple-500/10 text-purple-400">
                    {modelLabels[item.model] || item.model}
                  </span>
                  <span>{item.avatarName}</span>
                </div>
                <div className="text-xs text-gray-600">
                  {new Date(item.createdAt).toLocaleString('zh-CN')}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
