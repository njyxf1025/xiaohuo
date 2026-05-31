import { useEffect, useRef, useState, useCallback } from 'react'
import WaveSurfer from 'wavesurfer.js'
import RegionsPlugin from 'wavesurfer.js/plugins/regions'

interface AudioWaveformProps {
  fileId: string
  filename: string
  duration: number
  onRegionConfirm: (start: number, end: number) => void
  onBack: () => void
}

export default function AudioWaveform({ fileId, filename, duration, onRegionConfirm, onBack }: AudioWaveformProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const wavesurferRef = useRef<WaveSurfer | null>(null)
  const [isPlaying, setIsPlaying] = useState(false)
  const [currentTime, setCurrentTime] = useState(0)
  const [regionStart, setRegionStart] = useState(0)
  const [regionEnd, setRegionEnd] = useState(Math.min(30, duration))
  const [loading, setLoading] = useState(true)

  const formatTime = (seconds: number): string => {
    const m = Math.floor(seconds / 60)
    const s = Math.floor(seconds % 60)
    const ms = Math.floor((seconds % 1) * 10)
    return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}.${ms}`
  }

  const initWaveSurfer = useCallback(() => {
    if (!containerRef.current) return

    const ws = WaveSurfer.create({
      container: containerRef.current,
      waveColor: '#6366f1',
      progressColor: '#8b5cf6',
      cursorColor: '#c084fc',
      height: 128,
      barWidth: 2,
      barGap: 1,
      barRadius: 2,
      url: `/api/music/waveform/${fileId}`,
      backend: 'WebAudio',
    })

    const regions = ws.registerPlugin(RegionsPlugin.create())

    regions.addRegion({
      start: regionStart,
      end: regionEnd,
      color: 'rgba(139, 92, 246, 0.2)',
      drag: true,
      resize: true,
    })

    regions.on('region-updated', (region) => {
      setRegionStart(Math.max(0, region.start))
      setRegionEnd(Math.min(duration, region.end))
    })

    ws.on('ready', () => {
      setLoading(false)
    })

    ws.on('play', () => setIsPlaying(true))
    ws.on('pause', () => setIsPlaying(false))
    ws.on('timeupdate', (time) => setCurrentTime(time))

    wavesurferRef.current = ws

    return () => {
      ws.destroy()
    }
  }, [fileId, regionStart, regionEnd, duration])

  useEffect(() => {
    const cleanup = initWaveSurfer()
    return () => cleanup?.()
  }, [initWaveSurfer])

  const togglePlay = () => {
    wavesurferRef.current?.playPause()
  }

  const handleStartChange = (value: string) => {
    const num = parseFloat(value)
    if (!isNaN(num) && num >= 0 && num < regionEnd) {
      setRegionStart(num)
    }
  }

  const handleEndChange = (value: string) => {
    const num = parseFloat(value)
    if (!isNaN(num) && num > regionStart && num <= duration) {
      setRegionEnd(num)
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-bold text-gray-100">选择高潮区间</h2>
        <span className="text-sm text-gray-500">{filename}</span>
      </div>

      <div className="bg-[#1a1d2e] rounded-2xl p-6 border border-white/5">
        {loading && (
          <div className="flex items-center justify-center py-8">
            <div className="w-6 h-6 border-2 border-purple-500 border-t-transparent rounded-full animate-spin mr-3" />
            <span className="text-gray-400">加载波形中...</span>
          </div>
        )}
        <div ref={containerRef} className="rounded-lg overflow-hidden" />

        <div className="flex items-center gap-4 mt-4">
          <button
            type="button"
            onClick={togglePlay}
            className="w-10 h-10 rounded-full bg-purple-500/20 text-purple-300 flex items-center justify-center hover:bg-purple-500/30 transition-all"
          >
            {isPlaying ? (
              <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
                <path d="M6 4h4v16H6V4zm8 0h4v16h-4V4z" />
              </svg>
            ) : (
              <svg className="w-4 h-4 ml-0.5" fill="currentColor" viewBox="0 0 24 24">
                <path d="M8 5v14l11-7z" />
              </svg>
            )}
          </button>
          <span className="text-sm text-gray-400 font-mono">{formatTime(currentTime)}</span>
          <span className="text-sm text-gray-600">/</span>
          <span className="text-sm text-gray-500 font-mono">{formatTime(duration)}</span>
        </div>
      </div>

      <div className="bg-[#1a1d2e] rounded-xl p-4 border border-white/5">
        <p className="text-sm text-gray-400 mb-3">高潮区间（可拖拽波形上的紫色区域调整）</p>
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2">
            <label className="text-xs text-gray-500">开始</label>
            <input
              type="text"
              value={regionStart.toFixed(1)}
              onChange={(e) => handleStartChange(e.target.value)}
              className="w-20 px-2 py-1 rounded-lg bg-white/5 border border-white/10 text-gray-300 text-sm text-center focus:outline-none focus:border-purple-500/50"
            />
            <span className="text-xs text-gray-600">秒</span>
          </div>
          <div className="text-gray-600">→</div>
          <div className="flex items-center gap-2">
            <label className="text-xs text-gray-500">结束</label>
            <input
              type="text"
              value={regionEnd.toFixed(1)}
              onChange={(e) => handleEndChange(e.target.value)}
              className="w-20 px-2 py-1 rounded-lg bg-white/5 border border-white/10 text-gray-300 text-sm text-center focus:outline-none focus:border-purple-500/50"
            />
            <span className="text-xs text-gray-600">秒</span>
          </div>
          <div className="ml-auto text-sm text-purple-400 font-medium">
            时长 {(regionEnd - regionStart).toFixed(1)}s
          </div>
        </div>
      </div>

      <div className="flex items-center justify-between pt-2">
        <button
          type="button"
          onClick={onBack}
          className="px-6 py-2.5 rounded-xl text-gray-400 hover:text-gray-200 hover:bg-white/5 transition-all"
        >
          ← 重新上传
        </button>
        <button
          type="button"
          onClick={() => onRegionConfirm(regionStart, regionEnd)}
          className="px-8 py-3 rounded-xl bg-gradient-to-r from-purple-600 to-blue-600 text-white font-semibold shadow-lg shadow-purple-500/25 hover:shadow-purple-500/40 hover:scale-105 transition-all duration-300"
        >
          确认区间 →
        </button>
      </div>
    </div>
  )
}
